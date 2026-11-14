import pytest
from fastapi.testclient import TestClient

from core import app as core_app
from core import public_demo
from generator import showcase


class FakeRunner:
    def __init__(self):
        self.calls = []

    def cards(self):
        return [{"name": "normal", "state": "ready"}]

    async def start(self, name, speed, **callbacks):
        self.calls.append((name, speed, callbacks))
        return {"name": name, "speed": speed, "simulated": True}

    async def shutdown(self):
        pass


@pytest.fixture
def public_client(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_PUBLIC_DEMO", "1")
    monkeypatch.delenv("AURA_ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("AURA_DB", str(tmp_path / "public-demo.db"))
    monkeypatch.setenv("AURA_MQTT_PORT", "1")
    monkeypatch.setattr(core_app.model_client, "URL", "http://127.0.0.1:1")
    monkeypatch.setattr(core_app.model_client, "_down_until", 0.0)
    runner = FakeRunner()
    monkeypatch.setattr(core_app.showcase, "runner", runner)
    public_demo.reset_cooldowns()
    with TestClient(core_app.app) as client:
        yield client, runner
    public_demo.reset_cooldowns()


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/scenario/normal"),
        ("post", "/checkin"),
        ("post", "/game-sessions"),
        ("post", "/alerts/1/ack"),
        ("put", "/mission"),
        ("delete", "/crew/cm1"),
    ],
)
def test_public_demo_denies_unauthenticated_mutations(public_client, method, path):
    client, _ = public_client
    response = client.request(method, path, json={})
    assert response.status_code == 401
    assert "admin bearer token required" in response.json()["detail"]


def test_public_demo_admin_bearer_allows_mutation(public_client, monkeypatch):
    client, _ = public_client
    monkeypatch.setenv("AURA_ADMIN_TOKEN", "test-admin-secret")
    cleared = []
    monkeypatch.setattr(core_app.store, "clear", lambda crew_id: cleared.append(crew_id))

    response = client.delete("/crew/cm1", headers={"Authorization": "Bearer test-admin-secret"})

    assert response.status_code == 200 and response.json() == {"cleared": "cm1"}
    assert cleared == ["cm1"]


def test_public_showcase_is_allowed_once_then_cooled_down(public_client):
    client, runner = public_client

    first = client.post("/showcase/normal")
    second = client.post("/showcase/normal")

    assert first.status_code == 200
    assert runner.calls and runner.calls[0][0] == "normal"
    assert second.status_code == 429
    assert second.headers["retry-after"].isdigit()
    assert "cooling down" in second.json()["detail"]


def test_public_reads_head_static_websocket_and_cors_remain_available(public_client):
    client, _ = public_client

    assert client.get("/crew").status_code == 200
    assert client.get("/showcases").status_code == 200
    assert client.head("/static/app.js").status_code == 200
    with client.websocket_connect("/ws"):
        pass

    preflight = client.options(
        "/checkin",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200
    assert "access-control-allow-origin" not in preflight.headers


def test_public_mutation_body_limit_applies_before_runner(public_client):
    client, runner = public_client
    body = b"x" * (public_demo.PUBLIC_BODY_LIMIT + 1)

    response = client.post("/showcase/normal", content=body)

    assert response.status_code == 413
    assert "at most" in response.json()["detail"]
    assert runner.calls == []


def test_public_admin_mutation_body_limit_applies_before_handler(public_client, monkeypatch):
    client, _ = public_client
    monkeypatch.setenv("AURA_ADMIN_TOKEN", "test-admin-secret")
    body = b"x" * (public_demo.PUBLIC_BODY_LIMIT + 1)

    response = client.post(
        "/checkin",
        content=body,
        headers={"Authorization": "Bearer test-admin-secret", "Content-Type": "application/json"},
    )

    assert response.status_code == 413
