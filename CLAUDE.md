# AURA-Bio

Astronaut health monitoring for NASA Space Apps 2026 (48-h build, Nov 14–15). Scores each crew
member against their own baseline and alerts on cross-system patterns. The full plan is the team's
"AURA-Bio software plan" PDF; section refs below (e.g. "plan 4.3") point into it.

This repo holds the **data + model** workstream, the **core service** (backend) and the **web console** (`web/`, replaces
the plan's Flutter app). The integrated branch also includes `firmware/`, narrowly ported from the `hardware` branch without its older UI.

## Layout
- `contract/` — shared contract, changed only by team agreement. `signals.yaml` (names include
  units; `model: true` + order = autoencoder input vector), `schema.py` (`Reading` message, topics
  `aura/<crew_id>/<group>`).
- `contract/presets.yaml` — mission presets (dose level, quality factor, delay).
- `contract/thresholds.yaml` — amber/red rules per signal, cross-system `patterns` (research doc 7, with responses and citations), `baseline_days`,
  stale rule. Every number is from the research doc or a recorded team choice; the header lists what is not covered yet.
- `core/` — core service (plan 3.5): `domain.py` (all health logic, pure: bands, patterns, responses, cumulative dose,
  immune-risk score, check-in scoring, model window), `store.py` (SQLite), `model_client.py` (calls `/score`; down = `anomaly.available: false`),
  `app.py` (MQTT ingest of `aura/+/+`; REST `/health`, `/crew`, `/crew/<id>/status`, `/crew/<id>/signal/<name>?days=` trend, `/crew/<id>/timeline`,
  `GET/PUT /mission` preset, `POST /checkin` (raw `reaction_times_ms`, `mood_answers` or signal `values`; `ts` optional, default = the crew member's newest reading, i.e. the current simulated day), `DELETE /crew/<id>`
  demo reset, `/crew/overview` (FR-17), `POST /alerts/<id>/ack`, `/ground/reports` (FR-16: released after the preset's one-way
  delay, wall clock); WebSocket `/ws` pushes the full status). Layers as plan 3.5: app -> domain + store/model_client; the
  store never calls the domain. Tables follow the plan's data view: mission, crew_member, reading, baseline (saved once its
  window has passed: daily signals `baseline_days` 14, weekly labs `lab_baseline_days` 28), alert (per episode of a pattern,
  or of a signal red by a *published* threshold; stays until acknowledged), report; invalid messages go to `reject`.
  No migrations: after a schema change delete `core.db` (or `docker compose down -v`).
- `web/static/` — web console, served by the core at `/` (no server or build step of its own). Redesigned 2026-11-14 as a
  "flight plan timeline" (direction contract: `.impeccable/surfaces/web-static-index-html.md`; product brief: `PRODUCT.md`):
  status sentence on top, one lane per body system over mission days from `GET /crew/<id>/timeline` (per-day system bands
  and alert episodes, computed in the core), views for signals, check-in, crew and ground reports. `app.js` reads the
  core's JSON directly; it computes no bands. Demo replay sits in the Mission dialog (`POST /scenario/<name>?speed=`).
- `docs/model-handover.md` — start here if you work on the model: what the data can and can't tell it.
- `data/SOURCES.md` — dataset list; raw downloads in `data/raw/` (committed so clones work offline; regenerate with `data/fetch.py`).
- `artifacts/` — trained model (git-ignored; regenerate with `model.train`).

`hardware/bridge.py` connects Serial output from `firmware/` to the existing MQTT bus.
It validates and forwards simulated Wokwi messages unchanged with QoS 1; see `hardware/README.md` for file, stdin,
and optional serial-port input (`uv sync --group hardware`). It never fills missing sensor readings.

## Commands
Python is pinned <3.14 (torch); uv picks 3.12. Torch comes from the CPU wheel index.
If a foreign `VIRTUAL_ENV` is exported in your shell, `unset VIRTUAL_ENV` first.
- `uv sync` · `uv run pytest -q`
- `uv run python -m model.train` — trains the 3 models, then reports detection rate, days to detection and false alarms over 200 simulated astronauts per scenario
- `uv run python data/process.py` — raw data to `data/processed/`
- `uv run python data/validate.py` — simulator vs the real data (also run by `tests/test_validation.py`)
- `uv run uvicorn model.service:app --port 8001`
- `uv run uvicorn core.app:app --port 8000` — core service (env `AURA_DB`, `AURA_MQTT_HOST`, `AURA_MQTT_PORT`, `AURA_MODEL_URL`); works without a broker or model.
  Run one core per broker: every core connects as MQTT client `aura-core`, so a second one (e.g. local + compose)
  keeps disconnecting the first and readings split between two databases
- `docker compose up --build` — broker :1883, core :8000, model :8001 (needs `artifacts/`)
- `uv run python -m generator.publish --scenario sleep_debt --crew cm1 --speed 10` (needs a broker on :1883); add `--replay [--co2-source RR-5|RR-3|stitched]` and `--preset` for the demo;
  use `--seed 12` (tests pin it: normal raises nothing, each scenario raises only its own pattern)
- Data decisions (cleaning rules, cut-offs, calibration values, scenario sizes) are the user's call: show the numbers and ask first.

## Rules
- All crew data is simulated and must carry `provenance: simulated`; never present it as real (NFR-11).
- Model output is a "research concept, not validated on crew data"; no diagnostic wording (NFR-10).
- Thresholds/patterns belong in config files, not code (NFR-12); cite source + published/proposed tag.
- `/score` takes baseline-normalised z-scores; the core service owns baselines.
