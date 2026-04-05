# DocGen API

FastAPI SaaS backend for the DocGen documentation generation platform — multi-tenant, JWT-authenticated, with Celery workers and real-time log streaming.

## Architecture

```
DocGen-API/
├── api/
│   ├── api/
│   │   ├── routers/       # REST + WebSocket endpoints
│   │   └── dependencies.py # Auth guards (RBAC)
│   ├── core/              # Config, database, security
│   ├── models/            # SQLAlchemy models
│   ├── schemas/           # Pydantic request/response schemas
│   ├── services/          # Business logic
│   ├── repositories/      # Data access layer
│   └── migrations/        # Alembic migrations
├── worker/
│   ├── celery_app.py      # Celery config
│   ├── tasks.py           # Background tasks
│   ├── redis_log_handler.py # Pub/Sub log streaming
│   └── tracing.py         # Phoenix/OpenTelemetry
├── shared/                # Models shared with worker
└── tests/                 # E2E test suite
```

---

## Running Locally (without Docker)

### Prerequisites

- Python 3.10+
- [`uv`](https://docs.astral.sh/uv/) package manager
- PostgreSQL running on localhost:5432
- Redis running on localhost:6379

### 1. Install dependencies

```bash
cd DocGen-API
uv sync
```

### 2. Set environment variables

```bash
export POSTGRES_SERVER=localhost
export POSTGRES_USER=docgen
export POSTGRES_PASSWORD=docgen_password
export POSTGRES_DB=docgen_saas
export REDIS_URL=redis://localhost:6379/0
```

### 3. Run database migrations

```bash
uv run alembic upgrade head
```

### 4. Start the API server

```bash
uv run uvicorn api.main:app --reload --port 8000
```

---

## Running with Docker

See the [root README](../README.md) for full Docker instructions. Quick reference:

```bash
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# From the root DocGen/ directory:
docker compose up --build
```

---

## Running Tests

Tests run against a **live** API and database (not mocked).

### Prerequisites

```bash
# Start infra
docker compose up postgres redis -d

# Install test deps
cd DocGen-API
uv sync --group dev
```

### Run all tests

```bash
PYTHONPATH=".:../DocGen-RAG" \
DATABASE_URL="postgresql+asyncpg://docgen:docgen_password@localhost:5432/docgen_saas" \
uv run pytest tests/saas_api/ -v
```

### Run specific test suites

```bash
# Team management tests (13 scenarios)
PYTHONPATH=".:../DocGen-RAG" \
DATABASE_URL="postgresql+asyncpg://docgen:docgen_password@localhost:5432/docgen_saas" \
uv run pytest tests/saas_api/test_teams.py -v

# Log streaming + regression tests (7 scenarios)
PYTHONPATH=".:../DocGen-RAG" \
DATABASE_URL="postgresql+asyncpg://docgen:docgen_password@localhost:5432/docgen_saas" \
uv run pytest tests/saas_api/test_logs.py -v
```

---

## API Endpoints

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register a new user |
| POST | `/api/v1/auth/token` | Login (OAuth2 password flow) |

### Teams
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/teams/` | Create a new team |
| GET | `/api/v1/teams/me` | List your teams |
| GET | `/api/v1/teams/search?q=name` | Search public teams |
| POST | `/api/v1/teams/{id}/join` | Join via invite link |
| POST | `/api/v1/teams/{id}/request-join` | Request to join |
| POST | `/api/v1/teams/{id}/invite` | Admin sends invite |
| PUT | `/api/v1/teams/{id}/members/{uid}/role` | Change member role |
| DELETE | `/api/v1/teams/{id}/members/{uid}` | Remove member |
| POST | `/api/v1/teams/{id}/rotate-invite` | Rotate invite token |

### Jobs
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/jobs/` | Submit documentation generation job |
| GET | `/api/v1/jobs/{id}` | Get job status |

### Documentation Revisions
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/revisions/propose` | Propose a documentation edit |
| POST | `/api/v1/revisions/{id}/approve` | Approve revision (Admin/Maintainer) |
| POST | `/api/v1/revisions/{id}/reject` | Reject revision (Admin/Maintainer) |

### Log Streaming
| Method | Endpoint | Description |
|--------|----------|-------------|
| WS | `/ws/logs/{job_id}?token=JWT` | Real-time worker log stream |

### Tracing
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/traces/{job_id}` | Aggregated Phoenix trace data |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
