"""python -m model.train  -> artifacts/model_2d.pt + artifacts/ewma.json, then evaluates the pair over several
training seeds (an autoencoder moves 10-20 points between retrains; one run can't rank changes).

Two detectors (plan 4.3): the 2-day autoencoder for sudden change, alarm confirmed on CONFIRM_DAYS days in a
row; the one-sided EWMA drift score (model/ewma.py) for slow drift. /score reports the higher of the two."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch

from contract.schema import model_signals
from generator.sim import BASELINE_DAYS, SCENARIOS
from model import ewma
from model.autoencoder import WindowAE, errors, save
from model.dataset import CONFIRM_DAYS, WINDOWS, confirmed, normal_frames, scenario_run, windows
from model.eval_scenarios import PATTERNS, SWEEP, SWEEP_DAYS

ARTIFACTS = Path("artifacts")


def artifact(w: int) -> Path:
    return ARTIFACTS / f"model_{w}d.pt"


def train_one(w: int, train_z: list, val_z: list, epochs: int, quantile: float, seed: int = 0) -> tuple[WindowAE, float]:
    torch.manual_seed(seed)
    train = torch.from_numpy(np.concatenate([windows(z, w) for z in train_z]))
    val = torch.from_numpy(np.concatenate([windows(z, w) for z in val_z]))
    model = WindowAE(w, train.shape[2])
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loader = torch.utils.data.DataLoader(train, batch_size=256, shuffle=True)
    for ep in range(epochs):
        model.train()
        for xb in loader:
            loss = ((model(xb) - xb) ** 2).mean()
            opt.zero_grad(); loss.backward(); opt.step()
    model.eval()
    val_err = errors(model, val)[0].numpy()
    threshold = float(np.quantile(val_err, quantile))
    print(f"{w:2d}-day: train {loss.item():.3f}  val {val_err.mean():.3f}  threshold(p{quantile*100:g})={threshold:.3f}")
    return model, threshold


def train_ewma(train_z: list, val_z: list, quantile: float, sig: list[str]):
    win = lambda frames: np.concatenate([windows(z, ewma.DAYS) for z in frames])
    sd, thr = ewma.calibrate(win(train_z), win(val_z), sig, quantile)
    print(f"ewma:   threshold(p{quantile*100:g})={thr:.3f}")
    return sd, thr, sig


def daily_scores(z, models: dict, ew: tuple) -> dict:
    """Per detector, one score per day from BASELINE_DAYS on (> 1 = alarm), as /score computes them."""
    out = {}
    for w, (m, thr) in models.items():  # windows from k-1 days earlier, so each day can be confirmed
        x = torch.from_numpy(windows(z, w, start=BASELINE_DAYS - CONFIRM_DAYS + 1))
        out[f"{w}d"] = confirmed(errors(m, x)[0].numpy() / thr)
    out["ewma"] = ewma.score(windows(z, ewma.DAYS), *ew)[0]
    out["combined"] = np.max(list(out.values()), axis=0)
    return out


def evaluate(models: dict, ew: tuple, n: int = 200, days: int = 40) -> dict:
    """Per scenario, over n simulated astronauts (n/2 for the 60 sweep scenarios): share flagged (score > 1) after
    onset, median day of first flag, and false alarms per normal day before onset. 'combined' = what /score reports.
    Covers the demo scenarios, the research-doc patterns and the per-signal sweep (model/eval_scenarios.py); sweep runs
    use their own, longer length.
    Returns {scenario: {detector: (%, day, %)}}; prints all but the sweep."""
    onset = SCENARIOS["normal"].onset_day
    print(f"{n} astronauts per scenario, onset day {onset}: flagged % / median day after onset / false alarms per day before onset")
    out = {}
    for name, sc in {**SCENARIOS, **PATTERNS, **SWEEP}.items():
        m = n // 2 if name in SWEEP else n
        length = sc.days if name in SWEEP else days
        per = [daily_scores(scenario_run(sc, n_days=length, seed=seed)[1], models, ew) for seed in range(1000, 1000 + m)]
        out[name], cells = {}, []
        for k in per[0]:
            runs = np.array([p[k] for p in per])
            pre, post = runs[:, : onset - BASELINE_DAYS], runs[:, onset - BASELINE_DAYS :]
            first = np.array([np.argmax(r > 1) if (r > 1).any() else np.nan for r in post])
            hit = np.isfinite(first)
            med = float(np.nanmedian(first)) if hit.any() else np.nan
            out[name][k] = (hit.mean() * 100, med, (pre > 1).mean() * 100)
            cells.append(f"{k}: {hit.mean() * 100:3.0f}% {med:4.1f} {(pre > 1).mean() * 100:3.1f}%")
        if name not in SWEEP:
            print(f"{name:25s} " + " | ".join(cells))
    return out


def summarise(runs: list[dict]) -> None:
    """Mean [min-max] over training seeds of each evaluate() cell; the sweep as one table (combined detector)."""
    def cell(v, d=0):
        v = v[np.isfinite(v)]
        return f"{v.mean():4.{d}f} [{v.min():.{d}f}-{v.max():.{d}f}]" if len(v) else "   -"
    print(f"\nOver {len(runs)} training seeds, mean [min-max]: flagged % / median day / false alarms % of days")
    for name in runs[0]:
        if name in SWEEP:
            continue
        print(name)
        for k in runs[0][name]:
            v = np.array([r[name][k] for r in runs])
            print(f"  {k:8s} {cell(v[:, 0])} {cell(v[:, 1])} {cell(v[:, 2], 1)}")  # false alarms are ~1%: keep a decimal
    print(f"\nSweep: one signal drifting alone in its harmful direction, % flagged (combined, mean over seeds); "
          f"healthy astronauts over the same {SWEEP_DAYS - SCENARIOS['normal'].onset_day} days: "
          f"{np.mean([r['sweep_normal']['combined'][0] for r in runs]):.0f}%")
    print(f"  {'signal':24s} " + " ".join(f"{m}sd {sp:4s}" for m in (1, 2, 3) for sp in ("fast", "slow")))
    for s in model_signals():
        vals = [np.mean([r[f"sweep_{s}_{m}sd_{sp}"]["combined"][0] for r in runs]) for m in (1, 2, 3) for sp in ("fast", "slow")]
        print(f"  {s:24s} " + " ".join(f"{v:9.0f}" for v in vals))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--crew", type=int, default=300)
    ap.add_argument("--val-crew", type=int, default=1000,
                    help="astronauts that set the alarm lines (60 made them wobble 32-48; 300 still 32-40)")
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--quantile", type=float, default=0.995,
                    help="alarm line per detector; 0.995 + 2-day confirmation flags ~5%% of healthy astronauts in 19 days (plan 6.3)")
    ap.add_argument("--seeds", type=int, default=3, help="training seeds to compare over; the first is saved")
    ap.add_argument("--no-eval", action="store_true",
                    help="train seed 0 and save artifacts only, skipping the scenario evaluation (fast image builds)")
    a = ap.parse_args()
    assert 1 <= a.seeds <= 9, "data seeds 1+100k / 2+100k must stay below the evaluation seeds (1000+)"

    sig = model_signals()
    runs = []
    for k in range(a.seeds):
        print(f"\n=== training seed {k} ===")
        train_z, val_z = normal_frames(a.crew, a.days, seed=1 + 100 * k), normal_frames(a.val_crew, a.days, seed=2 + 100 * k)
        models = {w: train_one(w, train_z, val_z, a.epochs, a.quantile, seed=k) for w in WINDOWS}
        ew = train_ewma(train_z, val_z, a.quantile, sig)
        if k == 0:  # seed 0 = the original data seeds 1/2: the saved artifacts stay reproducible
            for w, (m, thr) in models.items():
                save(artifact(w), m, thr, sig)
            ewma.save(ARTIFACTS / "ewma.json", *ew)
        print()
        if not a.no_eval:
            runs.append(evaluate(models, ew))
    if runs:
        summarise(runs)
    else:
        print(f"\nSaved {', '.join(str(artifact(w)) for w in WINDOWS)} and {ARTIFACTS / 'ewma.json'} (evaluation skipped)")


if __name__ == "__main__":
    main()
