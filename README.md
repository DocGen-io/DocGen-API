# DocGen API

FastAPI SaaS backend for the DocGen documentation generation platform.

## Architecture

- **`src/saas_api/`** — FastAPI application (routers, services, repositories, models, migrations)
- **`worker/`** — Celery background worker for running documentation pipelines
- **`shared/`** — Shared models between API and Worker (e.g., GenerationJob)
- **`tests/`** — Test suite

## Quick Start

```bash
# Start all services (API + Postgres + Redis + Worker)
docker compose up --build

# Or run the API locally
uv sync
uv run uvicorn src.saas_api.main:app --reload --port 8000
```

## API Endpoints

- `GET /health` — Health check
- `POST /api/v1/auth/register` — Register user
- `POST /api/v1/auth/login` — Login
- `GET /api/v1/teams` — List teams
- `POST /api/v1/jobs` — Submit documentation generation job

## Full Stack

To run with the full DocGen platform (including the RAG pipeline), use the root-level `docker-compose.yaml` in the parent `DocGen/` directory.
