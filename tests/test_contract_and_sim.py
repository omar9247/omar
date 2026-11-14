import pandas as pd
import numpy as np

from contract.schema import Reading, load_signals, model_signals
from generator.sim import BASELINE_DAYS, SCENARIOS, make_profile, simulate, to_readings
from model.dataset import normalise, windows


def _run(name, days=40):
    rng = np.random.default_rng(0)
    return simulate(make_profile(rng), days, rng, SCENARIOS[name])


def test_readings_match_contract():
    msgs = to_readings("cm1", _run("normal", 3))
    daily = [s for s in load_signals() if "interval_days" not in s]
    weekly = [s for s in load_signals() if "interval_days" in s]
    assert len(msgs) == 3 * len(daily) + len(weekly)  # weekly labs only on day 0
    r = Reading(**msgs[0])
    assert r.topic().startswith("aura/cm1/")


def test_sleep_debt_reaches_target():
    df = _run("sleep_debt")
    base = df["sleep_duration_h"].iloc[:BASELINE_DAYS].mean()
    assert df["sleep_duration_h"].iloc[-10:].mean() < base - 1.8  # ~2.4 h below own baseline


def test_sensor_loss_drops_readings():
    df = _run("sensor_loss")
    on = SCENARIOS["sensor_loss"].onset_day
    assert df["resting_hr_bpm"].iloc[on:].isna().all()
    assert all(m["signal"] != "rmssd_ms" for m in to_readings("cm1", df.iloc[on:]))


def test_window_shape():
    for n in (2, 7, 14):
        w = windows(normalise(_run("normal")), n)
        assert w.shape == (40 - BASELINE_DAYS, n, len(model_signals()))
        assert np.isfinite(w).all()


def test_rmssd_never_negative():
    rng = np.random.default_rng(0)
    x = np.concatenate([simulate(make_profile(rng), 60, rng)["rmssd_ms"].to_numpy() for _ in range(300)])
    assert (x > 0).all()


def test_sleep_debt_lapses_follow_van_dongen():
    df = _run("sleep_debt", 60)
    on = SCENARIOS["sleep_debt"].onset_day
    base = df["reaction_lapses_pct"].iloc[:BASELINE_DAYS].mean()
    day14 = df["reaction_lapses_pct"].iloc[on + 11: on + 16].mean()  # around day 14 of restriction
    assert 8 < day14 - base < 20                                      # ~ +14 points
    assert df["reaction_lapses_pct"].iloc[-5:].mean() > day14         # keeps rising after day 14


def test_dose_follows_preset_and_differs_per_astronaut():
    from contract.schema import load_presets
    for preset, p in load_presets().items():
        rng = np.random.default_rng(1)
        levels = [simulate(make_profile(rng, preset), 60, rng)["dose_mgy"].mean() for _ in range(200)]
        assert abs(np.mean(levels) - p["dose_mgy_day"]) / p["dose_mgy_day"] < 0.03, preset
        assert np.std(levels) > 0.05 * p["dose_mgy_day"], preset   # each astronaut has own level
    rng = np.random.default_rng(2)
    assert (simulate(make_profile(rng, "mars_transit"), 60, rng)["dose_mgy"] > 0).all()


def test_labs_weekly_and_plausible():
    df = _run("normal", 60)
    lab = df["lymphocytes_per_ul"]
    assert lab.notna().sum() == 9 and lab.dropna().index.tolist()[:2] == [0, 7]
    assert (lab.dropna() > 0).all() and (df["il6_pg_ml"].dropna() > 0).all()
    assert set(df["viral_pcr_positive"].dropna().unique()) <= {0.0, 1.0}
    assert all(s not in model_signals() for s in ["lymphocytes_per_ul", "il6_pg_ml"])


def test_immune_scenario_sizes():
    sc = SCENARIOS["immune"]
    pre, post = [], []
    shed_pre, shed_post = [], []
    rng = np.random.default_rng(3)
    for _ in range(300):
        df = simulate(make_profile(rng), sc.days, rng, sc)
        lab = df["lymphocytes_per_ul"].dropna()
        pre.append(lab[lab.index < sc.onset_day].mean())
        post.append(lab[lab.index >= sc.onset_day + 60].mean())      # full effect
        v = df["viral_pcr_positive"].dropna()
        shed_pre.append(v[v.index < sc.onset_day].mean())
        shed_post.append(v[v.index >= sc.onset_day + 60].mean())
    assert abs(np.mean(post) / np.mean(pre) - 0.73) < 0.05          # lymphocytes -27%
    assert np.mean(shed_pre) < 0.08 and abs(np.mean(shed_post) - 0.23) < 0.06


def test_solar_event_is_one_day_spike():
    sc = SCENARIOS["solar_event"]
    rng = np.random.default_rng(5)
    ratios = []
    for _ in range(200):
        d = simulate(make_profile(rng), sc.days, rng, sc)["dose_mgy"]
        normal = d.drop(index=sc.onset_day).mean()
        ratios.append(d[sc.onset_day] / normal)
        assert abs(d[sc.onset_day + 1] / normal - 1) < 0.25                # back to normal next day
    assert abs(np.mean(ratios) - (1 + 0.146 / 0.285)) < 0.05               # +51% on the event day


def test_scale_limits_hold():
    rng = np.random.default_rng(9)
    df = pd.concat([simulate(make_profile(rng), 60, rng, SCENARIOS["sleep_debt"]) for _ in range(200)])
    assert df["sleep_efficiency_pct"].max() <= 100 and df["reaction_lapses_pct"].min() >= 0
    assert df["mood_score"].between(0, 10).all()


def test_log_signals_keep_stated_average():
    from contract.schema import load_signals
    rng = np.random.default_rng(4)
    df = pd.concat([simulate(make_profile(rng), 60, rng) for _ in range(1500)])
    for s in load_signals():
        if s.get("log"):
            # sampling error of the average grows with the person-to-person spread (3 standard errors)
            tol = max(0.02, 3 * s["person_sd"] / s["sim_mean"] / np.sqrt(1500))
            assert abs(df[s["name"]].mean() / s["sim_mean"] - 1) < tol, s["name"]
            assert (df[s["name"]].dropna() > 0).all(), s["name"]


def test_spreads_match_and_caps_dont_pile_up():
    from contract.schema import load_signals
    rng = np.random.default_rng(6)
    profiles = [make_profile(rng) for _ in range(4000)]
    for s in load_signals():
        if s.get("log") or "log_from" in s:            # person-to-person spread matches what's stated
            got = np.std([p[s["name"]] for p in profiles])
            assert s["person_sd"] == 0 or abs(got / s["person_sd"] - 1) < 0.15, s["name"]
    df = pd.concat([simulate(p, 60, rng) for p in profiles[:1500]])
    for name in ["sleep_efficiency_pct", "exercise_completion_pct"]:
        assert (df[name] >= 100).mean() < 0.001, name                     # no pile-up at the cap
    assert abs(df["sleep_efficiency_pct"].mean() - 91.8) < 0.5
    assert abs(df["exercise_completion_pct"].mean() - 98) < 0.5
    assert (df["mood_score"].isin([0, 10])).mean() < 0.001
    assert abs(df["mood_score"].mean() - 6.2) < 0.06                 # logit: never on either end
    base = pd.concat([simulate(p, BASELINE_DAYS, rng)["mood_score"] for p in profiles[:1500]], axis=1)
    assert (base.std() > 0).all()                                          # no flat mood baselines


def test_scenarios_never_produce_impossible_values():
    """log signals stay > 0 and chances stay 0..1 under every scenario, incl. large immune responses."""
    sig = load_signals()
    rng = np.random.default_rng(7)
    for sc in SCENARIOS.values():
        for _ in range(200):
            d = simulate(make_profile(rng), sc.days, rng, sc)
            for s in sig:
                col = d[s["name"]].dropna()
                if s.get("log"):
                    assert (col > 0).all(), (sc.name, s["name"])
                if "p" in s:
                    assert col.isin([0.0, 1.0]).all(), (sc.name, s["name"])


def test_mood_follows_last_nights_sleep():
    """Within-person effect of last night's sleep on mood reproduces Jones 2022 Table 1 (vs 7-8 h),
    and the average mood stays at its stated level."""
    rng = np.random.default_rng(11)
    d = pd.concat([simulate(make_profile(rng), 60, rng).assign(p=i) for i in range(400)])
    bins = pd.get_dummies(pd.cut(d.sleep_duration_h, [0, 4, 5, 6, 7, 8, 9, 24]), dtype=float)
    X = bins.drop(columns=bins.columns[4])  # 7-8 h is the reference, as in the paper
    within = lambda v: v - v.groupby(d.p).transform("mean")  # person fixed effects
    beta = np.linalg.lstsq(within(X).to_numpy(), within(d.mood_score).to_numpy(), rcond=None)[0]
    assert np.allclose(beta, [-0.77, -0.38, -0.26, -0.05, 0.11, 0.05], atol=0.06), beta.round(2)
    # same astronauts without the link: the average mood must not move
    mood = {x["name"]: x for x in load_signals()}["mood_score"]
    f = mood.pop("follows")
    try:
        rng = np.random.default_rng(11)
        plain = pd.concat([simulate(make_profile(rng), 60, rng) for _ in range(400)])
    finally:
        mood["follows"] = f
    assert abs(d.mood_score.mean() - plain.mood_score.mean()) < 0.02
