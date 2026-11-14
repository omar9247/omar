"""Forward Wokwi Serial JSON to the existing MQTT bus: python -m hardware.bridge --help."""
from __future__ import annotations

import argparse
import logging
import math
import sys
import threading
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Iterable

import paho.mqtt.client as mqtt

from contract.schema import Reading, load_signals

log = logging.getLogger("aura.hardware")
BOOT_PREFIXES = ("ets ", "rst:", "configsip:", "clk_drv:", "mode:", "load:", "ho ", "entry ")


def parse_line(line: str, crew: str) -> Reading | None:
    """Ignore Serial diagnostics; reject anything outside the simulated Wokwi contract."""
    line = line.strip()
    if not line or line.startswith(("#", *BOOT_PREFIXES)):
        return None
    r = Reading.model_validate_json(line)
    if r.crew_id != crew or not crew or any(c in crew for c in "/+#"):
        raise ValueError(f"expected crew_id={crew!r} without MQTT topic separators or wildcards")
    if r.source != "wokwi" or r.provenance != "simulated":
        raise ValueError("expected source='wokwi' and provenance='simulated'")
    if r.signal not in {s["name"] for s in load_signals() if s["source"] == "wokwi"}:
        raise ValueError(f"signal {r.signal!r} is not a contract-declared Wokwi input")
    if not math.isfinite(r.value):
        raise ValueError("value is not finite")
    return r


def forward(lines: Iterable[bytes], client: mqtt.Client, crew: str = "cm2", speed: float = 0,
            timeout: float = 10) -> tuple[int, int]:
    """Publish unchanged payloads, waiting for each QoS 1 acknowledgement before reading more."""
    published = rejected = 0
    previous_day = None
    for lineno, raw in enumerate(lines, 1):
        try:
            line = raw.decode("utf-8").strip()
            r = parse_line(line, crew)
        except ValueError as e:
            rejected += 1
            log.warning("Rejected Serial line %d: %s", lineno, e)
            continue
        if r is None:
            continue
        day = r.ts.date()
        if previous_day is not None and day != previous_day and speed:
            time.sleep(speed)
        previous_day = day
        info = client.publish(r.topic(), line, qos=1, retain=False)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError(f"Serial line {lineno} was not queued: {mqtt.error_string(info.rc)}")
        info.wait_for_publish(timeout=timeout)
        if not info.is_published():
            raise TimeoutError(f"No broker acknowledgement for Serial line {lineno}; keep the capture for retry")
        published += 1
    return published, rejected


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    source = ap.add_mutually_exclusive_group()
    source.add_argument("--file", type=Path, help="captured Serial log; default is stdin")
    source.add_argument("--serial", help="serial port, e.g. COM5 or /dev/ttyUSB0 (needs the hardware dependency group)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--crew", default="cm2", help="expected crew; never rewrites the firmware crew_id")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--speed", type=float, default=0, help="pause between simulated days when replaying a capture (seconds)")
    ap.add_argument("--timeout", type=float, default=10, help="broker connection / acknowledgement timeout (seconds)")
    a = ap.parse_args()
    if not math.isfinite(a.speed) or a.speed < 0 or not math.isfinite(a.timeout) or a.timeout <= 0:
        ap.error("--speed must be finite and non-negative; --timeout must be finite and positive")
    if a.baud <= 0 or not 1 <= a.port <= 65535 or not a.crew or any(c in a.crew for c in "/+#"):
        ap.error("invalid baud, port, or crew (no MQTT separators/wildcards)")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect_timeout = a.timeout
    connected = threading.Event()

    def on_connect(_client, _userdata, _flags, reason_code, _properties):
        if reason_code.is_failure:
            log.error("Broker refused connection: %s", reason_code)
        else:
            connected.set()

    client.on_connect = on_connect
    try:
        with ExitStack() as stack:
            if a.serial:
                try:
                    import serial
                except ImportError:
                    raise RuntimeError("Serial input needs: uv sync --group hardware") from None
                stream = stack.enter_context(serial.Serial(a.serial, a.baud, timeout=None))
            elif a.file:
                stream = stack.enter_context(a.file.open("rb"))
            else:
                stream = sys.stdin.buffer
            client.connect(a.host, a.port)
            client.loop_start()
            if not connected.wait(a.timeout):
                raise TimeoutError("Broker did not accept the connection")
            log.info("Connected to %s:%d; forwarding simulated Wokwi readings for %s", a.host, a.port, a.crew)
            published, rejected = forward(iter(stream.readline, b""), client, a.crew, a.speed, a.timeout)
            log.info("Published: %d, Rejected: %d", published, rejected)
            return 1 if rejected or not published else 0
    except KeyboardInterrupt:
        log.info("Stopped; keep a Serial capture if you need to replay readings")
        return 130
    except (OSError, RuntimeError, ValueError) as e:
        log.error("Bridge stopped: %s", e)
        return 2
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    raise SystemExit(main())
