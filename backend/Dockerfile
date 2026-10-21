# Temporal worker image for Cloud Run (guide section 1). Build context: backend/.
# Stage 1 resolves dependencies with uv from the lockfile; stage 2 fetches the Temporal CLI, whose
# `server start-dev` serves as the PoC's embedded engine (decision 43); stage 3 is a slim runtime.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev
COPY . .

FROM python:3.12-slim-bookworm AS temporal-cli
ARG TARGETARCH
ARG TEMPORAL_CLI_VERSION=1.9.1
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /out \
    && curl -fsSL "https://temporal.download/cli/archive/v${TEMPORAL_CLI_VERSION}?platform=linux&arch=${TARGETARCH}" \
       | tar -xz -C /out temporal

FROM python:3.12-slim-bookworm
WORKDIR /app
RUN useradd --create-home --uid 1000 worker
COPY --from=build --chown=worker:worker /app /app
COPY --from=temporal-cli /out/temporal /usr/local/bin/temporal
COPY --chmod=755 docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER worker
# Configuration comes from the environment (guide section 10); secrets from Secret Manager.
# TEMPORAL_EMBEDDED=true starts `temporal server start-dev` inside the container first.
ENTRYPOINT ["docker-entrypoint.sh"]
