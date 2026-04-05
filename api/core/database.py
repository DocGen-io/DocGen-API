from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from api.core.config import settings

# Create async engine for SQLAlchemy
engine = create_async_engine(
    settings.async_database_uri,
    echo=False,
    future=True,
    pool_size=20,
    max_overflow=10
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    """
    Dependency function to yield database sessions.
    """
    async with AsyncSessionLocal() as session:
        yield session
