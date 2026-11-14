# AURA-Bio web console

Static HTML/CSS/JS served by the core service (no server of its own). Everything it shows comes from the core:
`/crew/cm1/status` and the WebSocket `/ws` (readings, personal baselines, bands, alerts, anomaly and immune-risk
scores), `/crew/<id>/signal/<name>` (trend history), `/crew/overview` (crew roster), `/mission` (presets),
`/checkin` and `/scenario/<name>` (demo replay). The mapping from the core's status to what the UI draws is the
adapter at the top of `static/app.js`; signal names are the contract's (`contract/signals.yaml`).

```bash
uv run uvicorn core.app:app --port 8000      # from the repo root
```
Open http://localhost:8000 and pick a scenario (each replays the demo astronaut, seed 12, at 10 s per day;
`POST /scenario/<name>?speed=0.5` for a faster run). All crew data is simulated; not a medical device.
