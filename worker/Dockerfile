# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app
ENV UV_PROJECT_ENVIRONMENT=/app/.venv

# ── System deps ──────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -u 1000 -m -s /bin/bash docgen

# ── uv ───────────────────────────────────────────────────────────────────────
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh

# ── Dependencies (cached unless pyproject.toml / uv.lock change) ─────────────
# Copy ONLY the manifest first so Docker can cache this expensive layer.
COPY DocGen-API/worker/pyproject.toml worker/pyproject.toml
COPY DocGen-API/worker/uv.lock        worker/uv.lock

# BuildKit cache mount: reuses the uv download cache across rebuilds.
# Deps are only re-downloaded if uv.lock actually changes.
RUN --mount=type=cache,target=/root/.cache/uv \
    cd worker && uv sync --no-dev --no-install-project --frozen

# ── Source code (invalidates cache on every .py change, but deps are cached) ─
COPY DocGen-RAG/src/        src/
COPY DocGen-API/api/        api/
COPY DocGen-RAG/prompts/    prompts/
COPY DocGen-RAG/config.yaml config.yaml
COPY DocGen-RAG/queries/    queries/
COPY DocGen-API/shared/     shared/
COPY DocGen-API/worker/     worker/

RUN chown -R docgen:docgen /app

USER docgen

# ── Entrypoint ────────────────────────────────────────────────────────────────
CMD ["uv", "run", "--project", "worker", \
     "watchmedo", "auto-restart", \
     "--directory=/app/src", \
     "--directory=/app/api", \
     "--directory=/app/worker", \
     "--directory=/app/shared", \
     "--pattern=*.py", \
     "--recursive", \
     "--", \
     "celery", "-A", "worker.celery_app", "worker", \
     "--loglevel=info", "--concurrency=2"]