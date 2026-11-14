import asyncio
import threading
import time

import pytest
from fastapi.testclient import TestClient

from core import app as core_app
from generator import showcase


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_DB", str(tmp_path / "showcases.db"))
    monkeypatch.setenv("AURA_MQTT_PORT", "1")
    monkeypatch.setattr(core_app.model_client, "URL", "http://127.0.0.1:1")
    monkeypatch.setattr(core_app.model_client, "_down_until", 0.0)
    monkeypatch.setattr(core_app.showcase, "runner", showcase.ShowcaseRunner())
    with TestClient(core_app.app) as test_client:
        yield test_client


def run_fast(monkeypatch):
    """Keep the replay asynchronous while avoiding wall-clock days in API tests."""
    real_sleep = asyncio.sleep

    async def instant(_seconds):
        await real_sleep(0)

    monkeypatch.setattr(showcase.asyncio, "sleep", instant)


def wait_for_status(client, name, expected, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get("/showcases").json()
        card = next(c for c in response if c["name"] == name)
        if card["state"] == expected:
            return card
        time.sleep(0.01)
    raise AssertionError(f"{name} did not reach {expected}: {card}")


def test_catalog_has_four_honest_simulated_story_cards(client):
    response = client.get("/showcases")
    assert response.status_code == 200
    cards = response.json()
    assert [card["name"] for card in cards] == ["normal", "co2_creep", "sleep_debt", "sensor_loss"]
    for card in cards:
        assert {"title", "story", "expected_events", "watch_signals", "scenario", "source",
                "crew_id", "days", "onset_day", "provenance"} <= card.keys()
        assert card["provenance"] == card["label"] == "simulated"
        assert card["simulated"] is True
        assert card["crew_id"] == f"demo_{card['name']}"
        assert card["onset_day"] == 22  # generator.sim's zero-index 21 is Mission day 22
        assert all(isinstance(event, str) for event in card["expected_events"])


@pytest.mark.parametrize("query", ["?speed=0", "?speed=0.099", "?speed=60.1", "?speed=nan"])
def test_invalid_names_and_speed_bounds_are_rejected(client, query):
    assert client.post("/showcase/not_a_catalog_entry").status_code == 422
    assert client.post(f"/showcase/normal{query}").status_code == 422


def test_showcase_is_reserved_non_destructive_and_reports_provenance(client, monkeypatch):
    run_fast(monkeypatch)
    # Existing crew and game data must not be touched by a showcase reset.
    core_app.store.add_game_session(
        {"session_id": "existing-session", "crew_id": "cm1", "game_id": "reaction_test",
         "difficulty": "normal", "result": {"score": 1}},
        "2026-11-14T10:00:00+00:00",
    )
    assert client.post("/checkin", json={"crew_id": "cm1", "values": {"mood_score": 6}}).status_code == 200

    response = client.post("/showcase/co2_creep?speed=0.1")
    assert response.status_code == 200
    started = response.json()
    assert started["name"] == "co2_creep"
    assert started["crew_id"] == "demo_co2_creep"
    assert started["days"] == 40 and started["speed"] == 0.1
    assert started["simulated"] is True and started["label"] == "simulated"
    completed = wait_for_status(client, "co2_creep", "completed")

    assert "cm1" in client.get("/crew").json()
    assert core_app.store.count("game_session") == 1
    assert completed["completed_days"] == 40
    assert completed["progress"] == {"day": 40, "days": 40, "fraction": 1.0}
    readings = core_app.store.q("SELECT DISTINCT provenance FROM reading WHERE crew_id = ?", "demo_co2_creep")
    assert [row[0] for row in readings] == ["simulated"]
    status = client.get("/crew/demo_co2_creep/status").json()
    assert status["signals"]
    raw = core_app.store.q("SELECT DISTINCT provenance FROM reading WHERE crew_id = ?", "demo_co2_creep")
    assert [row[0] for row in raw] == ["simulated"]

    # Completion permits a safe rerun on the same reserved ID.
    rerun = client.post("/showcase/co2_creep?speed=0.1")
    assert rerun.status_code == 200 and rerun.json()["crew_id"] == "demo_co2_creep"
    wait_for_status(client, "co2_creep", "completed")


def test_running_showcase_rejects_duplicate_start(client, monkeypatch):
    real_sleep = asyncio.sleep
    started = threading.Event()
    release = threading.Event()
    first = True

    async def pause_once(_seconds):
        nonlocal first
        if first:
            first = False
            started.set()
            await asyncio.to_thread(release.wait)
        else:
            await real_sleep(0)

    monkeypatch.setattr(showcase.asyncio, "sleep", pause_once)
    assert client.post("/showcase/normal?speed=0.1").status_code == 200
    assert started.wait(2)
    duplicate = client.post("/showcase/normal?speed=0.1")
    assert duplicate.status_code == 409
    release.set()
    wait_for_status(client, "normal", "completed")


def test_reserved_id_collision_never_erases_existing_data(client):
    assert client.post("/checkin", json={"crew_id": "demo_co2_creep", "values": {"mood_score": 6}}).status_code == 200
    before = [dict(row) for row in core_app.store.q("SELECT * FROM reading WHERE crew_id = ?", "demo_co2_creep")]
    response = client.post("/showcase/co2_creep?speed=0.1")
    assert response.status_code == 409
    assert "nothing was reset" in response.json()["detail"]
    assert [dict(row) for row in core_app.store.q("SELECT * FROM reading WHERE crew_id = ?", "demo_co2_creep")] == before
    assert core_app.store.q("SELECT * FROM showcase_crew") == []


def test_showcase_ownership_survives_runner_restart_and_preserves_demo_games(client, monkeypatch):
    run_fast(monkeypatch)
    assert client.post("/showcase/normal?speed=0.1").status_code == 200
    wait_for_status(client, "normal", "completed")
    core_app.store.add_game_session({"session_id": "demo-game", "crew_id": "demo_normal", "game_id": "reaction_test"}, "2026-11-14T10:00:00+00:00")
    monkeypatch.setattr(core_app.showcase, "runner", showcase.ShowcaseRunner())
    assert client.post("/showcase/normal?speed=0.1").status_code == 200
    wait_for_status(client, "normal", "completed")
    assert core_app.store.q("SELECT session_id FROM game_session WHERE crew_id = ?", "demo_normal")[0][0] == "demo-game"
