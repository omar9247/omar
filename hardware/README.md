# Hardware connection

`bridge.py` forwards the Serial JSON emitted by `firmware/src/main.cpp` to the existing MQTT bus. It does not generate readings, change timestamps, fill missing sensors, calculate health bands, or require the anomaly model.

The path is **Wokwi/ESP32 Serial → host bridge → Mosquitto → core → existing web console**. The integrated branch includes the firmware component from `hardware` commit `29b7e82915cf6cb50674cbfcbf70fa2650dedb91`, with freshly compiled custom-chip WASM; no retired hardware-branch UI was imported. Build/run instructions are in `firmware/README.md` and actual execution evidence is in `docs/offline-and-wokwi-verification.md`.

## Start the existing bus

```bash
# Core + broker only; no trained model artifacts needed for the hardware connection.
docker compose up --build broker core
```

The broker is on `localhost:1883` and the console is at `http://localhost:8000`. Do not also run a second local core against that broker: both use client ID `aura-core` and would disconnect each other. If you already run the core locally, start only `docker compose up -d broker` instead.

The checked-in Mosquitto configuration allows anonymous connections and publishes port 1883. Use it only on a trusted demo network; do not expose it to the public internet. Authentication/TLS is not added by this bridge.

## Forward Serial output

For a completed Wokwi capture (also works with output copied from the Wokwi browser):

```bash
uv sync
uv run python -m hardware.bridge --file /path/to/serial_capture.txt --speed 1
```

`--speed` pauses once per new simulated day when reading a saved capture. Its default is zero (publish as fast as acknowledged). For live stdin or a serial port, omit it so the firmware controls pacing.

For live output supplied by a tool that streams Serial JSON to stdout:

```bash
SERIAL_OUTPUT_COMMAND | uv run python -m hardware.bridge
```

A Wokwi VS Code/web simulator is not automatically a physical COM port. If it only offers a capture, use `--file`; no direct Wi-Fi/MQTT firmware path is assumed. To stream a growing Wokwi CLI capture on Linux/macOS:

```bash
tail -n +1 -F /path/to/serial_capture.txt | uv run python -m hardware.bridge
```

Keep the capture as a durable source for retries. Stop both commands when the simulation ends; a file-following process does not know the simulator has finished. PowerShell users can use `Get-Content -Path C:\path\serial_capture.txt -Wait` piped to the bridge (start after the capture file exists).

For an actual serial device or an explicitly provided virtual serial port:

```bash
uv sync --group hardware
uv run --group hardware python -m hardware.bridge --serial /dev/ttyUSB0
# Windows: replace /dev/ttyUSB0 with COM5 (or your port).
```

`--baud` defaults to the firmware's 115200. Close other serial monitors that hold the port. Physical ESP32 ADC calibration is separate from this transport: the current firmware is calibrated for Wokwi, not physical health sensors.

Use `--host` and `--port` for a broker running elsewhere. `--crew` defaults to `cm2` and is an expectation check, not a rewrite; set it only if the firmware was deliberately built for another crew ID.

## Delivery and verification

Each accepted line is published unchanged (apart from surrounding whitespace) using `Reading.topic()`: HR/RMSSD → `aura/cm2/vitals`, CO₂ → `aura/cm2/cabin`, labs → `aura/cm2/labs`. Blank lines, `#` diagnostics, and known ESP32 boot lines are ignored. Invalid JSON, unknown or non-Wokwi signals, non-finite values, wrong crew IDs, or anything not marked `source: wokwi` / `provenance: simulated` is rejected with a line number. The allowed inputs come from the shared contract's `source: wokwi` metadata, so app/generator signals cannot be mislabeled as hardware. Valid subsequent lines continue; the command exits nonzero if any input was rejected or no readings were published.

The bridge uses QoS 1, no retained readings, and waits for the broker's acknowledgement for each message. A connection or acknowledgement failure stops forwarding and exits nonzero. QoS 1 acknowledges the broker, not database persistence; verify core ingestion separately. No automatic disk spool is provided: keep a Serial capture and replay it after a failure. The core deduplicates by crew/signal/timestamp, so replaying an identical capture does not add duplicate rows. A changed value at that same key replaces the previous value; a new firmware run restarts its simulated date, so deliberately reset demo `cm2` before an unrelated run if needed.

After publishing, check `GET /health` (`mqtt_connected: true`, increased reading count), `GET /crew` (includes `cm2`), `GET /crew/cm2/status`, and `GET /crew/cm2/timeline`. Select `cm2` in the existing console. The hardware only supplies its implemented signals; absent sleep/reaction/exercise/dose signals must remain unknown/stale rather than fabricated. Leave sliders at defaults during the first 14 simulated days (28 for lab baselines) before demonstrating changes.

For phase-2 firmware/cadence validation, use the existing validator from the firmware checkout:

```bash
uv run python firmware/tools/validate_serial.py --timeline --crew cm2 /path/to/serial_capture.txt
```

The bridge validates individual transport messages, not 30-day capture completeness or ADC correctness. Focused bridge regression tests are in `tests/test_hardware_bridge.py`:

```bash
uv run pytest -q tests/test_hardware_bridge.py
```
