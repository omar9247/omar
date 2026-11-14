"""Simulator vs the real datasets it was calibrated from (data/validate.py)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data"))
import validate  # noqa: E402

# Documented exceptions (contract/signals.yaml header):
# sleep levels are ISS in-flight values (Jones 2022), not BIDSleep's ground nights;
# lymphocyte spreads come from Coskun 2020, Inspiration4 samples are months apart with n=4.
SKIP_LEVEL = {"sleep_duration_h", "sleep_efficiency_pct"}
SKIP_SPREAD = {"lymphocytes_per_ul"}


@pytest.fixture(scope="module")
def v():
    return validate.validate(seed=3, n_sim=300)


def test_levels_and_spreads_match_real_data(v):
    for r in v.itertuples():
        assert r.coverage_95 >= 0.9, r.signal
        if r.signal not in SKIP_LEVEL:
            assert abs(r.sim_level / r.real_level - 1) < 0.15, r.signal
        if r.signal not in SKIP_SPREAD:
            assert abs(r.sim_within_sd / r.real_within_sd - 1) < 0.15, r.signal
            assert abs(r.sim_between_sd / r.real_between_sd - 1) < 0.15, r.signal


def test_links_match_real_data():
    l = validate.links(seed=3, n_sim=300)
    assert ((l.sim_r - l.real_r).abs() < 0.08).all(), l


def test_immune_scenario_covers_inspiration4_flight_change():
    f = validate.flight_change(seed=3)
    assert (f.coverage_95 == 1).all()
    assert ((f.sim_mean_pct / f.real_mean_pct - 1).abs() < 0.15).all()
