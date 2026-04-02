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

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies using uv sync
RUN uv sync --no-dev --no-install-project

# Copy project files
COPY . .

EXPOSE 8000

# Start FastAPI server
CMD ["uv", "run", "uvicorn", "src.saas_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
