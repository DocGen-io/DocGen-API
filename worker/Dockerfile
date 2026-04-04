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

RUN cd worker && uv sync --no-dev --no-install-project --frozen

# ── Source code (invalidates cache on every .py change, but deps are cached) ─
# These directories are volume-mounted in dev, so this layer only matters for
# production builds or the initial image pull.
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
# watchmedo auto-restart: restarts `celery worker` whenever any .py file changes
# in the mounted source dirs. This makes `docker compose restart` unnecessary
# during development — just save a file and Celery reloads automatically.
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