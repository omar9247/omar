# Core image; the model uses deploy/model/Dockerfile.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
# generator is needed by model.dataset
COPY contract contract
COPY core core
COPY model model
COPY generator generator
COPY web/static web/static
COPY deploy/render/seed_demo.py seed_demo.py
ENV PATH=/app/.venv/bin:$PATH
