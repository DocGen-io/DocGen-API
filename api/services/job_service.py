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
import os
from api.models.project import Project
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
        # Ensure Project record exists in the database
       
        
        # Determine project name once and persist it in the job
        project_name = job_in.project_name or  "default"
        job_in.project_name = project_name

        job = await job_repo.create_job(
            self.db,
            team_id=team_id,
            submitted_by=submitted_by,
            obj_in=job_in,
        )
        
        # Check if project exists
        stmt = select(Project).where(Project.team_id == team_id, Project.name == project_name)
        result = await self.db.execute(stmt)
        existing_project = result.scalars().first()
        
        if not existing_project:
            new_project = Project(
                name=project_name,
                team_id=team_id,
                source_type=job.source_type,
                path=job.path
            )
            self.db.add(new_project)
            await self.db.commit()
            await self.db.refresh(new_project)

        # Fire-and-forget: dispatch to the worker via Redis
        _celery_client.send_task(
            "worker.tasks.run_documentation_pipeline",
            kwargs={
                "job_id": job.id,
                "project_name": job.project_name,
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
