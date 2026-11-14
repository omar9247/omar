import json
from unittest.mock import Mock

import paho.mqtt.client as mqtt
import pytest

from hardware.bridge import forward, parse_line


def message(**changes):
    return json.dumps({"crew_id": "cm2", "ts": "2026-11-14T10:00:00Z", "signal": "resting_hr_bpm",
                       "value": 60.0, "source": "wokwi", "provenance": "simulated"} | changes)


def publisher():
    client = Mock()
    client.publish.return_value.rc = mqtt.MQTT_ERR_SUCCESS
    client.publish.return_value.is_published.return_value = True
    return client


@pytest.mark.parametrize("line", ["", "  ", "# day 0", "ets Jun  8 2016 00:22:57", "rst:0x1", "entry 0x400805e4"])
def test_ignores_serial_diagnostics(line):
    assert parse_line(line, "cm2") is None


@pytest.mark.parametrize("bad", ["not json", message(signal="unknown"), message(value=float("nan")),
                                  message(value=float("inf")), message(crew_id="cm1"), message(source="app"),
                                  message(provenance="real"), message(provenance="replayed"),
                                  message(ts="2026-11-14T10:00:00"), message(value="broken")])
def test_rejects_invalid_or_mislabelled_readings(bad):
    with pytest.raises(ValueError):
        parse_line(bad, "cm2")


@pytest.mark.parametrize("name", ["bp_systolic_mmhg", "sleep_duration_h", "mood_score", "dose_mgy"])
def test_rejects_other_workstream_signals_mislabelled_as_wokwi(name):
    with pytest.raises(ValueError, match="not a contract-declared Wokwi input"):
        parse_line(message(signal=name), "cm2")


def test_crew_cannot_inject_topic_segments():
    with pytest.raises(ValueError):
        parse_line(message(crew_id="cm2/other"), "cm2/other")


def test_routes_all_hardware_groups_without_changing_payloads():
    client = publisher()
    signals = ["resting_hr_bpm", "rmssd_ms", "cabin_co2_mmhg", "lymphocytes_per_ul",
               "il6_pg_ml", "nk_activity_pct", "viral_pcr_positive"]
    payloads = [message(signal=s) for s in signals]
    assert forward([p.encode() for p in payloads], client) == (7, 0)
    groups = ["vitals", "vitals", "cabin", "labs", "labs", "labs", "labs"]
    assert [call.args for call in client.publish.call_args_list] == [
        (f"aura/cm2/{group}", payload) for group, payload in zip(groups, payloads)]
    assert all(c.kwargs == {"qos": 1, "retain": False} for c in client.publish.call_args_list)
    assert client.publish.return_value.wait_for_publish.call_count == 7


def test_rejected_line_does_not_stop_later_valid_readings():
    client = publisher()
    assert forward([b"# day 0", b"bad", b"\xff", message().encode()], client) == (1, 2)
    client.publish.assert_called_once()


def test_capture_pacing_once_per_new_day(monkeypatch):
    sleep = Mock()
    monkeypatch.setattr("hardware.bridge.time.sleep", sleep)
    lines = [message(), message(signal="rmssd_ms"), message(ts="2026-11-15T10:00:00Z"),
             message(ts="2026-11-15T10:00:00Z", signal="cabin_co2_mmhg")]
    assert forward([p.encode() for p in lines], publisher(), speed=1) == (4, 0)
    sleep.assert_called_once_with(1)


@pytest.mark.parametrize("rc,acked,error", [(mqtt.MQTT_ERR_NO_CONN, False, ConnectionError),
                                             (mqtt.MQTT_ERR_SUCCESS, False, TimeoutError)])
def test_unacknowledged_publish_stops_before_consuming_next_reading(rc, acked, error):
    client = publisher()
    client.publish.return_value.rc = rc
    client.publish.return_value.is_published.return_value = acked
    lines = iter([message().encode(), message(signal="rmssd_ms").encode()])
    with pytest.raises(error):
        forward(lines, client, timeout=0.01)
    assert json.loads(next(lines))["signal"] == "rmssd_ms"
    client.publish.assert_called_once()
