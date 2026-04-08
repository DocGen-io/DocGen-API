"""
Job Service — creates persistent job records and dispatches Celery tasks.

The SaaS API never imports the DocumentationPipeline directly.
It only sends a message to Redis via celery_app.send_task().
"""
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from celery import Celery

from shared.models import GenerationJob
from api.schemas.job import JobCreate
from api.repositories.job import job_repo
from api.core.config import settings

from sqlalchemy import select
from shared.models import JobLog
# Lightweight Celery client — only used to dispatch tasks, NOT to run them.
# This connects to the same Redis broker the worker listens on.
_celery_client = Celery(
    "docgen_dispatcher",
    broker=settings.REDIS_URL,
)


class JobService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit_job(self, team_id: str, submitted_by: str, job_in: JobCreate) -> GenerationJob:
        """Create a job record in PostgreSQL and dispatch it to the Celery worker."""
        job = await job_repo.create_job(
            self.db,
            team_id=team_id,
            submitted_by=submitted_by,
            obj_in=job_in,
        )

        # Fire-and-forget: dispatch to the worker via Redis
        _celery_client.send_task(
            "worker.tasks.run_documentation_pipeline",
            kwargs={
                "job_id": job.id,
                "source_type": job.source_type,
                "path": job.path,
                "credentials": job.credentials,
                "api_dir": job.api_dir,
            },
        )

        return job

    async def get_job(self, job_id: str) -> GenerationJob | None:
        return await job_repo.get(self.db, job_id)

    async def get_job_logs(self, job_id: str) -> list:
        return await job_repo.get_job_logs(self.db, job_id)

    async def list_team_jobs(self, team_id: str) -> List[GenerationJob]:
        return await job_repo.get_by_team(self.db, team_id)
