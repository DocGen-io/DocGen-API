from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "DocGen-RAG SaaS"
    API_V1_STR: str = "/api/v1"
    
    # Auth
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    
    # PostgreSQL
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "docgen"
    POSTGRES_PASSWORD: str = "docgen_password"
    POSTGRES_DB: str = "docgen_saas"
    POSTGRES_PORT: int = 5432
    
    # Redis Queue
    REDIS_URL: str = "redis://localhost:6379/0"

    # Encryption (Fernet needs 32-byte url-safe base64 key)
    # Default generated for dev via `Fernet.generate_key()`
    ENCRYPTION_KEY: str = "gTjRQ7I2G_Bv-b81b8k7qf3M3VzX_-AawS0bB3Z9Z0A="

    @property
    def sync_database_uri(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        
    @property
    def async_database_uri(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore"
    }

settings = Settings()
