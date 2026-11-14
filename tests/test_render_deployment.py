import hashlib
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from core import app as core
from core.store import Store
from deploy.render import seed_demo
from generator.showcase import RESERVED_CREWS

ROOT = Path(__file__).resolve().parents[1]


def test_render_topology():
    services = yaml.safe_load((ROOT / "deploy/render/render.yaml").read_text())["services"]
    assert [(s["type"], s["plan"]) for s in services] == [
        ("pserv", "0.5c-512mb"), ("pserv", "0.5c-512mb"), ("web", "0.5c-512mb")]
    assert [s["disk"]["sizeGB"] for s in services if "disk" in s] == [1, 1]
    env = {v["key"]: v for v in services[-1]["envVars"]}
    assert env["AURA_PUBLIC_DEMO"]["value"] == "1"
    assert env["AURA_ADMIN_TOKEN"]["generateValue"] is True
    assert all(s["autoDeployTrigger"] == "off" for s in services)


def test_packaged_model_version():
    artifacts = ROOT / "deploy/render/model-artifacts"
    payload = b"".join((artifacts / f).read_bytes() for f in ("model_2d.pt", "ewma.json"))
    assert hashlib.sha256(payload).hexdigest()[:12] == "8d30c5cab8db"


def test_seed_is_simulated_and_repeat_safe(tmp_path, monkeypatch):
    path = str(tmp_path / "core.db")
    monkeypatch.setenv("AURA_PUBLIC_DEMO", "1")
    monkeypatch.setenv("AURA_DB", path)
    monkeypatch.setattr(core, "store", None, raising=False)
    monkeypatch.setattr(core.model_client, "score", lambda *_: {"available": False, "reason": "test"})
    seed_demo.seed()
    store = Store(path)
    first_count = store.count()
    assert first_count > 1000
    assert set(store.crews()) == set(RESERVED_CREWS.values())
    assert store.q("SELECT count(*) n FROM reading WHERE provenance != 'simulated'")[0]["n"] == 0
    store.db.close()
    seed_demo.seed()
    store = Store(path)
    assert store.count() == first_count
    store.db.close()


def test_seed_does_not_touch_existing_crew(tmp_path, monkeypatch):
    path = str(tmp_path / "core.db")
    store = Store(path)
    store.set_mission("station", 0, 0)
    store.q("INSERT INTO crew_member VALUES (?, ?, 1)", "cm2", "cm2")
    store.db.close()
    monkeypatch.setenv("AURA_PUBLIC_DEMO", "1")
    monkeypatch.setenv("AURA_DB", path)
    monkeypatch.setattr(core, "store", None, raising=False)
    seed_demo.seed()
    store = Store(path)
    assert store.crews() == ["cm2"]
    assert store.count() == 0
    store.db.close()


def test_seed_failure_rolls_back(tmp_path, monkeypatch):
    path = str(tmp_path / "core.db")
    monkeypatch.setenv("AURA_PUBLIC_DEMO", "1")
    monkeypatch.setenv("AURA_DB", path)
    monkeypatch.setattr(core, "store", None, raising=False)
    def fail(*_):
        raise RuntimeError("interrupted")
    monkeypatch.setattr(core, "crew_status", fail)
    with pytest.raises(RuntimeError, match="interrupted"):
        seed_demo.seed()
    store = Store(path)
    assert store.count() == 0
    assert store.crews() == []
    store.db.close()


def test_free_demo_private_ports_and_supervisor_cleanup(tmp_path):
    dockerfile = (ROOT / "deploy/render/FreeDemo.Dockerfile").read_text()
    assert "AURA_PUBLIC_DEMO=1" in dockerfile
    assert "AURA_MODEL_URL=http://127.0.0.1:8001" in dockerfile
    assert "AURA_ADMIN_TOKEN=" not in dockerfile
    assert "listener 1883 127.0.0.1" in (ROOT / "deploy/render/free-mosquitto.conf").read_text()
    bins = tmp_path / "bin"
    bins.mkdir()
    commands = {
        "python": "#!/bin/sh\nexit 0\n",
        "mosquitto": f"#!/bin/sh\necho $$ > '{tmp_path / 'broker.pid'}'\nexec sleep 60\n",
        "uvicorn": f"#!/bin/sh\ncase \"$1\" in model.*) echo $$ > '{tmp_path / 'model.pid'}'; exec sleep 60;; *) exit 9;; esac\n",
    }
    for name, text in commands.items():
        path = bins / name
        path.write_text(text)
        path.chmod(0o755)
    result = subprocess.run(["sh", str(ROOT / "deploy/render/start_free_demo.sh")],
                            cwd=tmp_path, env=os.environ | {"PATH": f"{bins}:/usr/bin:/bin"},
                            capture_output=True, timeout=10)
    assert result.returncode == 9
    for name in ("model", "broker"):
        pid = int((tmp_path / f"{name}.pid").read_text())
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
