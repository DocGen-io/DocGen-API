from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
import os
import json

from api.core.database import get_db
from api.api.dependencies import get_current_active_user, verify_team_membership
from api.models.user import User
from shared.models import GenerationJob, JobStatus
from sqlalchemy.future import select
from api.models.project import Project
from api.services.job_service import JobService
from api.schemas.job import JobCreate, JobResponse
import logging
from api.services.job_service import JobService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/endpoints", tags=["Endpoints"])


def get_job_service(db: AsyncSession = Depends(get_db)) -> JobService:
    return JobService(db)

@router.get("/", response_model=Dict[str, List[str]])
async def list_available_projects(
    team_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all projects for a team from the database."""
    if not team_id:
        return {"projects": []}
    
    stmt = select(Project.name).where(Project.team_id == team_id).distinct()
    result = await db.execute(stmt)
    projects = result.scalars().all()
    
    return {"projects": projects}

@router.get("/{project_name}", response_model=JobResponse)
async def list_project_endpoints(
    project_name: str,
    team_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    membership = Depends(verify_team_membership),
    job_service: JobService = Depends(get_job_service)
):
    """List all generated endpoints for a project by querying Weaviate via Worker."""
    return await job_service.submit_task(
        team_id=team_id,
        submitted_by=current_user.id,
        task_name="worker.tasks.list_endpoints_task",
        task_kwargs={"project_name": project_name, "team_id": team_id},
        source_type="list_endpoints",
        path=project_name,
        project_name=project_name
    )

@router.get("/{project_name}/query", response_model=JobResponse)
async def query_endpoints(
    project_name: str,
    team_id: str,
    q: str = Query(..., description="Natural language query"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    membership = Depends(verify_team_membership),
    job_service: JobService = Depends(get_job_service)
):
    """Trigger a background semantic search task."""
    return await job_service.submit_task(
        team_id=team_id,
        submitted_by=current_user.id,
        task_name="worker.tasks.run_semantic_search_task",
        task_kwargs={"project_name": project_name, "query": q},
        source_type="query",
        path=project_name,
        project_name=project_name
    )

@router.get("/{project_name}/clusters", response_model=JobResponse)
async def get_endpoint_clusters(
    project_name: str,
    team_id: str,
    n_clusters: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    membership = Depends(verify_team_membership),
    job_service: JobService = Depends(get_job_service)
):
    """Trigger a background clustering task."""
    return await job_service.submit_task(
        team_id=team_id,
        submitted_by=current_user.id,
        task_name="worker.tasks.run_clustering_task",
        task_kwargs={"project_name": project_name, "n_clusters": n_clusters},
        source_type="clustering",
        path=project_name,
        project_name=project_name
    )

from api.schemas.job import JobResponse, JobCreate, ExampleGenerationRequest


@router.post("/{project_name}/examples", response_model=JobResponse)
async def generate_examples(
    project_name: str,
    team_id: str,
    request: ExampleGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    membership = Depends(verify_team_membership),
    job_service: JobService = Depends(get_job_service)
):
    """Trigger a background example generation task using Weaviate documentation."""
    return await job_service.submit_task(
        team_id=team_id,
        submitted_by=current_user.id,
        task_name="worker.tasks.generate_examples_task",
        task_kwargs={
            "project_name": project_name,
            "team_id": team_id,
            "path": request.path,
            "method": request.method
        },
        source_type="examples",
        path=project_name,
        project_name=project_name
    )
