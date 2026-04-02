"""
Worker-specific settings loaded from environment variables.
"""
from pydantic_settings import BaseSettings


class WorkerSettings(BaseSettings):
    REDIS_URL: str = "redis://localhost:6379/0"
    DATABASE_URL: str = "postgresql://docgen:docgen_password@localhost:5432/docgen_saas"
    WEAVIATE_URL: str = "http://localhost:8080"

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = WorkerSettings()
