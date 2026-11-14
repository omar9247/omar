from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from contract.schema import load_signals, load_thresholds
from core import app as core_app
from core.domain import band, match_patterns

T0 = datetime(2026, 11, 14, 10, tzinfo=timezone.utc)
BASE = 100.0  # baseline mean used for the relative rules


def value_for(rule, t, eps):
    """A value sitting eps past threshold t on the bad side."""
    sign = 1 if rule["direction"] == "above" else -1
    if rule["kind"] == "abs":
        return t + sign * eps
    return BASE + sign * (t + eps) * (BASE / 100 if rule["kind"] == "pct" else 1)


RULES = [(n, r) for n, rs in load_thresholds()["thresholds"].items() for r in (rs if isinstance(rs, list) else [rs])]


@pytest.mark.parametrize("name,rule", RULES)
def test_every_threshold_boundary(name, rule):  # NFR-5
    assert rule["basis"] in ("published", "proposed") and rule["citation"]  # NFR-13
    assert name in {s["name"] for s in load_signals()}
    for level in ("amber", "red"):
        if (t := rule.get(level)) is None:
            continue
        below = "green" if level == "amber" or "amber" not in rule else "amber"
        assert band(rule, value_for(rule, t, -0.01), BASE) == below
        assert band(rule, value_for(rule, t, 0.01), BASE) == level


def test_relative_rule_needs_baseline():
    assert band(load_thresholds()["thresholds"]["rmssd_ms"], 10.0, None) is None


def test_rule_list_takes_worst():
    lymph = load_thresholds()["thresholds"]["lymphocytes_per_ul"]
    assert band(lymph, 1100, 1300) == "green"
    assert band(lymph, 900, 1300) == "red"      # under 1000 even though only 31% below baseline
    assert band(lymph, 900, None) == "red"      # absolute rule works before a baseline exists
    assert band(lymph, 1500, 2600) == "red"     # 42% below baseline


PATTERNS = load_thresholds()["patterns"]


@pytest.mark.parametrize("p", PATTERNS, ids=lambda p: p["id"])
def test_every_pattern_boundary(p):  # NFR-5, NFR-13
    names = {s["name"] for s in load_signals()}
    assert set(p["signals"]) <= names and len(p["signals"]) >= 2
    assert p["basis"] in ("published", "proposed") and p["citation"] and p["response_system"] and p["response_crew"]

    need = p.get("min_band", {})
    days = p.get("days", 1)

    def fired(yesterday=None, **override):
        sig = {s: {"band": override.get(s, need.get(s, "amber")), "value": 1.0} for s in p["signals"]}
        return match_patterns(sig, [p], [yesterday or sig] * (days - 1))

    base = "red" if need else "amber"
    assert [a["level"] for a in fired()] == [base]
    assert [a["level"] for a in fired(**{p["signals"][0]: "red"})] == ["red"]
    for s in p["signals"]:
        for other in ("green", "stale", "unknown") + (("amber",) if need.get(s) == "red" else ()):
            assert fired(**{s: other}) == []
    if days > 1:  # must also have matched yesterday
        assert match_patterns({s: {"band": "red"} for s in p["signals"]}, [p], []) == []
        assert fired(yesterday={s: {"band": "green"} for s in p["signals"]}) == []


def test_only_published_reds_become_alerts():
    from core.domain import signal_alerts
    cfg = load_thresholds()

    def alerts(name, value, base):
        return [a["signal"] for a in signal_alerts({name: {"band": band(cfg["thresholds"][name], value, base),
                                                           "value": value, "baseline_mean": base}}, cfg)]
    assert alerts("lymphocytes_per_ul", 900, 1300) == ["lymphocytes_per_ul"]  # < 1000: published
    assert alerts("lymphocytes_per_ul", 1500, 2600) == []                     # -42%: proposed rule only
    assert alerts("cabin_co2_mmhg", 3.1, None) == ["cabin_co2_mmhg"]
    assert alerts("rmssd_ms", 30, 60) == []                                    # -50%, proposed


def test_broken_pattern_does_not_stop_others():  # NFR-2
    ok = {"id": "ok", "signals": ["a"]}
    assert [a["id"] for a in match_patterns({"a": {"band": "red"}}, [{"id": "bad", "signals": ["nope"]}, ok])] == ["ok"]


def replay(scenario, seed):
    """Run a simulated scenario through the store and status, day by day; return the patterns raised, in order."""
    import itertools

    import numpy as np

    from contract.schema import Reading
    from core.store import Store
    from generator.sim import SCENARIOS, make_profile, simulate, to_readings

    core_app.store = Store(":memory:")
    rng = np.random.default_rng(seed)
    sc = SCENARIOS[scenario]
    raised = []
    for _, msgs in itertools.groupby(to_readings("cm1", simulate(make_profile(rng), sc.days, rng, sc)),
                                     key=lambda m: m["ts"]):
        for m in msgs:
            core_app.store.add(Reading(**m))
        raised += [a["id"] for a in core_app.crew_status("cm1")["alerts"] if a["id"] and a["id"] not in raised]
    return raised


DEMO_SEED = 12  # an astronaut whose normal run raises nothing and each scenario raises only its own pattern


@pytest.mark.parametrize("scenario,expected", [("normal", []), ("co2_creep", ["co2_performance"]),
                                               ("sleep_debt", ["sleep_loss_impairment"]),
                                               ("deconditioning", ["cardio_deconditioning"])])
def test_demo_scenarios_raise_their_pattern(scenario, expected):  # NFR-5, plan 6.2: same alerts every run
    assert replay(scenario, DEMO_SEED) == expected


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("AURA_MQTT_PORT", "1")  # nothing listens there; the service must start anyway
    from core import model_client
    monkeypatch.setattr(model_client, "URL", "http://127.0.0.1:1")  # model down, whatever runs on :8001
    monkeypatch.setattr(model_client, "_down_until", 0.0)
    with TestClient(core_app.app) as c:
        yield c


def post_day(client, day, **values):
    return client.post("/checkin", json={"crew_id": "cm1", "ts": (T0 + timedelta(days=day)).isoformat(),
                                         "values": values}).json()


def test_baseline_then_bands_and_stale(client):
    assert client.get("/crew/cm1/status").status_code == 404
    with client.websocket_connect("/ws") as ws:
        for d in range(14):
            post_day(client, d, resting_hr_bpm=60 + d % 2, cabin_co2_mmhg=2.0, sleep_duration_h=7.5)
            assert ws.receive_json()["baseline_ready"] is False
        post_day(client, 14, resting_hr_bpm=72, cabin_co2_mmhg=3.2, sleep_duration_h=7.5)
        s = ws.receive_json()
    assert s == client.get("/crew/cm1/status").json()
    assert s["baseline_ready"] and s["disclaimer"]
    assert s["signals"]["resting_hr_bpm"]["band"] == "amber"  # 72 vs baseline 60.5
    assert s["signals"]["resting_hr_bpm"]["provenance"] == "simulated"
    assert s["systems"] == {"cardiovascular": "amber", "neurocognitive": "green", "environment": "red",
                            "bone_muscle": "unknown", "radiation": "green", "immune": "unknown"}
    # pulse sensor stops: two days later heart rate is stale, never green (FR-8)
    post_day(client, 16, cabin_co2_mmhg=2.0)
    s = client.get("/crew/cm1/status").json()
    assert s["signals"]["resting_hr_bpm"]["band"] == "stale" and s["systems"]["cardiovascular"] == "stale"
    assert client.delete("/crew/cm1").status_code == 200 and client.get("/crew").json() == []


def test_bad_messages_are_rejected_without_stopping(client):  # FR-2, NFR-2
    good = '{"crew_id":"cm1","ts":"2026-11-14T10:00:00Z","signal":"cabin_co2_mmhg","value":2.7,' \
           '"source":"wokwi","provenance":"simulated"}'
    for bad in (b"not json", good.replace("cabin_co2_mmhg", "nope"), good.replace("2.7", '"x"'),
                good.replace("simulated", "made-up"), good.replace("Z", "")):  # last: ts without a time zone
        assert core_app.ingest(bad, "aura/cm1/cabin") is None
    assert post_day(client, 0, nope=1.0, mood_score=6)["rejected"] == ["nope"]
    assert core_app.ingest(good, "aura/cm1/cabin") is not None
    core_app.ingest(good, "aura/cm1/cabin")  # QoS 1 duplicate is stored once
    assert client.get("/health").json() == {"status": "ok", "mqtt_connected": False, "readings": 2, "rejects": 6}


def test_every_rule_has_a_response():  # FR-6
    cfg = load_thresholds()
    for name, rs in cfg["thresholds"].items():
        r = cfg["responses"][name]
        assert r["crew"] and all(r[lvl] for rule in (rs if isinstance(rs, list) else [rs])
                                 for lvl in ("amber", "red") if lvl in rule)


def test_cumulative_dose_boundaries():
    from core.domain import cumulative_dose
    cfg, preset, limits = load_thresholds(), {"quality_factor": 2.0}, {"career_effective_dose_msv": 600}
    assert cumulative_dose(239.9, preset, limits, cfg)["band"] == "green"   # 479.8 mSv = 79.97%
    assert cumulative_dose(240.0, preset, limits, cfg)["band"] == "amber"   # 80%
    assert cumulative_dose(300.0, preset, limits, cfg)["band"] == "amber"   # 100%, not over
    d = cumulative_dose(300.1, preset, limits, cfg)
    assert d["band"] == "red" and d["response"]["system"]


def test_immune_risk():
    from core.domain import immune_risk
    cfg = load_thresholds()
    sig = {"nk_activity_pct": {"z": -3.0}, "rmssd_ms": {"z": 1.0}, "dose_mgy": {"z": 3.0}}
    r = immune_risk(sig, cfg)
    assert r["score"] == round(100 * (3 + 0 + 3) / 3 / 3, 1)  # rmssd above baseline counts as 0
    assert r["inputs"]["lymphocytes_per_ul"] is None and "research concept" in r["label"]
    assert immune_risk({}, cfg)["score"] is None


def test_checkin_scoring():
    from core.domain import score_checkin
    cfg = load_thresholds()
    assert score_checkin([354.9, 355, 400, 200], [6, 8], cfg) == {"reaction_lapses_pct": 50.0, "mood_score": 7}
    with pytest.raises(ValueError):
        score_checkin(None, [11], cfg)


def test_model_window_matches_model_service():
    from contract.schema import model_signals
    from core.domain import model_window
    names = model_signals()
    snaps = [{"resting_hr_bpm": {"value": 70.0}}, {}, {}]  # today, yesterday, two days ago
    w = model_window(snaps, {"resting_hr_bpm": (60.0, 5.0)}, names)
    assert w["resting_hr_bpm"] == [0.0, 0.0, 2.0] and set(w) == set(names)
    from pathlib import Path
    if not Path("artifacts/model_2d.pt").exists():
        pytest.skip("no trained model")
    from model.service import ScoreRequest, score
    response = score(ScoreRequest(crew_id="cm1", window=w))
    assert response.detector in {"2d", "ewma"} and len(response.model_version) == 12


def test_model_scaling_matches_dataset_for_full_missing_constant_and_partial_signals():
    import numpy as np
    from contract.schema import model_signals
    from core.domain import model_baselines, model_window
    from generator.sim import make_profile, simulate
    from model.dataset import baseline_stats, normalise

    names = model_signals()
    rng = np.random.default_rng(7)
    df = simulate(make_profile(rng), 20, rng)
    expected = normalise(df)
    stats = model_baselines({n: df[n].tolist() for n in df})
    snaps = [{n: {"value": float(df.iloc[i][n])} for n in names} for i in (19, 18, 17)]
    live = model_window(snaps, stats, names)
    for n in names:
        assert live[n] == pytest.approx(expected[n].iloc[17:20].round(4).tolist())

    partial = df.copy()
    partial.loc[:4, "sleep_duration_h"] = np.nan
    partial.loc[:13, "cabin_co2_mmhg"] = 2.0
    partial_raw = {n: partial[n].iloc[:14].dropna().tolist() for n in partial}
    partial_expected_centre, partial_expected_spread = baseline_stats(partial[names])
    partial_stats = model_baselines(partial_raw)
    for n in names:
        if not np.isnan(partial_expected_centre[n]):
            assert partial_stats[n] == pytest.approx((partial_expected_centre[n], partial_expected_spread[n]))
    assert np.all(partial_expected_spread["cabin_co2_mmhg"] > 0)  # constant baseline uses population spread
    assert np.all(partial_expected_spread["sleep_duration_h"] > 0)  # missing samples still blend by count
    assert partial_expected_centre["sleep_duration_h"] == pytest.approx(partial["sleep_duration_h"].iloc[:14].mean())
    assert normalise(partial)["sleep_duration_h"].iloc[:5].eq(0).all()


def test_model_window_caps_and_anomaly_waits_for_fourteen_days():
    from contract.schema import Reading, model_signals
    from core.domain import model_window
    from core import app as core_app
    from core.store import Store

    names = model_signals()
    clipped = model_window([{"resting_hr_bpm": {"value": 1000.0}}, {}],
                           {"resting_hr_bpm": (0.0, 1.0)}, names)
    assert clipped["resting_hr_bpm"] == [0.0, 8.0]

    core_app.store = Store(":memory:")
    for day in range(13):
        core_app.store.add(Reading(crew_id="cm1", ts=T0 + timedelta(days=day), signal="resting_hr_bpm",
                                   value=60.0, source="app", provenance="simulated"))
    assert core_app.anomaly("cm1", {}, T0 + timedelta(days=12)) == {
        "available": False, "reason": "baseline not ready"
    }


def test_model_sees_a_dropped_sensor_as_baseline(client, monkeypatch):
    from core import model_client
    sent = {}
    monkeypatch.setattr(model_client, "score", lambda crew_id, window: sent.update(window) or {"available": False})
    for d in range(17):
        post_day(client, d, mood_score=6 + d % 2, **({"resting_hr_bpm": 60 + d % 2} if d < 15 else {}))
    client.get("/crew/cm1/status")
    assert sent["resting_hr_bpm"][-2:] == [0.0, 0.0]  # no reading on days 15-16: baseline, not day 14 repeated
    assert sent["resting_hr_bpm"][-3] != 0.0


def test_api_mission_trend_checkin_and_model_down(client):
    with client.websocket_connect("/ws") as ws:
        for d in range(16):
            co2 = 2.0 if d < 14 else 3.5
            post_day(client, d, cabin_co2_mmhg=co2, dose_mgy=0.3)
            ws.receive_json()
        s = client.get("/crew/cm1/status").json()
        assert s["anomaly"]["available"] is False  # no model service in tests: rules carry on (NFR-4)
        assert s["signals"]["cabin_co2_mmhg"]["response"]["system"].startswith("Investigate")
        assert s["signals"]["cumulative_dose_msv"]["value"] == round(16 * 0.3 * 1.85, 2)
        assert s["mission"]["name"] == "station"
        assert client.put("/mission", json={"preset": "nowhere"}).status_code == 422
        assert client.put("/mission", json={"preset": "mars_transit"}).json()["alert_wording"].startswith("Follow")
        assert ws.receive_json()["mission"]["name"] == "mars_transit"  # pushed to the app
    t = client.get("/crew/cm1/signal/cabin_co2_mmhg?days=3").json()
    assert [p["value"] for p in t["points"]] == [2.0, 2.0, 3.5, 3.5] and t["baseline_mean"] == 2.0
    assert client.get("/crew/cm1/signal/nope").status_code == 404
    r = client.post("/checkin", json={"crew_id": "cm1", "ts": (T0 + timedelta(days=16)).isoformat(),
                                      "reaction_times_ms": [300, 400], "mood_answers": [7, 5]}).json()
    assert sorted(r["accepted"]) == ["mood_score", "reaction_lapses_pct"]
    s = client.get("/crew/cm1/status").json()
    assert s["signals"]["reaction_lapses_pct"]["value"] == 50 and s["signals"]["mood_score"]["value"] == 6
    assert client.post("/checkin", json={"crew_id": "cm1", "ts": T0.isoformat(), "mood_answers": [12]}).status_code == 422
    assert client.post("/checkin", json={"crew_id": "cm1", "ts": "2026-11-30T10:00:00", "mood_answers": [2]}).status_code == 422
    client.post("/checkin", json={"crew_id": "cm1", "mood_answers": [2]})  # no ts: lands on the crew's current day
    m = client.get("/crew/cm1/status").json()["signals"]["mood_score"]
    assert m["value"] == 2 and m["ts"] == (T0 + timedelta(days=16)).isoformat()


def test_labs_wait_for_their_longer_baseline(client):
    for d in range(29):
        post_day(client, d, resting_hr_bpm=60 + d % 2, **({"nk_activity_pct": 100 + d % 3} if d % 7 == 0 else {}))
        s = client.get("/crew/cm1/status").json()["signals"]
        if d == 14:
            assert s["resting_hr_bpm"]["baseline_mean"] is not None and s["nk_activity_pct"]["baseline_mean"] is None
    assert s["nk_activity_pct"]["baseline_mean"] == 100.75  # 100, 101, 102, 100 on days 0, 7, 14, 21


def test_alerts_persist_until_acknowledged_and_reach_the_ground_late(client, monkeypatch):  # FR-6, 16, 17
    client.put("/mission", json={"preset": "mars_transit"})  # 750 s one-way delay
    t0 = core_app.time.time()
    for d in range(14):
        post_day(client, d, resting_hr_bpm=60 + d % 2, exercise_completion_pct=98)
    post_day(client, 14, resting_hr_bpm=75, exercise_completion_pct=80)  # cardio_deconditioning, both amber
    post_day(client, 15, resting_hr_bpm=75, exercise_completion_pct=80)  # same episode: no second alert
    [a] = client.get("/crew/cm1/status").json()["alerts"]
    assert a["id"] == "cardio_deconditioning" and a["active"] and a["level"] == "amber"
    assert a["started_ts"].startswith("2026-11-28") and a["action"].startswith("Follow onboard protocol")
    post_day(client, 16, resting_hr_bpm=60, exercise_completion_pct=98)  # pattern stops: stays until acknowledged
    [a] = client.get("/crew/cm1/status").json()["alerts"]
    assert not a["active"] and a["acknowledged_at"] is None
    assert client.get("/crew/overview").json()[0]["alerts"][0]["alert_id"] == a["alert_id"]
    assert client.post(f"/alerts/{a['alert_id']}/ack").status_code == 200
    assert client.get("/crew/cm1/status").json()["alerts"] == []
    assert client.post("/alerts/999/ack").status_code == 404

    r = client.get("/ground/reports").json()
    assert r["released"] == [] and 740 < r["pending"][0]["release_in_s"] <= 750
    monkeypatch.setattr(core_app.time, "time", lambda: t0 + 751)
    [rep] = client.get("/ground/reports").json()["released"]
    assert rep["alert"] == "Cardiovascular deconditioning" and rep["mission"] == "mars_transit" and rep["disclaimer"]


def test_overlapping_status_cannot_reopen_a_closed_alert(client, monkeypatch):
    import threading

    from contract.schema import Reading
    from core import model_client
    for d in range(14):
        post_day(client, d, resting_hr_bpm=60 + d % 2, exercise_completion_pct=98)
    post_day(client, 14, resting_hr_bpm=75, exercise_completion_pct=80)  # cardio_deconditioning opens, both amber
    stuck, release, calls = threading.Event(), threading.Event(), []

    def slow_model(*_):  # the first status call hangs in the model, the next ones don't
        calls.append(1)
        if len(calls) == 1:
            stuck.set()
            release.wait(5)
        return {"available": False}

    monkeypatch.setattr(model_client, "score", slow_model)
    old = threading.Thread(target=core_app.crew_status, args=("cm1",))
    old.start()
    assert stuck.wait(5)  # `old` has read the data while the pattern still matched
    for sig, v in (("resting_hr_bpm", 60), ("exercise_completion_pct", 98)):  # day 15: pattern stops
        core_app.store.add(Reading(crew_id="cm1", ts=T0 + timedelta(days=15), signal=sig, value=v,
                                   source="app", provenance="simulated"))
    new = threading.Thread(target=core_app.crew_status, args=("cm1",))
    new.start()
    new.join(0.5)  # without the lock, `new` closes the alert now and `old` then reopens it
    release.set()
    old.join(5)
    new.join(5)
    assert core_app.store.count("alert") == 1 and core_app.store.count("report") == 1


def test_red_signal_alert_and_plan_tables(client):  # plan 3.5 data decomposition
    for d in range(14):
        post_day(client, d, cabin_co2_mmhg=2.0 + d % 2 / 10)
    s = client.get("/crew/cm1/status").json()
    assert s["alerts"] == [] and core_app.store.baselines("cm1") == {}  # window not over yet
    post_day(client, 14, cabin_co2_mmhg=3.5)  # red: single-signal alert; amber would not be one
    assert core_app.store.baselines("cm1")["cabin_co2_mmhg"][0] == pytest.approx(2.05)  # days 0-13
    [a] = client.get("/crew/cm1/status").json()["alerts"]
    assert a["id"] is None and a["signal"] == "cabin_co2_mmhg" and a["response"]["system"].startswith("Investigate")
    post_day(client, 15, cabin_co2_mmhg=2.8)  # amber: episode ends, alert waits for acknowledgement
    [a] = client.get("/crew/cm1/status").json()["alerts"]
    assert not a["active"] and a["fired"]["cabin_co2_mmhg"]["value"] == 3.5
    assert core_app.store.baselines("cm1")["cabin_co2_mmhg"][0] == pytest.approx(2.05)  # frozen after the window
    assert core_app.store.mission()["preset"] == "station" and core_app.store.crews() == ["cm1"]


def test_web_app_may_call_the_api(client):  # the web app runs on another origin
    r = client.options("/checkin", headers={"Origin": "http://localhost:5000", "Access-Control-Request-Method": "POST",
                                            "Access-Control-Request-Headers": "content-type"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "*"


def test_demo_scenario_replays_into_the_core_and_page_is_served(client):  # FR-9
    import time as _time
    assert client.post("/scenario/nope").status_code == 422
    assert client.post("/scenario/co2_creep?speed=0").json()["days"] == 40
    deadline = _time.time() + 20
    while _time.time() < deadline:
        s = client.get("/crew/cm1/status")
        if s.status_code == 200 and s.json()["ts"].startswith("2026-12-23"):  # day 39 of 40
            break
        _time.sleep(0.2)
    assert {a["id"] for a in s.json()["alerts"] if a["id"]} == {"co2_performance"}  # demo seed 12
    assert "AURA" in client.get("/").text and client.get("/static/app.js").status_code == 200
    assert set(client.get("/mission").json()["presets"]["mars_transit"]) >= {"alert_wording", "one_way_delay_s"}


def test_server_can_serve_websockets():
    # TestClient fakes /ws, but uvicorn answers it with 404 unless a WebSocket library is installed
    import importlib.util
    assert importlib.util.find_spec("websockets") or importlib.util.find_spec("wsproto")


def test_timeline_days_and_episodes(client):  # the console's lanes: bands per day, alert episodes by day
    for d in range(14):
        post_day(client, d, cabin_co2_mmhg=2.0, resting_hr_bpm=60 + d % 2)
    post_day(client, 14, cabin_co2_mmhg=3.5, resting_hr_bpm=72)
    post_day(client, 15, cabin_co2_mmhg=2.0, resting_hr_bpm=60)
    t = client.get("/crew/cm1/timeline").json()
    assert [d["day"] for d in t["days"]] == list(range(1, 17))
    assert t["days"][0]["systems"]["environment"] == "green"
    assert t["days"][5]["systems"]["cardiovascular"] == "unknown"  # relative rule had no baseline yet: no band
    assert t["days"][14]["systems"] == t["days"][14]["systems"] | {"environment": "red", "cardiovascular": "amber"}
    [e] = t["episodes"]
    assert (e["signal"], e["start_day"], e["end_day"], e["active"]) == ("cabin_co2_mmhg", 15, 15, False)
    assert e["systems"] == ["environment"]
    assert client.get("/crew/nobody/timeline").status_code == 404
