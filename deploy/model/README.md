# Model service image

Container for `model.service:app` (plan 3.7): the two-detector anomaly model behind `POST /score` and
`GET /health` on port **8001**. It is a separate container on purpose (NFR-4): if the model crashes, the
core's rule-based alerts keep running; the core shows the score as unavailable and retries.

The image contains the code, the CPU-only Python environment and the trained artifacts. It has no data
pipeline, no broker and no database: it scores one astronaut-day per request and keeps nothing.

## Quick start

Prerequisites: Docker (with Compose for the Compose path) and [uv](https://docs.astral.sh/uv/) for
`build.sh` (it trains the artifacts). Training happens on the host, not in the image.

```bash
# from the repo root
deploy/model/build.sh                     # trains artifacts/ if missing (~25 s), then docker build
docker run --rm -p 8001:8001 --read-only --tmpfs /tmp aura-bio/model:local
curl -s localhost:8001/health
```

Or with Compose, from this directory:

```bash
docker compose up --build -d
docker compose logs -f model
docker compose down
```

`build.sh` accepts a tag: `deploy/model/build.sh ghcr.io/<org>/aura-model:1.0`.

To publish for the team:

```bash
deploy/model/build.sh ghcr.io/seifelgendy-eg/aura-model:1.0
docker push ghcr.io/seifelgendy-eg/aura-model:1.0
```

Then `docker compose` on another machine only needs `image: ghcr.io/seifelgendy-eg/aura-model:1.0`
(after `docker login ghcr.io` if the package is private).

## Build details

`artifacts/` is git-ignored, so the image is built **after** training. `build.sh` runs
`uv run python -m model.train --seeds 1 --no-eval` if the two files are missing; `--no-eval` trains and
saves seed 0 (the reproducible seed used for the committed results) without the 74-scenario evaluation,
which takes 25 s instead of the full run. To bake a model trained differently, run `model.train` with
your own options first, then build; `/health` reports the hash of the exact files in the image.

The Dockerfile is deliberately two-stage:

| Stage | Why |
| --- | --- |
| `builder` (`ghcr.io/astral-sh/uv`) | Resolves the pinned `uv.lock` with `--frozen --no-dev`, compiles bytecode, and installs torch from the **CPU wheel index**. No CUDA: the model is a 32→6→32 MLP, so the CPU wheel keeps the image ~1.3 GB instead of several GB. |
| `runtime` (`python:3.12-slim-bookworm`) | Copies only the finished `.venv`, `contract/`, `generator/`, `model/` and `artifacts/`. No uv, compilers, raw data, web console or tests. Torch's `test/` and `include/` directories are removed (~170 MB); `torch/bin` is kept because torch imports `torch_shm_manager`. |

The build fails early, not at runtime, if dependencies do not import, an artifact is missing, or the
artifacts do not load together; it also prints the 12-character `model_version` into the build log.

## Runtime details

- **Non-root** (uid 10001, no shell, no home) and, in Compose, **read-only root filesystem** with a 64 MB
  `/tmp` tmpfs. The service only reads its baked artifacts.
- **Healthcheck** every 10 s. `/health` answers `200` even when the model failed to load (it reports
  `"status": "degraded"`), so the check reads the body and marks the container unhealthy on a broken model.
- **One uvicorn worker.** The model is ~11 KB; scoring is ~2 ms p50. A second worker would only duplicate
  the loaded model. Scale with replicas if that ever becomes the bottleneck.
- **Restart policy** `unless-stopped` (Compose). Measured restart to a healthy `/health` in this sandbox:
  about 4.5 s, inside the 10 s recoverability target (NFR-3).
- **Threads** pinned to 1 (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`) because the layers
  are tiny; this avoids oversubscription when several containers share a laptop during the demo.
- **No persistence.** State (baselines, history, rule alerts) belongs to the core service.

Measured in this sandbox (x86_64, 6 vCPU): image 1.34 GB, memory ~407 MB RSS, `/score` p50 2.1 ms /
p99 2.8 ms over 200 requests, cold start to healthy ~5 s.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `AURA_ARTIFACTS` | `/app/artifacts` | Directory holding `model_2d.pt` and `ewma.json`. Point it at a mounted volume to swap models without rebuilding. |
| `OMP_NUM_THREADS` etc. | `1` | BLAS threads; leave at 1 for this model. |

The service has no other settings; thresholds and harmful directions are read from `contract/signals.yaml`
and the trained files (NFR-12).

## Integrating with the core

The core calls `AURA_MODEL_URL` (backend default `http://model:8001`) from inside the team's Compose
network. Two options:

1. **Use this image** as the `model` service in the root `compose.yaml`: replace the shared `build:` with
   `image: aura-bio/model:local` (or `build: {context: ., dockerfile: deploy/model/Dockerfile}`) and drop
   the `./artifacts:/app/artifacts:ro` volume, because the artifacts are already inside. Keep the service
   name `model` and port `8001`.
2. **Keep the backend's shared image** (one image for core + model). It works too, but it mounts the host's
   `artifacts/` and therefore needs training on the host; this image is self-contained and hardened.

The core treats a `422` as "model down" for 10 s, so the service rejects bad windows (fewer than 3 or more
than 14 days, unknown signals, NaN/inf) instead of guessing. Missing signals are treated as baseline (0);
the core marks them stale separately.

## Updating the model

```bash
uv run python -m model.train              # full evaluation, writes artifacts/ (seed 0 is saved)
deploy/model/build.sh aura-bio/model:2    # new tag; /health shows a new model_version
```

Every stored score can be traced to the files that produced it through `model_version` (first 12 hex of a
SHA-256 over the artifacts). Rebuilding does not retrain: whatever is in `artifacts/` is what ships.

## Notes for merges and other platforms

- The root `.dockerignore` is an include-list shared with the backend's image. It already allows `core/`
  and `web/`, so a merge of the backend branch keeps both Dockerfiles working. If both branches edit the
  file, take the union of the allowed paths.
- The image targets `linux/amd64`. On Apple Silicon, Docker builds/runs it through emulation; for native
  arm64, check that the pinned torch CPU wheel has an `aarch64` wheel in `uv.lock` before building with
  `--platform linux/arm64`.
- Old Docker installs without BuildKit ignore the `# syntax=` line; the Dockerfile still builds with the
  legacy builder. If the daemon has no bridge network (some CI sandboxes), add `--network=host` to the
  build command.
