"""Scoring service (separate container so a crash never stops rule alerts, NFR-4).
uvicorn model.service:app --port 8001

POST /score {"crew_id": "cm1", "window": {"<signal>": [z_oldest, ..., z_today], ...}}
  Values are baseline-normalised z-scores, one per day, 3 to 14 days (14 recommended). Two detectors (plan 4.3):
  the 2-day autoencoder (sudden change; its score is the lower of today's and yesterday's, so an alarm needs two
  days in a row) and the one-sided EWMA drift score over all days sent (slow drift). Missing signals = baseline (0).
  Values are clipped at +-Z_CAP like training; NaN or infinite values are rejected (422).
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Annotated

import torch
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from model import ewma
from model.autoencoder import errors, load
from model.dataset import CONFIRM_DAYS, WINDOWS, Z_CAP

ARTIFACTS = Path(os.environ.get("AURA_ARTIFACTS", "artifacts"))
MIN_DAYS = max(WINDOWS) + CONFIRM_DAYS - 1
app = FastAPI(title="AURA-Bio model service")
_models: dict = {}


@app.exception_handler(RequestValidationError)
async def _invalid(_, exc: RequestValidationError) -> JSONResponse:
    """422 without echoing the input: the default handler crashes (500) writing a rejected NaN back as JSON."""
    return JSONResponse(status_code=422, content={"detail": [
        {k: v for k, v in e.items() if k not in ("input", "ctx")} for e in exc.errors()]})


def _load():
    if not _models:
        files = [ARTIFACTS / f"model_{w}d.pt" for w in WINDOWS] + [ARTIFACTS / "ewma.json"]
        for w, f in zip(WINDOWS, files):
            _models[w] = load(f)
        _models["ewma"] = ewma.load(files[-1])
        assert _models["ewma"][2] == _models[min(WINDOWS)][2], "ewma.json and the models list different signals"
        # which trained files produced a score: changes on every retrain, so stored scores stay traceable
        _models["version"] = hashlib.sha256(b"".join(f.read_bytes() for f in files)).hexdigest()[:12]
    return _models


class ScoreRequest(BaseModel):
    crew_id: str
    window: dict[str, list[Annotated[float, Field(allow_inf_nan=False)]]]  # NaN/inf -> 422, never a silent "healthy"


class ScoreResponse(BaseModel):
    crew_id: str
    score: float                 # higher of the two detectors; > 1 = outside 99.5% of normal
    anomalous: bool
    detector: str                # which gave the higher score: "2d" (sudden change) or "ewma" (slow drift)
    scores: dict[str, float]     # per detector, e.g. {"2d": 0.4, "ewma": 1.3}
    contributions: dict[str, float]  # share of the top detector's score per signal, sums to 1
    drift: dict[str, float]      # smoothed harmful drift per signal in z units (sign = direction, 0 = not worse)
    model_version: str           # hash of the trained files that produced this score
    label: str = "research concept, not validated on crew data"


@app.get("/health")
def health():
    try:
        m = _load()
        return {"status": "ok", "windows": list(WINDOWS), "confirm_days": CONFIRM_DAYS, "ewma": True,
                "model_version": m["version"]}
    except Exception as e:  # noqa: BLE001
        return {"status": "degraded", "error": str(e)}


@app.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest):
    models = _load()
    sig = models[min(WINDOWS)][2]
    unknown = set(req.window) - set(sig)
    if unknown:
        raise HTTPException(422, f"unknown signals: {sorted(unknown)}")
    days = {len(v) for v in req.window.values()}
    if len(days) != 1:
        raise HTTPException(422, f"all signals need the same number of days, got {sorted(days)}")
    n = days.pop() if days else 0
    if not MIN_DAYS <= n <= ewma.DAYS:
        raise HTTPException(422, f"need {MIN_DAYS} to {ewma.DAYS} days, got {n}")
    x = torch.tensor([req.window.get(s, [0.0] * n) for s in sig], dtype=torch.float32).T  # (days, signals)
    x = x.clamp(-Z_CAP, Z_CAP)  # same cap as training; a no-op when the core already applied it

    results = {}
    for w in WINDOWS:
        m, thr, _ = models[w]
        batch = torch.stack([x[n - w - i : n - i] for i in range(CONFIRM_DAYS)])  # today, yesterday, ...
        err, per_sig = errors(m, batch)
        results[f"{w}d"] = (float(err.min()) / thr, per_sig[0])  # alarm only if every day is over the line
    s, terms, e = ewma.score(x.numpy(), *models["ewma"])
    results["ewma"] = (float(s), torch.from_numpy(terms))
    top = max(results, key=lambda k: results[k][0])
    sc, per_sig = results[top]
    tot = float(per_sig.sum()) or 1.0
    return ScoreResponse(crew_id=req.crew_id, score=round(sc, 3), anomalous=sc > 1, detector=top,
                         scores={k: round(v, 3) for k, (v, _) in results.items()},
                         contributions={s: round(float(v) / tot, 3) for s, v in zip(sig, per_sig)},
                         drift={name: round(float(v), 3) for name, v in zip(sig, e)}, model_version=models["version"])
