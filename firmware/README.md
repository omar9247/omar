# AURA-Bio Wokwi Sensor Layer (Phase 1 & Phase 2)

ESP32 DevKitC v4 (`board-esp32-devkit-c-v4`) + 3 custom Wokwi chips (`pulse`, `co2`, `analyzer`) printing contract `Reading` JSON lines over Serial.

Still Serial only — no WiFi, MQTT, or noise model yet.

## Files

- `src/main.cpp` — ESP32 Arduino sketch reading ADC1 pins (`34`, `35`, `32`, `33`, `VP`/`36`, `VN`/`39`) and digital pins (`25`, `26`)
- `chips/{pulse,co2,analyzer}.chip.json` & `.chip.c` — custom Wokwi chips with interactive sliders
- `diagram.json` — circuit wiring with chip defaults
- `platformio.ini` & `wokwi.toml` — PlatformIO (`esp32dev` default + `fast` test env) + Wokwi config
- `tools/validate_serial.py` — validates captured Serial lines against `contract/schema.py`

## Phase 2 behavior (backend timeline)

- `CREW_ID` is `"cm2"` (so it does not collide with `cm1` from the Python generator).
- `ts` advances 1 simulated day per cycle starting from `2026-11-14T10:00:00Z` (with `Z`).
- `SECONDS_PER_DAY` defaults to `10` s/day (overridable via `-DSECONDS_PER_DAY=1` in the `fast` PlatformIO env).
- Labs (`lymphocytes_per_ul`, `il6_pg_ml`, `nk_activity_pct`, `viral_pcr_positive`) print only on days `0, 7, 14, ...`; other days print only HR, RMSSD, and CO₂.
- With pulse `ON` off, HR and RMSSD lines are omitted while the day counter continues advancing.
- Non-JSON debug lines start with `#` (e.g. `# day 0`).
- **Using sliders during a demo:** the core service uses the first **14 days** (28 days for labs) as the baseline, so leave sliders at defaults for the first 14–28 simulated days before moving them.

## Option A — Run locally (VS Code or Wokwi CLI)

1. **Build the firmware:**
   ```powershell
   & "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe" run            # default 10 s/day
   & "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe" run -e fast    # 1 s/day for quick tests
   ```
2. **Compile the 3 custom chips to `.wasm`** before the first CI run, after changing `.chip.c`, or after upgrading the CLI:
   ```powershell
   $w = "$env:USERPROFILE\.wokwi\bin\wokwi-cli.exe"
   & $w chip compile -o chips/pulse.chip.wasm chips/pulse.chip.c
   & $w chip compile -o chips/co2.chip.wasm chips/co2.chip.c
   & $w chip compile -o chips/analyzer.chip.wasm chips/analyzer.chip.c
   ```
3. **Interactive in VS Code:**
   - Open `firmware/diagram.json`, press `F1`, and run **Wokwi: Start Simulator**.
   - Click each custom chip in the diagram to adjust its sliders and switches.
4. **Headless via Wokwi CLI** (requires `WOKWI_CLI_TOKEN`):
   ```powershell
   & "$env:USERPROFILE\.wokwi\bin\wokwi-cli.exe" . --timeout 35000 --timeout-exit-code 0 --serial-log-file unneeded/serial_capture.txt
   ```
   Create `unneeded/` first. For the `fast` environment, set **both** `firmware` and `elf` in `wokwi.toml` to `.pio/build/fast/firmware.bin` and `.pio/build/fast/firmware.elf`. A 35-second fast run covers 35 simulated days; the default 10-second/day environment needs 350 seconds for that coverage. Do not mix build environments.

On Linux/macOS, run `pio run -e esp32dev` and `pio run -e fast` inside `firmware/`. Compile each chip with `wokwi-cli chip compile -o chips/<name>.chip.wasm chips/<name>.chip.c`, then use `wokwi-cli .` with the same capture/timeout options. Keep the CI token in `WOKWI_CLI_TOKEN`, never in source or command-line arguments. Actual verification used CLI 0.29.1 and newly compiled chips with unchanged C sources; see `../docs/offline-and-wokwi-verification.md`.

## Option B — Run on wokwi.com

1. Open <https://wokwi.com> → **New Project** → **ESP32**.
2. Paste `src/main.cpp` into `sketch.ino`.
3. Replace `diagram.json` with `firmware/diagram.json`.
4. Add 6 new files via the editor menu (`pulse.chip.json`, `pulse.chip.c`, `co2.chip.json`, `co2.chip.c`, `analyzer.chip.json`, `analyzer.chip.c`). The browser compiles the `.chip.c` files automatically.
5. Click **Start the simulation**, click any chip to move its sliders, and copy Serial output into `firmware/unneeded/serial_capture.txt`.

## Validate Serial output

From the repo root (`Aura-bio-hardware`):

```powershell
py firmware/tools/validate_serial.py --timeline --crew cm2 firmware/unneeded/serial_capture.txt
py firmware/tools/validate_serial.py --timeline --crew cm2 --expect-defaults firmware/unneeded/serial_capture.txt
```
