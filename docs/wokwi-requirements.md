# Wokwi sensor layer: requirements

**Status (2026-11-14):** phase 1 (a working circuit) is built in `firmware/` and checked in
Wokwi (section 4). **Next: phase 2** — make the Serial output follow the
timeline the core service (backend) expects (section 5). Still no network: connecting to the backend
is a separate piece of work, planned later.

Numbers come from `contract/signals.yaml` (calibrated from real data, see `data/SOURCES.md`).

## 1. Parts

| Part | Role |
| --- | --- |
| ESP32 DevKit (Wokwi `board-esp32-devkit-c-v4`) | Reads the chips, builds messages |
| Custom chip **pulse** | Heart rate and HRV, plus an on/off line |
| Custom chip **co2** | Cabin CO₂ |
| Custom chip **analyzer** | Four lab values |

Custom chips: a `.chip.json` (pins + attributes) and a `.chip.c` each
([Wokwi Custom Chips API](https://docs.wokwi.com/chips-api/getting-started)). Attributes appear as
sliders in the simulator.

## 2. How each value reaches the ESP32

Phase 1 keeps it simple: **each value is an analog voltage (0–3.3 V)** that the chip sets from its
slider (`pin_dac_write`), and the ESP32 reads with `analogRead` (12-bit, 0–4095). Viral shedding and
the pulse sensor's on/off are digital pins.

Use **ADC1 pins only** (GPIO 32–39): ADC2 pins stop working on the ESP32 once WiFi is on, which the later connection
needs.

| Chip | Output pin → ESP32 pin | Signal | Value at 0 V | Value at 3.3 V | Slider default |
| --- | --- | --- | --- | --- | --- |
| pulse | `HR` → GPIO 34 | `resting_hr_bpm` | 30 | 130 | 60 |
| pulse | `HRV` → GPIO 35 | `rmssd_ms` | 0 | 200 | 55 |
| pulse | `ON` → GPIO 25 (digital) | sensor present | low = off | high = on | on |
| co2 | `CO2` → GPIO 32 | `cabin_co2_mmhg` | 0 | 10 | 2.2 |
| analyzer | `LYM` → GPIO 33 | `lymphocytes_per_ul` | 0 | 6000 | 2679 |
| analyzer | `IL6` → GPIO 36 | `il6_pg_ml` | 0 | 25 | 3.7 |
| analyzer | `NK` → GPIO 39 | `nk_activity_pct` | 0 | 150 | 100 |
| analyzer | `VIR` → GPIO 26 (digital) | `viral_pcr_positive` | low = 0 | high = 1 | 0 |

Both ends use the same `lo` and `hi` from the table (the values at 0 V and 3.3 V):

- **Chip** (slider value → voltage): `voltage = 3.3 * (value - lo) / (hi - lo)`
- **Sketch** (voltage → value): `value = lo + (hi - lo) * analogRead(pin) / 4095.0`

Ranges that don't start at 0 (heart rate starts at 30) give wrong readings if either side leaves out
`lo`: e.g. a chip outputting `3.3 * value / 130` for 60 bpm makes the sketch read 76 bpm.

Why these ranges: they cover normal values (defaults = the typical level in our data), every demo
scenario and every alert line in the plan:

- **Heart rate:** the deconditioning scenario is +12 bpm; the plan's red line is +20 over baseline.
- **HRV:** the sleep-debt scenario is −25%; the plan's red line is −35%.
- **CO₂:** the ISS cabin has ranged 1–9 mmHg; the plan's amber is 2.5–3 and red is above 3.
- **Lymphocytes:** they fell up to 48% after the Inspiration4 flight.
- **IL-6:** it rose up to 190% after the Inspiration4 flight.
- **NK activity:** ISS crew lost about 50% by flight day 90.

The chip sliders should use these same ranges, so what you set is what the ESP32 reads.

## 3. What the sketch does (phase 1)

Every 2 seconds (stand-in for "one simulated day" until phase 2):

1. Read all pins and convert to values (section 2).
2. If the pulse `ON` pin is low, skip `resting_hr_bpm` and `rmssd_ms` entirely (no message, not 0).
3. Print one JSON line per signal to Serial, in the contract format:

```json
{"crew_id":"cm1","ts":"2026-11-14T10:00:00Z","signal":"resting_hr_bpm","value":60.1,"source":"wokwi","provenance":"simulated"}
```

- `crew_id`: `cm1` for now (a `#define`).
- `ts`: fixed day-0 timestamp for now; phase 2 makes it advance.
- `value`: round to sensible precision (1 decimal for HR, RMSSD, IL-6, NK; 2 for CO₂; whole numbers for
  lymphocytes; 0 or 1 for viral).
- `source` is always `"wokwi"`, `provenance` always `"simulated"`.

Printing the exact message now means the later connection work only has to send the same lines.

## 4. Done when (phase 1)

Checked 2026-11-13 in the Wokwi VS Code extension; Serial output run through
`firmware/tools/validate_serial.py`.

- [x] The circuit runs in Wokwi (VS Code extension) with the 3 chips wired as in section 2
- [x] With sliders at their defaults, Serial shows 7 lines per cycle with values within ~1% of the
      defaults (HR 60.0, RMSSD 55.0, CO₂ 2.20, lymphocytes 2680 for 2679, IL-6 3.7, NK 100.0, viral 0)
- [x] Moving each slider changes only its own value — seen for all 6: heart rate 60 → 95.5, RMSSD
      55 → 96.5, CO₂ 0.32 to 8.40, lymphocytes 2509 to 4089, IL-6 3.7 → 18.6, NK 58 to 144.5. The exact
      ends of each range were not hit
- [x] Pulse `ON` off → the two pulse lines disappear; on → they come back (cycles drop from 7 lines
      to 5, then return to 7)
- [x] Viral switch flips the value from 0 to 1 (back to 0 not tried)
- [x] Every printed line validates in Python: `Reading(**json.loads(line))` from `contract/schema.py`
      (210/210 lines of the first run; every distinct line of the second run)
- [x] Project files committed under `firmware/` (`diagram.json`, `wokwi.toml`, sketch, chips, validator)

Findings from the run:

- **ADC reference:** Wokwi's ESP32 ADC reads 0–5 V, so `ADC_VREF 5.0` in `main.cpp` is right for the
  simulator (defaults read back exactly). Real ESP32 hardware needs 3.3.
- **Precision:** one ADC step is about 2.2 /µL for lymphocytes and 0.04 bpm for heart rate, well under
  each signal's day-to-day spread.
- **Not checked:** the committed `chips/*.wasm` were not rebuilt from the `.c` files (no `wokwi-cli`
  here); rebuild them after any chip change.

## 5. Phase 2: output the backend can use

Still Serial only. The message format from phase 1 is already right; what changes is **when** lines are
printed and **what `ts` they carry**. Each rule below exists because of how the core service on `main`
stores and reads messages, so that connecting later means sending these same lines unchanged.

### 5.1 Rules

| # | Rule | Why the backend needs it |
| --- | --- | --- |
| 1 | **`ts` advances one simulated day per cycle**, starting at `2026-11-14T10:00:00Z` (day 1 = `2026-11-15T10:00:00Z`, …). Keep a day counter that goes up by one after each cycle. **Keep the `Z`** at the end. | The core keeps one reading per `crew_id` + `signal` + `ts`. With the phase 1 fixed `ts`, every message would replace the one before, and the crew member would never get a baseline or any bands. A `ts` without a time zone (`Z`) is rejected (contract, plan 4.2). |
| 2 | **One line per signal per simulated day**, one day every `SECONDS_PER_DAY` seconds (a `#define`, default 10, the same pace as the generator). | Baselines, trends and multi-day patterns all count in days. |
| 3 | **Labs only every 7th day** (days 0, 7, 14, …): `lymphocytes_per_ul`, `il6_pg_ml`, `nk_activity_pct`, `viral_pcr_positive`. Other days print only HR, RMSSD and CO₂. | `signals.yaml` gives labs `interval_days: 7`. The lab baseline is the first 28 days and expects 4 samples, not 28. |
| 4 | **Pulse `ON` off = no HR and RMSSD lines** that day (unchanged). The day counter still advances. | The core marks a signal `stale` once its last reading is more than 1.5 days old; a 0 would count as a real reading. |
| 5 | **Signal names exactly as in `contract/signals.yaml`**, values finite numbers (unchanged). | Anything else is rejected and dropped. |
| 6 | **`source: "wokwi"`, `provenance: "simulated"`** on every line (unchanged). | NFR-11: simulated data must say so. |
| 7 | **`crew_id` stays a `#define`; use `cm2`.** | The generator publishes every signal for `cm1`, and each signal of a crew member must come from one publisher only. |
| 8 | **Any other Serial text starts with `#`** (e.g. `# day 7`). | `validate_serial.py` skips `#` lines; anything else that is not a message counts as an error. |

Example, days 6 to 8 (day 7 is a lab day):

```
{"crew_id":"cm2","ts":"2026-11-20T10:00:00Z","signal":"resting_hr_bpm","value":60.0,...}
{"crew_id":"cm2","ts":"2026-11-20T10:00:00Z","signal":"rmssd_ms","value":55.0,...}
{"crew_id":"cm2","ts":"2026-11-20T10:00:00Z","signal":"cabin_co2_mmhg","value":2.20,...}
{"crew_id":"cm2","ts":"2026-11-21T10:00:00Z","signal":"resting_hr_bpm","value":60.0,...}
{"crew_id":"cm2","ts":"2026-11-21T10:00:00Z","signal":"rmssd_ms","value":55.0,...}
{"crew_id":"cm2","ts":"2026-11-21T10:00:00Z","signal":"cabin_co2_mmhg","value":2.20,...}
{"crew_id":"cm2","ts":"2026-11-21T10:00:00Z","signal":"lymphocytes_per_ul","value":2680,...}
{"crew_id":"cm2","ts":"2026-11-21T10:00:00Z","signal":"il6_pg_ml","value":3.7,...}
{"crew_id":"cm2","ts":"2026-11-21T10:00:00Z","signal":"nk_activity_pct","value":100.0,...}
{"crew_id":"cm2","ts":"2026-11-21T10:00:00Z","signal":"viral_pcr_positive","value":0,...}
{"crew_id":"cm2","ts":"2026-11-22T10:00:00Z","signal":"resting_hr_bpm","value":60.0,...}
...
```

### 5.2 What this means when using the sliders

- The core takes each person's baseline from their **first 14 days** (28 for labs) and keeps it. So
  leave the sliders at their defaults for the first 14 days (28 if the demo uses labs), and move them
  only after that: at 10 s per day that is about 2.5 minutes (5 for labs).
- A restart begins again at day 0. That is fine; the backend side clears the crew member before a run.

### 5.3 Done when (phase 2)

- [ ] `ts` goes up by exactly one day per cycle, starting at `2026-11-14T10:00:00Z`
- [ ] Lab lines appear on days 0, 7, 14, … only; HR, RMSSD and CO₂ every day
- [ ] Pulse `ON` off: HR and RMSSD lines stop, the day still advances, the other lines continue
- [ ] `crew_id` is `cm2`; changing `SECONDS_PER_DAY` changes the pace and nothing else
- [ ] A capture of at least 30 days passes `firmware/tools/validate_serial.py`

## Later (separate work, not now)

- **Connecting to the backend:** sending each line over MQTT to `aura/<crew_id>/<group>` (`vitals`,
  `cabin`, `labs`). Nothing in phase 2 needs to prepare for it beyond the rules above.
- **Realistic values:** day-to-day noise around the slider value. Until then a still slider gives a
  baseline with no spread, so the backend can band the signal but not give it a z-score. The numbers
  to use come from the data side (`contract/signals.yaml`).
- **Scenarios:** sliders only, or scripted runs matching the generator's.
