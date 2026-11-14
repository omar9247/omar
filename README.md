# AURA-Bio — data & model

NASA Space Apps 2026 · astronaut health monitoring. See `CLAUDE.md` for layout and commands.

```bash
uv sync && uv run pytest -q
uv run python -m model.train
uv run uvicorn model.service:app --port 8001
uv run uvicorn core.app:app --port 8000
```

For the full Docker stack on a fresh clone:

```bash
deploy/model/build.sh
docker compose up --build
```

The model build script trains the default artifacts only when missing; it does not pull a
pre-existing registry image. Root Compose uses the baked `aura-bio/model:local` image, without
a host artifact mount, with read-only runtime settings. For the model alone:

```bash
docker run --rm -p 8001:8001 --read-only --tmpfs /tmp aura-bio/model:local
```

See [`deploy/model/README.md`](deploy/model/README.md) and
[`docs/model-integration.md`](docs/model-integration.md) for the staged version,
model-down behavior and no-arbitrary-tuning boundary.

For Wokwi/ESP32 Serial → the existing MQTT bus → core → web console, see
[`hardware/README.md`](hardware/README.md). Start just `broker core` to connect hardware
without trained model artifacts.

The optional Check-in games save bounded raw sessions for the selected crew, separately
from health readings and anomaly input. See
[`web/static/lunar-arcade-hub/README.md`](web/static/lunar-arcade-hub/README.md)
for launch, storage, visible manual retry and reproducible bundle rebuild instructions.
