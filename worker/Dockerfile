FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (including git for GitPython)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh

# Copy worker dependency manifest
COPY DocGen-API/worker/pyproject.toml worker/pyproject.toml

# Copy DocGen-RAG pipeline source, prompts, config, and queries
COPY DocGen-RAG/src/ src/
# Overlay DocGen-API src (saas_api models needed by shared/)
COPY DocGen-API/src/ src/
COPY DocGen-RAG/prompts/ prompts/
COPY DocGen-RAG/config.yaml config.yaml
COPY DocGen-RAG/queries/ queries/

# Copy DocGen-API shared code and worker
COPY DocGen-API/shared/ shared/
COPY DocGen-API/worker/ worker/

# Install worker dependencies
RUN cd worker && uv sync --no-dev --no-install-project

# Start Celery worker
CMD ["uv", "run", "--directory", "worker", "celery", "-A", "worker.celery_app", "worker", "--loglevel=info", "--concurrency=2"]
