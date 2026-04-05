# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for rapid dependency management
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh

# Copy dependency files first for cache isolation
COPY DocGen-API/pyproject.toml ./
COPY DocGen-API/uv.lock        ./

# Install dependencies using uv sync with BuildKit cache mount
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project --frozen

# Copy source files (cache-busted only by source changes, not dep changes)
COPY DocGen-API/api/    api/
COPY DocGen-API/shared/ shared/
COPY DocGen-API/alembic.ini alembic.ini

# Copy prompts from DocGen-RAG (used by init_db seeding)
COPY DocGen-RAG/prompts/ prompts/

EXPOSE 8000

# Start FastAPI server
CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
