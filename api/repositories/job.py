from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from shared.models import GenerationJob, JobStatus
from api.repositories.base import BaseRepository
from api.schemas.job import JobCreate
from shared.models import JobLog


class JobRepository(BaseRepository[GenerationJob, JobCreate, JobCreate]):

    def __init__(self):
        super().__init__(GenerationJob)

    async def get_by_team(self, db: AsyncSession, team_id: str) -> List[GenerationJob]:
        result = await db.execute(
            select(self.model)
            .where(self.model.team_id == team_id)
            .order_by(self.model.created_at.desc())
        )
        return result.scalars().all()  # type: ignore

    async def create_job(
        self, db: AsyncSession, *, team_id: str, submitted_by: str, obj_in: JobCreate
    ) -> GenerationJob:
        db_obj = GenerationJob(
            team_id=team_id,
            submitted_by=submitted_by,
            source_type=obj_in.source_type,
            path=obj_in.path,
            credentials=obj_in.credentials,
            api_dir=obj_in.api_dir,
            status=JobStatus.PENDING,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    
    async def get_job_logs(self, job_id: str) -> list:
      
        stmt = select(JobLog).filter(JobLog.job_id == job_id).order_by(JobLog.timestamp.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())



job_repo = JobRepository()
