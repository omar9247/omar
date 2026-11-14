FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends mosquitto \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-cache
ENV PATH=/app/.venv/bin:$PATH \
    AURA_PUBLIC_DEMO=1 \
    AURA_DB=/tmp/aura-demo/core.db \
    AURA_MQTT_HOST=127.0.0.1 \
    AURA_MQTT_PORT=1883 \
    AURA_MODEL_URL=http://127.0.0.1:8001 \
    AURA_ARTIFACTS=/app/artifacts \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    PYTHONUNBUFFERED=1
COPY contract contract
COPY core core
COPY model model
COPY generator generator
COPY web/static web/static
COPY deploy/render/model-artifacts artifacts
COPY deploy/render/seed_demo.py seed_demo.py
COPY deploy/render/start_free_demo.sh start_free_demo.sh
COPY deploy/render/free-mosquitto.conf /app/mosquitto.conf
EXPOSE 10000
CMD ["sh", "/app/start_free_demo.sh"]
