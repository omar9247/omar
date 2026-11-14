import numpy as np
import pandas as pd

from contract.schema import load_signals, model_signals
from generator.sim import BASELINE_DAYS, make_profile, simulate
from model.dataset import baseline_stats, normalise

SLEEP_SD = {s["name"]: s for s in load_signals()}["sleep_duration_h"]["sim_sd"]


def frame(sleep: list[float]) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    df = simulate(make_profile(rng), len(sleep), rng)
    df["sleep_duration_h"] = sleep
    return df


def test_k0_mean_is_the_plain_baseline():
    df = frame(list(np.random.default_rng(1).normal(6.5, 1, 30)))
    centre, sd = baseline_stats(df, "mean", 0)
    base = df[model_signals()].iloc[:BASELINE_DAYS]
    assert np.allclose(centre, base.mean()) and np.allclose(sd, base.std().clip(lower=1e-3))


def test_blending_widens_a_narrow_baseline_toward_the_population():
    steady = frame([6.5, 6.6] * 7 + [6.5] * 10)  # unusually steady baseline: own spread ~0.05 h
    own = baseline_stats(steady, "mean", 0)[1]["sleep_duration_h"]
    blended = baseline_stats(steady, "mean", 6)[1]["sleep_duration_h"]
    assert own < 0.1 and 0.5 < blended < SLEEP_SD  # (13*0.05^2 + 6*0.98^2) / 19 -> ~0.55


def test_median_ignores_one_extreme_baseline_day():
    nights = list(np.random.default_rng(2).normal(6.5, 1, 14))
    wild = nights.copy(); wild[3] = 1.0  # one 1-hour night in the baseline
    for scaling, max_change in (("median", 0.15), ("mean", None)):
        a = baseline_stats(frame(nights), scaling, 6)[1]["sleep_duration_h"]
        b = baseline_stats(frame(wild), scaling, 6)[1]["sleep_duration_h"]
        if max_change is None:
            assert b / a > 1.3      # mean/SD: the one night inflates the spread
        else:
            assert abs(b / a - 1) < max_change


def test_deviations_are_capped():
    df = frame([6.5, 6.6] * 7 + [40.0] * 10)  # absurd sensor values after the baseline
    assert normalise(df, cap=6.0)["sleep_duration_h"].max() == 6.0
