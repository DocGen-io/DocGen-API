from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
import os
import json

from api.core.database import get_db
from api.api.dependencies import get_current_active_user, verify_team_membership
from api.models.user import User

router = APIRouter(prefix="/endpoints", tags=["Endpoints"])

@router.get("/", response_model=Dict[str, List[str]])
async def list_available_projects(
    output_dir: str = "output"
):
    """List all project directories that have generated documentation."""
    if not os.path.exists(output_dir):
        return {"projects": []}
    
    # Filter for directories only
    projects = [d for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d))]
    return {"projects": projects}

def _find_project_dir(project_name: str, output_dir: str = "output") -> Optional[str]:
    """Find a project directory case-insensitively."""
    if not os.path.exists(output_dir):
        return None
    for d in os.listdir(output_dir):
        if d.lower() == project_name.lower() and os.path.isdir(os.path.join(output_dir, d)):
            return d
    return None

@router.get("/{project_name}")
async def list_project_endpoints(
    project_name: str,
    output_dir: str = "output"
):
    """List all generated endpoints for a project by scanning the output directory."""
    name = _find_project_dir(project_name, output_dir)
    if not name:
        return {"project": project_name, "endpoints": {}}

    project_path = os.path.join(output_dir, name)
    swagger_path = os.path.join(project_path, "swagger.json")
    if os.path.exists(swagger_path):
        with open(swagger_path, "r") as f:
            spec = json.load(f)
            return {"project": name, "endpoints": spec.get("paths", {})}
            
    return {"project": name, "endpoints": {}}

@router.get("/{project_name}/query")
async def query_endpoints(
    project_name: str,
    team_id: str,
    q: str = Query(..., description="Natural language query"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    membership = Depends(verify_team_membership)
):
    """Trigger a background semantic search task."""
    from shared.models import GenerationJob, JobStatus
    from worker.tasks import run_semantic_search_task
    
    job = GenerationJob(
        team_id=team_id,
        submitted_by=current_user.id,
        source_type="query",
        path=project_name,
        status=JobStatus.PENDING
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    run_semantic_search_task.delay(job.id, project_name, q)
    return {"job_id": job.id, "status": "queued"}

@router.get("/{project_name}/clusters")
async def get_endpoint_clusters(
    project_name: str,
    team_id: str,
    n_clusters: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    membership = Depends(verify_team_membership)
):
    """Trigger a background clustering task."""
    from shared.models import GenerationJob, JobStatus
    from worker.tasks import run_clustering_task
    job = GenerationJob(
        team_id=team_id,
        submitted_by=current_user.id,
        source_type="clustering",
        path=project_name,
        status=JobStatus.PENDING
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    run_clustering_task.delay(job.id, project_name, n_clusters)
    return {"job_id": job.id, "status": "queued"}

@router.post("/{project_name}/examples")
async def generate_examples(
    project_name: str,
    team_id: str,
    swagger_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    membership = Depends(verify_team_membership)
):
    """Trigger a background example generation task."""
    from shared.models import GenerationJob, JobStatus
    from worker.tasks import generate_examples_task
    job = GenerationJob(
        team_id=team_id,
        submitted_by=current_user.id,
        source_type="examples",
        path=project_name,
        status=JobStatus.PENDING
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    generate_examples_task.delay(job.id, project_name, swagger_data)
    return {"job_id": job.id, "status": "queued"}
