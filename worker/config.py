"""
Worker-specific settings loaded from environment variables.
"""
from pydantic_settings import BaseSettings


class WorkerSettings(BaseSettings):
    REDIS_URL: str
    DATABASE_URL: str
    WEAVIATE_URL: str = "http://localhost:8080"

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = WorkerSettings()
