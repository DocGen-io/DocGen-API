# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV WORKDIR=/app
ENV PYTHONPATH=${WORKDIR}
ENV UV_PROJECT_ENVIRONMENT=${WORKDIR}/.venv
ENV PATH="$UV_PROJECT_ENVIRONMENT/bin:$PATH"

# ── System deps ──────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -u 1000 -m -s /bin/bash docgen && \
    mkdir -p ${WORKDIR} && chown docgen:docgen ${WORKDIR}

# ── uv ───────────────────────────────────────────────────────────────────────
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh

# Switch user early so that `.venv` is strictly created and owned by docgen
USER docgen

# ── Dependencies (cached unless pyproject.toml / uv.lock change) ─────────────
# Copy ONLY the manifest first so Docker can cache this expensive layer.
COPY --chown=docgen:docgen DocGen-API/worker/pyproject.toml worker/pyproject.toml
COPY --chown=docgen:docgen DocGen-API/worker/uv.lock        worker/uv.lock

# BuildKit cache mount: reuses the uv download cache across rebuilds.
# Deps are only re-downloaded if uv.lock actually changes.
RUN --mount=type=cache,target=/home/docgen/.cache/uv,uid=1000,gid=1000 \
    echo 'Busting root cache' && cd worker && uv sync --no-dev --no-install-project --frozen

# ── Source code (invalidates cache on every .py change, but deps are cached) ─
COPY --chown=docgen:docgen DocGen-RAG/src/        src/
COPY --chown=docgen:docgen DocGen-API/api/        api/
COPY --chown=docgen:docgen DocGen-RAG/prompts/    prompts/
COPY --chown=docgen:docgen DocGen-RAG/config.yaml config.yaml
COPY --chown=docgen:docgen DocGen-RAG/queries/    queries/
COPY --chown=docgen:docgen DocGen-API/shared/     shared/
COPY --chown=docgen:docgen DocGen-API/worker/     worker/

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