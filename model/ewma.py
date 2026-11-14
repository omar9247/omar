"""One-sided EWMA drift score: slow, sustained drift away from an astronaut's own baseline (plan 4.3 step 4).
Pairs with the 2-day autoencoder, which catches sudden changes. Nothing is learned: each signal's normal size
of the smoothed value and the alarm line are measured on simulated normal astronauts by model.train.

Per signal: smooth the daily z-scores over time keeping the sign, drop the harmless direction, divide by its
normal size, square. Score = sum over signals / alarm line, so > 1 = outside 99% of normal, as for /score.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from contract.schema import load_signals

LAMBDA = 0.2  # weight of today's value; memory ~1/LAMBDA = 5 days, 0.8**14 = 4% left after a 14-day window
DAYS = 14     # longest window /score receives
HARMFUL = {s["name"]: s["harmful"] for s in load_signals() if s.get("model")}  # contract/signals.yaml `harmful`


def smooth(x: np.ndarray) -> np.ndarray:
    """EWMA over the days axis of x (..., days, signals), starting at baseline (0); value on the last day."""
    e = np.zeros(x.shape[:-2] + x.shape[-1:])
    for t in range(x.shape[-2]):
        e = LAMBDA * x[..., t, :] + (1 - LAMBDA) * e
    return e


def harmful(e: np.ndarray, signals: list[str]) -> np.ndarray:
    """Zero each smoothed value that moved in its harmless direction."""
    sign = np.array([{"high": 1, "low": -1, "both": 0}[HARMFUL[s]] for s in signals])
    return np.where((sign == 0) | (e * sign > 0), e, 0.0)


def score(x: np.ndarray, sd: np.ndarray, threshold: float, signals: list[str]):
    """x (..., days, signals) of z-scores -> (score, per-signal terms, signed smoothed harmful drift)."""
    e = harmful(smooth(x), signals)
    terms = (e / sd) ** 2
    return terms.sum(-1) / threshold, terms, e


def calibrate(train: np.ndarray, val: np.ndarray, signals: list[str], quantile: float):
    """Normal size of each smoothed signal (RMS on train windows) and the alarm line (quantile on val)."""
    sd = np.sqrt((smooth(train) ** 2).mean(0)).clip(min=1e-6)
    return sd, float(np.quantile(score(val, sd, 1.0, signals)[0], quantile))


def save(path: Path, sd: np.ndarray, threshold: float, signals: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"lambda": LAMBDA, "signals": signals, "sd": sd.tolist(), "threshold": threshold}))


def load(path: Path) -> tuple[np.ndarray, float, list[str]]:
    d = json.loads(path.read_text())
    assert d["lambda"] == LAMBDA, "artifact made with another LAMBDA: retrain"
    return np.array(d["sd"]), d["threshold"], d["signals"]
