from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.saas_api.core.database import get_db
from src.saas_api.api.dependencies import verify_team_membership, get_current_active_user
from src.saas_api.models.user import User
from src.saas_api.schemas.job import JobCreate, JobResponse
from src.saas_api.services.job_service import JobService

router = APIRouter(prefix="/teams/{team_id}/jobs", tags=["Jobs"])


def get_job_service(db: AsyncSession = Depends(get_db)) -> JobService:
    return JobService(db)


@router.post("/generate", response_model=JobResponse)
async def submit_generation_job(
    team_id: str,
    job_in: JobCreate,
    membership=Depends(verify_team_membership),
    current_user: User = Depends(get_current_active_user),
    job_service: JobService = Depends(get_job_service),
):
    """Submit a documentation generation job. Processing happens asynchronously via the Worker."""
    return await job_service.submit_job(
        team_id=team_id,
        submitted_by=current_user.id,
        job_in=job_in,
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_status(
    team_id: str,
    job_id: str,
    membership=Depends(verify_team_membership),
    job_service: JobService = Depends(get_job_service),
):
    """Poll the status of a generation job."""
    job = await job_service.get_job(job_id)
    if not job or job.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.get("/", response_model=List[JobResponse])
async def list_team_jobs(
    team_id: str,
    membership=Depends(verify_team_membership),
    job_service: JobService = Depends(get_job_service),
):
    """List all generation jobs for a team."""
    return await job_service.list_team_jobs(team_id)
