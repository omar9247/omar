import numpy as np

from generator.replay import apply_replay, co2_series, dose_series
from generator.sim import SCENARIOS, make_profile, simulate, to_readings


def _sim(name="normal", days=40):
    rng = np.random.default_rng(0)
    return simulate(make_profile(rng), days, rng, SCENARIOS[name])


def test_replay_uses_real_values_and_labels_them():
    df, prov = apply_replay(_sim(), "cm1", SCENARIOS["normal"], "RR-5")
    assert np.allclose(df["cabin_co2_mmhg"], co2_series("RR-5")[:40])
    assert np.allclose(df["dose_mgy"], dose_series("cm1")[:40])
    assert (prov["cabin_co2_mmhg"] == "replayed").all() and (prov["dose_mgy"] == "replayed").all()
    assert (prov["resting_hr_bpm"] == "simulated").all()
    msgs = to_readings("cm1", df, provenance=prov)
    assert {m["provenance"] for m in msgs if m["signal"] == "cabin_co2_mmhg"} == {"replayed"}


def test_scenario_on_replay_switches_label_at_onset():
    sc = SCENARIOS["co2_creep"]
    df, prov = apply_replay(_sim("co2_creep"), "cm1", sc, "RR-5")
    on = sc.onset_day
    assert (prov["cabin_co2_mmhg"].iloc[:on] == "replayed").all()
    assert (prov["cabin_co2_mmhg"].iloc[on:] == "simulated").all()
    real = co2_series("RR-5")[:40]
    assert df["cabin_co2_mmhg"].iloc[-1] - real[-1] > 1.1  # +1.2 mmHg creep on top of the real day


def test_only_two_dosimeters_and_only_on_station():
    _, prov3 = apply_replay(_sim(), "cm3", SCENARIOS["normal"])
    assert (prov3["dose_mgy"] == "simulated").all()
    _, prov_mars = apply_replay(_sim(), "cm1", SCENARIOS["normal"], preset="mars_transit")
    assert (prov_mars["dose_mgy"] == "simulated").all()


def test_short_series_and_stitched():
    df, prov = apply_replay(_sim(days=50), "cm2", SCENARIOS["normal"], "RR-3")  # RR-3 has 45 days
    assert (prov["cabin_co2_mmhg"].iloc[45:] == "simulated").all()
    assert len(co2_series("stitched")) == 423
