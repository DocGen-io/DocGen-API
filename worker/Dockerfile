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
COPY worker/pyproject.toml worker/pyproject.toml

# Copy the full project source (pipelines, components, prompts, shared)
COPY src/ src/
COPY shared/ shared/
COPY worker/ worker/
COPY prompts/ prompts/
COPY config.yaml config.yaml
COPY queries/ queries/

# Install worker dependencies
RUN cd worker && uv sync --no-dev --no-install-project

# Start Celery worker
CMD ["uv", "run", "--directory", "worker", "celery", "-A", "worker.celery_app", "worker", "--loglevel=info", "--concurrency=2"]
