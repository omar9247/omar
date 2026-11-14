import json
from uuid import uuid4

import pytest

from core import app as core_app
from core.game_sessions import GAME_IDS
from core.store import Store
from tests.test_core import client, post_day  # reuse the isolated DB/model-down fixture


def session(game_id="reaction_test", **changes):
    return {"session_id": str(uuid4()), "crew_id": "cm1", "game_id": game_id, "difficulty": "normal",
            "result": {"score": 120, "accuracy": 90.0, "mistakes": 1, "hits": 9, "avg_reaction_ms": 310.0,
                       "duration": 40.0, "stats": [["Hits", "9"]], "extra": {"trials": [280.0, 340.0]}}} | changes


@pytest.mark.parametrize("game_id", GAME_IDS)
def test_each_game_is_saved_without_writing_health_readings(client, game_id):
    body = session(game_id)
    result = client.post("/game-sessions", json=body)
    assert result.status_code == 200 and result.json()["saved"] == body["session_id"]
    history = client.get("/crew/cm1/game-sessions").json()
    assert len(history["sessions"]) == 1
    assert history["sessions"][0]["result"] == body["result"]
    assert history["sessions"][0]["provenance"] == "simulated"
    assert "not a validated health" in history["label"]
    assert client.get("/health").json()["readings"] == 0
    assert client.get("/crew/cm1/status").status_code == 404


def test_uuid_retry_is_idempotent_and_conflicting_data_is_not_overwritten(client):
    body = session()
    assert client.post("/game-sessions", json=body).json()["created"] is True
    assert client.post("/game-sessions", json=body).json()["created"] is False
    conflict = body | {"crew_id": "cm2"}
    assert client.post("/game-sessions", json=conflict).status_code == 409
    assert len(client.get("/crew/cm1/game-sessions").json()["sessions"]) == 1
    assert client.get("/crew/cm2/game-sessions").json()["sessions"] == []

def test_explicit_timestamp_is_immutable_and_normalized(client):
    body = session(ts="2026-11-14T12:00:00+02:00")
    assert client.post("/game-sessions", json=body).json()["created"]
    assert client.post("/game-sessions", json=body | {"ts": "2026-11-14T10:00:00Z"}).json()["created"] is False
    assert client.post("/game-sessions", json=body | {"ts": "2026-11-15T10:00:00Z"}).status_code == 409

@pytest.mark.parametrize("text", ["{broken", "null", "[]", "NaN"])
def test_bad_json_or_root_is_json_safe(client, text):
    response = client.post("/game-sessions", content=text, headers={"Content-Type": "application/json"})
    assert response.status_code == 422 and response.json()["detail"]


@pytest.mark.parametrize("change", [{"game_id": "nope"}, {"difficulty": "unknown"}, {"crew_id": "cm1/other"},
                                    {"session_id": "not-a-uuid"}, {"ts": "2026-11-14T10:00:00"},
                                    {"provenance": "real"}])
def test_bad_session_metadata_is_rejected(client, change):
    assert client.post("/game-sessions", json=session(**change)).status_code == 422


@pytest.mark.parametrize("field,value", [("accuracy", -1), ("accuracy", 101), ("mistakes", -1),
                                          ("avg_reaction_ms", float("nan")), ("duration", float("inf")),
                                          ("extra", {"rt": float("nan")}), ("extra", {"huge": "x" * 65536})])
def test_bad_values_return_json_safe_422(client, field, value):
    body = session()
    body["result"][field] = value
    # Raw JSON intentionally exercises NaN/inf; the error reply must not echo it into JSON and crash.
    r = client.post("/game-sessions", content=json.dumps(body), headers={"Content-Type": "application/json"})
    assert r.status_code == 422 and r.json()["detail"]
    assert core_app.store.count("game_session") == 0


def test_game_timestamp_uses_current_mission_day_and_health_state_is_unchanged(client):
    post_day(client, 16, cabin_co2_mmhg=2.2)
    before = client.get("/crew/cm1/status").json()
    assert client.post("/game-sessions", json=session()).status_code == 200
    saved = client.get("/crew/cm1/game-sessions").json()["sessions"][0]
    assert saved["ts"] == before["ts"]
    assert client.get("/crew/cm1/status").json() == before
    assert client.get("/crew/cm1/game-sessions?limit=0").status_code == 422


def test_additive_store_upgrade_and_game_history_survive_restart_and_replay_reset(tmp_path):
    path = str(tmp_path / "core.db")
    store = Store(path)
    body = session()
    store.add_game_session(body, "2026-11-14T10:00:00+00:00")
    store.db.close()
    restored = Store(path)
    assert restored.game_sessions("cm1")[0]["session_id"] == body["session_id"]
    restored.clear("cm1", include_games=False)
    assert restored.count("game_session") == 1
    restored.clear("cm1")
    assert restored.count("game_session") == 0
    restored.db.close()


def test_game_route_and_both_runtime_archives_are_served(client):
    assert client.get("/lunar-arcade-hub/").status_code == 200
    for name in ("aura-bridge.js", "lunar_arcade_hub.tar.gz", "lunar_arcade_hub.apk"):
        assert client.get("/lunar-arcade-hub/" + name).status_code == 200
    assert "Reaction test · 90 seconds" in client.get("/").text
