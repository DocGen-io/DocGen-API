"""
Synchronous SQLAlchemy engine for the Celery Worker.

The SaaS API uses async (asyncpg), but Celery tasks run in a synchronous
context, so the worker needs a standard psycopg2-based engine.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://docgen:docgen_password@localhost:5432/docgen_saas"
)

engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
