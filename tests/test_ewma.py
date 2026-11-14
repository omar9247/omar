import numpy as np

from contract.schema import model_signals
from generator.sim import BASELINE_DAYS, SCENARIOS
from model import ewma
from model.dataset import normal_frames, scenario_run, windows

SIG = model_signals()


def test_every_model_input_has_a_harmful_direction():
    assert set(ewma.HARMFUL) == set(SIG) and set(ewma.HARMFUL.values()) <= {"high", "low", "both"}


def drift(signal: str, z: float) -> float:
    x = np.zeros((ewma.DAYS, len(SIG)))
    x[:, SIG.index(signal)] = z
    return float(ewma.score(x, np.ones(len(SIG)), 1.0, SIG)[0])


def test_only_the_harmful_direction_counts():
    assert drift("sleep_duration_h", -1) > 0.9          # sleeping less: counts (0.956**2 after 14 days)
    assert drift("sleep_duration_h", +1) == 0           # sleeping more: ignored
    assert drift("resting_hr_bpm", +1) > 0.9 and drift("resting_hr_bpm", -1) == 0
    assert drift("bp_systolic_mmhg", +1) == drift("bp_systolic_mmhg", -1) > 0.9  # both directions


def test_drift_outscores_noise_and_catches_sleep_debt():
    """Calibrated on normal astronauts: ~1% of normal days over the line, sleep debt flagged far more often."""
    win = lambda frames: np.concatenate([windows(z, ewma.DAYS) for z in frames])
    sd, thr = ewma.calibrate(win(normal_frames(80, 60, seed=21)), win(normal_frames(40, 60, seed=22)), SIG, 0.99)
    normal = ewma.score(win(normal_frames(40, 60, seed=23)), sd, thr, SIG)[0]
    assert (normal > 1).mean() < 0.03
    late = SCENARIOS["sleep_debt"].onset_day + 10 - BASELINE_DAYS  # 10 days into the scenario
    flagged = [ewma.score(windows(scenario_run("sleep_debt", seed=s)[1], ewma.DAYS), sd, thr, SIG)[0][late] > 1
               for s in range(500, 540)]
    assert np.mean(flagged) > 0.5


def test_slow_sweep_runs_long_enough_to_reach_full_size():
    from model.eval_scenarios import SWEEP
    onset = SCENARIOS["normal"].onset_day
    for name, sc in SWEEP.items():
        ramp = max((e.ramp_days for e in sc.effects.values()), default=0)
        assert sc.days - onset >= ramp + 14, name  # at least two weeks at full size after the ramp
