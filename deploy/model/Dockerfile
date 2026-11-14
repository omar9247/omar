# syntax=docker/dockerfile:1.7
# AURA-Bio anomaly-model service (plan 3.7, NFR-3/NFR-4). One image, one process: /score + /health on 8001.
#
# Build from the REPO ROOT (artifacts/ are git-ignored and must be trained first):
#   uv run python -m model.train --seeds 1 --no-eval      # ~25 s, writes artifacts/
#   docker build -f deploy/model/Dockerfile -t aura-bio/model:local .
# or just: deploy/model/build.sh
#
# Why the two stages: the builder carries uv and the PyPI/PyTorch-CPU wheels; the runtime only carries the
# finished virtualenv, the code the service imports and the trained files. No compilers, no uv, no data/.

ARG PYTHON=3.12

FROM ghcr.io/astral-sh/uv:python${PYTHON}-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependency layer first: source edits rebuild in seconds. uv.lock pins torch to the CPU wheel index,
# so the image never pulls CUDA (~2 GB); the model is a 32-6-32 MLP, CPU is the right target.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:${PYTHON}-slim-bookworm AS runtime
# Tiny linear layers: one BLAS thread avoids oversubscription and keeps p99 latency flat.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PATH=/app/.venv/bin:$PATH \
    VIRTUAL_ENV=/app/.venv \
    HOME=/tmp \
    AURA_ARTIFACTS=/app/artifacts \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1
WORKDIR /app
LABEL org.opencontainers.image.title="AURA-Bio anomaly model service" \
      org.opencontainers.image.description="Two-detector astronaut anomaly scoring: 2-day autoencoder + one-sided EWMA (plan 4.3)" \
      org.opencontainers.image.source="https://github.com/SeifElgendy-eg/Aura-bio"

# Non-root, no home, no shell: the service only reads files.
RUN groupadd --system --gid 10001 aura \
 && useradd --system --uid 10001 --gid aura --no-create-home --shell /usr/sbin/nologin aura

COPY --from=builder /app/.venv /app/.venv
# Inference never compiles C++ extensions or runs the torch test suite: drop ~170 MB of headers and
# tests that the CPU wheel ships. Keep torch/bin: torch imports torch_shm_manager from there.
RUN rm -rf /app/.venv/lib/python3.12/site-packages/torch/test \
           /app/.venv/lib/python3.12/site-packages/torch/include
# Only what model.service imports at runtime: contract/ (signals), generator/sim (constants + scenario
# definitions used by dataset.py), model/, artifacts/. No data/raw, web/ or tests/ in the image.
COPY contract ./contract
COPY generator ./generator
COPY model ./model
ARG AURA_ARTIFACTS_BUILD=artifacts
COPY ${AURA_ARTIFACTS_BUILD} ./artifacts

# Fail the build, not the container, on a broken image: deps import, trained files exist and load,
# and the model version is printed into the build log (traceability for every stored score).
RUN python -c "import torch, fastapi, uvicorn, numpy, pandas, yaml, scipy, pydantic" \
 && test -f artifacts/model_2d.pt \
 && test -f artifacts/ewma.json \
 && python -c "from model.service import _load; print('model_version', _load()['version'])"

USER aura
EXPOSE 8001

# /health reports 200 even when degraded (so the core can distinguish "up but broken" from "down"),
# so check the body, not just the status code.
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import json, sys, urllib.request; d = json.load(urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=2)); sys.exit(0 if d.get('status') == 'ok' else 1)"

# One worker: the model is ~11 KB and scoring is ~2 ms, so a second process would only duplicate the
# loaded artifacts and split the tiny workload. Scale with replicas behind the core if that ever changes.
CMD ["uvicorn", "model.service:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1", "--no-server-header"]
