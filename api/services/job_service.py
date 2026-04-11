"""
Job Service — creates persistent job records and dispatches Celery tasks.

The SaaS API never imports the DocumentationPipeline directly.
It only sends a message to Redis via celery_app.send_task().
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import GenerationJob
from api.schemas.job import JobCreate
from api.repositories.job import job_repo
from api.core.config import settings
import os
from api.models.project import Project
from sqlalchemy import select
from shared.models import JobLog
from api.core.celery_client import celery_client


class JobService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit_job(self, team_id: str, submitted_by: str, job_in: JobCreate) -> GenerationJob:
        """Create a job record in PostgreSQL and dispatch it to the Celery worker."""

        # Determine project name once and persist it in the job
        # Determine project name robustly
        project_name = job_in.project_name
        if not project_name:
            if job_in.path:
                # Get the last non-empty part of the path
                path_parts = [p for p in job_in.path.split("/") if p]
                project_name = path_parts[-1] if path_parts else "default"
                # Remove .git suffix if present
                if project_name.endswith(".git"):
                    project_name = project_name[:-4]
            else:
                project_name = "default"
        
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
        celery_client.send_task(
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

    async def submit_task(
        self, 
        team_id: str, 
        submitted_by: str, 
        task_name: str, 
        task_kwargs: dict, 
        source_type: str, 
        path: str, 
        project_name: Optional[str] = None
    ) -> GenerationJob:
        """
        Generic method to create a job and dispatch a specific task to the worker.
        Centralizes Celery interaction in the service layer.
        """
        job = await job_repo.create_job(
            self.db,
            team_id=team_id,
            submitted_by=submitted_by,
            obj_in=JobCreate(
                source_type=source_type,
                path=path,
                project_name=project_name or path
            )
        )
        
        # Dispatch to worker
        celery_client.send_task(
            task_name,
            kwargs={
                "job_id": job.id,
                **task_kwargs
            }
        )

        return job

    async def get_job(self, job_id: str) -> GenerationJob | None:
        return await job_repo.get(self.db, job_id)

    async def get_job_logs(self, job_id: str) -> list:
        return await job_repo.get_job_logs(self.db, job_id)

    async def list_team_jobs(self, team_id: str) -> List[GenerationJob]:
        return await job_repo.get_by_team(self.db, team_id)
