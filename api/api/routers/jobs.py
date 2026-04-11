from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.api.dependencies import verify_team_membership, get_current_active_user
from api.models.user import User
from api.schemas.job import JobCreate, JobResponse, JobStatusResponse
from api.services.job_service import JobService
import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])

@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_universal_job_status(
    job_id: str,
    job_service: JobService = Depends(get_job_service)
):
    """Poll the status of any generation job by its ID."""
    job = await job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    logs = await job_service.get_job_logs(job_id)
    return JobStatusResponse(job=job, logs=logs)

# Prefix-based team routes
team_router = APIRouter(prefix="/teams/{team_id}/jobs", tags=["Jobs"])


def get_job_service(db: AsyncSession = Depends(get_db)) -> JobService:
    return JobService(db)


@team_router.post("/generate", response_model=JobResponse)
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


@team_router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    team_id: str,
    job_id: str,
    membership=Depends(verify_team_membership),
    job_service: JobService = Depends(get_job_service),
):
    """Poll the status of a generation job and its associated logs."""
    job = await job_service.get_job(job_id)
    if not job or job.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    logs = await job_service.get_job_logs(job_id)
    return JobStatusResponse(job=job, logs=logs)



@team_router.get("/", response_model=List[JobResponse])
async def list_team_jobs(
    team_id: str,
    membership=Depends(verify_team_membership),
    job_service: JobService = Depends(get_job_service),
):
    """List all generation jobs for a team."""
    logger.info(f"Listing jobs for team {team_id} requested by user")
    return await job_service.list_team_jobs(team_id)
