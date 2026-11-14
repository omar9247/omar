"""Training data for the autoencoder: windows of baseline-normalised daily signals.

Normalisation is per astronaut: z = (x - baseline centre) / blended baseline spread over the first BASELINE_DAYS,
clipped at +-Z_CAP (see baseline_stats). The core service must do exactly the same with its stored Baseline rows,
then call /score.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from contract.schema import load_signals, model_signals
from generator.sim import BASELINE_DAYS, SCENARIOS, Scenario, make_profile, simulate

WINDOWS = (2,)  # days; autoencoder for sudden change. Slow drift is model/ewma.py (7/14-day AEs dropped, plan 6.3)
CONFIRM_DAYS = 2  # an autoencoder alarm needs this many days in a row over the line (halves false alarms, plan 6.3)


def confirmed(scores: np.ndarray, k: int = CONFIRM_DAYS) -> np.ndarray:
    """Lowest of each run of k consecutive daily scores (last axis): > 1 only if all k days are over the line.
    Output has k - 1 fewer days, aligned to the last day of each run."""
    return np.lib.stride_tricks.sliding_window_view(scores, k, axis=-1).min(-1)


SCALING = "mean"  # baseline centre: "mean" or "median" (median + MAD tested worse: solar 57% vs 100%, plan 6.3)
BLEND_K = 6       # days' worth of weight for the population spread (best k on real BIDSleep + ISS CO2 data, plan 6.3)
Z_CAP = 8.0       # clip deviations at +-Z_CAP spreads: tames heavy tails; 6 flattened the solar event (plan 6.3)


def typical_sd(s: dict, centre: float) -> float:
    """Population day-to-day spread (signals.yaml sim_sd), moved to this astronaut's level for multiplicative signals."""
    if s.get("log"):
        return s["sim_sd"] * centre / s["sim_mean"]
    if "log_from" in s:  # the shortfall below the cap varies multiplicatively
        return s["sim_sd"] * max(s["log_from"] - centre, 1e-6) / (s["log_from"] - s["sim_mean"])
    return s["sim_sd"]


def baseline_stats(df: pd.DataFrame, scaling: str = SCALING, k: float = BLEND_K) -> tuple[pd.Series, pd.Series]:
    """Per model signal: baseline centre and spread over the first BASELINE_DAYS. The astronaut's own spread is
    blended with the population spread: sd^2 = ((n-1) own^2 + k pop^2) / (n-1+k), so 14 unusually steady or
    unusually wild days can't make every later day look too big or too small."""
    base = df[model_signals()].iloc[:BASELINE_DAYS]
    if scaling == "median":
        centre = base.median()
        own = 1.4826 * (base - centre).abs().median()  # MAD, scaled to match an SD for normal data
    else:
        centre, own = base.mean(), base.std()
    n = base.count() - 1
    pop = pd.Series({s["name"]: typical_sd(s, centre[s["name"]]) for s in load_signals() if s.get("model")})
    sd = np.sqrt((n * own.fillna(0) ** 2 + k * pop**2) / (n + k).clip(lower=1e-9))
    return centre, sd.clip(lower=1e-3)


def normalise(df: pd.DataFrame, scaling: str = SCALING, k: float = BLEND_K, cap: float = Z_CAP) -> pd.DataFrame:
    centre, sd = baseline_stats(df, scaling, k)
    z = ((df[model_signals()] - centre) / sd).clip(-cap, cap)
    return z.fillna(0.0)  # missing (stale) -> baseline; core marks it stale separately


def windows(z: pd.DataFrame, w: int, start: int = BASELINE_DAYS) -> np.ndarray:
    """(n_windows, w, n_signals): one window ending on each day from `start` on."""
    arr = z.to_numpy(dtype=np.float32)
    return np.stack([arr[t - w + 1 : t + 1] for t in range(max(start, w - 1), len(arr))])


def normal_frames(n_crew: int, n_days: int, seed: int) -> list[pd.DataFrame]:
    """Baseline-normalised normal days, one frame per simulated astronaut."""
    rng = np.random.default_rng(seed)
    return [normalise(simulate(make_profile(rng), n_days, rng)) for _ in range(n_crew)]


def scenario_run(scenario: Scenario | str, n_days: int = 40, seed: int = 0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Raw daily frame and its baseline-normalised version."""
    sc = SCENARIOS[scenario] if isinstance(scenario, str) else scenario
    rng = np.random.default_rng(seed)
    df = simulate(make_profile(rng), n_days, rng, sc)
    return df, normalise(df)
