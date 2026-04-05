import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.api.routers import auth_router, team_config_router, prompt_router, team_router, jobs_router, revisions_router
from api.core.config import settings
from api.core.database import engine, AsyncSessionLocal
from api.core.init_db import seed_system_prompts

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info("Starting up DocGen SaaS API...")
    async with AsyncSessionLocal() as session:
        await seed_system_prompts(session)
    yield
    # Shutdown actions
    logger.info("Shutting down DocGen SaaS API...")
    await engine.dispose()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "docgen-saas-core"}

app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(team_router, prefix=settings.API_V1_STR)
app.include_router(team_config_router, prefix=settings.API_V1_STR)
app.include_router(prompt_router, prefix=settings.API_V1_STR)
app.include_router(jobs_router, prefix=settings.API_V1_STR)
app.include_router(revisions_router, prefix=settings.API_V1_STR)
