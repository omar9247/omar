import numpy as np
import pytest
import torch
from fastapi.testclient import TestClient

from contract.schema import model_signals
from model import autoencoder, ewma, service

SIG = model_signals()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Service on an untrained 2-day model (threshold 1) and a unit EWMA calibration."""
    torch.manual_seed(0)
    autoencoder.save(tmp_path / "model_2d.pt", autoencoder.WindowAE(2, len(SIG)), 1.0, SIG)
    ewma.save(tmp_path / "ewma.json", np.ones(len(SIG)), 1.0, SIG)
    monkeypatch.setattr(service, "ARTIFACTS", tmp_path)
    monkeypatch.setattr(service, "_models", {})
    return TestClient(service.app)


def test_autoencoder_alarm_needs_two_days_and_ewma_counts_only_harm(client):
    rng = np.random.default_rng(0)
    days = rng.normal(size=(14, len(SIG)))
    days[:, SIG.index("sleep_duration_h")] = 2.0  # sleeping more: harmless for the drift score
    r = client.post("/score", json={"crew_id": "cm1", "window": {s: days[:, i].tolist() for i, s in enumerate(SIG)}})
    assert r.status_code == 200, r.text
    body = r.json()
    m = service._models[2][0]
    x = torch.from_numpy(days.astype(np.float32))
    today, yesterday = (float(autoencoder.errors(m, x[a:b].unsqueeze(0))[0]) for a, b in [(12, 14), (11, 13)])
    assert body["scores"]["2d"] == pytest.approx(min(today, yesterday), abs=1e-3)
    assert body["drift"]["sleep_duration_h"] == 0
    assert body["score"] == max(body["scores"].values()) and abs(sum(body["contributions"].values()) - 1) < 0.01


def test_rejects_too_few_days_and_unknown_signals(client):
    assert client.post("/score", json={"crew_id": "cm1", "window": {"rmssd_ms": [0.0, 0.0]}}).status_code == 422
    assert client.post("/score", json={"crew_id": "cm1", "window": {"heart": [0.0] * 14}}).status_code == 422


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity"])
def test_rejects_non_finite_values_instead_of_reading_as_healthy(client, bad):
    body = '{"crew_id": "cm1", "window": {"resting_hr_bpm": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, %s]}}' % bad
    assert client.post("/score", content=body, headers={"Content-Type": "application/json"}).status_code == 422


def test_absurd_values_are_capped_like_training_and_score_carries_the_model_version(client):
    def post(v):
        return client.post("/score", json={"crew_id": "cm1", "window": {"resting_hr_bpm": [0.0] * 13 + [v]}}).json()
    capped, absurd = post(service.Z_CAP), post(1e6)
    assert absurd["scores"] == capped["scores"] and absurd["drift"] == capped["drift"]
    version = client.get("/health").json()["model_version"]
    assert len(version) == 12 and absurd["model_version"] == version
