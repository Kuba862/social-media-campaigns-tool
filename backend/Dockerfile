# Temporal worker image for Cloud Run (guide section 1). Build context: backend/.
# Stage 1 resolves dependencies with uv from the lockfile; stage 2 is a slim runtime.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev
COPY . .

FROM python:3.12-slim-bookworm
WORKDIR /app
RUN useradd --create-home --uid 1000 worker
COPY --from=build --chown=worker:worker /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER worker
# Configuration comes from the environment (guide section 10); secrets from Secret Manager.
CMD ["python", "-m", "worker.main"]
