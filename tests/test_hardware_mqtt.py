"""Optional runtime checks: native Mosquitto + isolated core, never the preview/real hardware."""
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import paho.mqtt.client as mqtt
import pytest
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]
MOSQUITTO = shutil.which("mosquitto")
pytestmark = pytest.mark.skipif(MOSQUITTO is None, reason="native Mosquitto not installed")


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for(check, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if result := check():
                return result
        except (OSError, httpx.HTTPError):
            pass
        time.sleep(0.05)
    raise AssertionError("isolated hardware runtime check timed out")


@pytest.fixture
def runtime(tmp_path):
    broker_port, core_port = free_port(), free_port()
    conf = tmp_path / "mosquitto.conf"
    conf.write_text(f"listener {broker_port} 127.0.0.1\nallow_anonymous true\npersistence false\n")
    env = os.environ | {"AURA_DB": str(tmp_path / "core.db"), "AURA_MQTT_HOST": "127.0.0.1",
                        "AURA_MQTT_PORT": str(broker_port), "AURA_MODEL_URL": "http://127.0.0.1:1"}
    processes = []
    base = f"http://127.0.0.1:{core_port}"
    try:
        with (tmp_path / "runtime.log").open("wb") as log:
            processes.append(subprocess.Popen([MOSQUITTO, "-c", str(conf)], stdout=log, stderr=log))
            processes.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "core.app:app", "--host",
                                               "127.0.0.1", "--port", str(core_port)], cwd=ROOT, env=env,
                                              stdout=log, stderr=log))
            wait_for(lambda: httpx.get(base + "/health").json().get("mqtt_connected"))
            yield base, broker_port, tmp_path
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def payload(signal_name="cabin_co2_mmhg", value=2.2, day=0):
    ts = datetime(2026, 11, 14, 10, tzinfo=timezone.utc) + timedelta(days=day)
    return json.dumps({"crew_id": "cm2", "ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "signal": signal_name,
                       "value": value, "source": "wokwi", "provenance": "simulated"})


def bridge(port, *args, input=None):
    return subprocess.run([sys.executable, "-m", "hardware.bridge", "--host", "127.0.0.1", "--port",
                           str(port), *args], cwd=ROOT, input=input, text=True, capture_output=True, timeout=30)


def test_capture_reaches_mqtt_core_status_timeline_and_websocket(runtime):
    base, port, tmp = runtime
    rows = []
    lines = ["ets Jun  8 2016 00:22:57", "# synthetic firmware-format fixture, not an actual Wokwi capture"]
    for day in range(30):
        lines.append(f"# day {day}")
        if day < 28:  # two pulse-off days: never turn missing HR/RMSSD into zero readings
            rows.extend([payload("resting_hr_bpm", 60, day), payload("rmssd_ms", 55, day)])
            lines.extend(rows[-2:])
        rows.append(payload(value=3.5 if day == 29 else 2.2, day=day))
        lines.append(rows[-1])
        if day % 7 == 0:
            for name, value in [("lymphocytes_per_ul", 2679), ("il6_pg_ml", 3.7),
                                ("nk_activity_pct", 100), ("viral_pcr_positive", 0)]:
                rows.append(payload(name, value, day))
                lines.append(rows[-1])
    capture = tmp / "synthetic_serial.txt"
    capture.write_text("\n".join(lines) + "\n")

    received = []
    subscribed = threading.Event()
    observer = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    observer.on_connect = lambda c, *_: c.subscribe("aura/+/+", qos=1)
    observer.on_subscribe = lambda *_: subscribed.set()
    observer.on_message = lambda _c, _u, m: received.append((m.topic, m.payload.decode()))
    observer.connect("127.0.0.1", port)
    observer.loop_start()
    try:
        assert subscribed.wait(5)
        with connect(base.replace("http://", "ws://") + "/ws", open_timeout=5) as ws:
            result = bridge(port, "--file", str(capture))
            assert result.returncode == 0, result.stderr
            assert f"Published: {len(rows)}, Rejected: 0" in result.stderr
            pushed = json.loads(ws.recv(timeout=10))
            assert pushed["crew_id"] == "cm2" and pushed["disclaimer"]
        wait_for(lambda: httpx.get(base + "/health").json()["readings"] == len(rows))
        wait_for(lambda: len(received) == len(rows))
        assert [text for _, text in received] == rows  # original source, provenance and Z timestamps survive MQTT
        assert {topic for topic, _ in received} == {"aura/cm2/vitals", "aura/cm2/cabin", "aura/cm2/labs"}
        assert httpx.get(base + "/crew").json() == ["cm2"]
        status = httpx.get(base + "/crew/cm2/status").json()
        assert status["signals"]["cabin_co2_mmhg"]["value"] == 3.5
        assert status["signals"]["cabin_co2_mmhg"]["provenance"] == "simulated"
        assert status["signals"]["resting_hr_bpm"]["band"] == "stale"
        assert status["signals"]["sleep_duration_h"]["band"] == "unknown"
        trend = httpx.get(base + "/crew/cm2/signal/cabin_co2_mmhg?days=60").json()["points"]
        assert len(trend) == 30 and trend[-1]["value"] == 3.5
        assert trend[-1]["ts"] == "2026-12-13T10:00:00+00:00"
        timeline = httpx.get(base + "/crew/cm2/timeline").json()
        assert len(timeline["days"]) == 30 and timeline["days"][-1]["systems"]["environment"] == "red"
        assert httpx.get(base + "/static/app.js").status_code == 200
        assert bridge(port, "--file", str(capture)).returncode == 0
        wait_for(lambda: len(received) == 2 * len(rows))
        assert httpx.get(base + "/health").json()["readings"] == len(rows)  # QoS 1/replay dedupe in core
        bad = bridge(port, input="not json\n" + rows[-1] + "\n{\"truncated\":")
        assert bad.returncode == 1 and "Published: 1, Rejected: 2" in bad.stderr
        info = observer.publish("aura/cm2/cabin", "bad direct MQTT payload", qos=1)
        info.wait_for_publish(timeout=5)
        wait_for(lambda: httpx.get(base + "/health").json()["rejects"] == 1)
        assert httpx.get(base + "/health").json()["readings"] == len(rows)
    finally:
        observer.disconnect()
        observer.loop_stop()


def test_serial_port_input_with_os_pseudo_terminal(runtime):
    pytest.importorskip("serial", reason="optional hardware dependency group not installed")
    if not hasattr(os, "openpty"):
        pytest.skip("OS pseudo-terminal unavailable")
    base, port, tmp = runtime
    master, slave = os.openpty()
    process = None
    log_path = tmp / "serial_bridge.log"
    try:
        with log_path.open("wb") as log:
            process = subprocess.Popen([sys.executable, "-m", "hardware.bridge", "--host", "127.0.0.1",
                                        "--port", str(port), "--serial", os.ttyname(slave)], cwd=ROOT,
                                       stdout=log, stderr=log)
            wait_for(lambda: "Connected to" in log_path.read_text())
            line = payload(value=2.7) + "\n"
            os.write(master, line[:20].encode())  # partial arrival must not publish a partial message
            time.sleep(0.15)
            assert httpx.get(base + "/health").json()["readings"] == 0
            os.write(master, line[20:].encode())
            wait_for(lambda: httpx.get(base + "/health").json()["readings"] == 1)
            assert httpx.get(base + "/crew/cm2/status").json()["signals"]["cabin_co2_mmhg"]["value"] == 2.7
            process.send_signal(signal.SIGINT)
            assert process.wait(timeout=5) == 130
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        os.close(master)
        os.close(slave)


def test_missing_broker_exits_nonzero_without_claiming_delivery():
    result = bridge(free_port(), input=payload() + "\n")
    assert result.returncode == 2 and "Bridge stopped:" in result.stderr
    assert "Published:" not in result.stderr
