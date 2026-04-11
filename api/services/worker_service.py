"""
Worker Service — Synchronous database operations for the Celery Worker.

Since Celery tasks run in a synchronous environment (using psycopg2 and `SessionLocal`),
they cannot trivially share the main API's heavily async-focused service layer (`AsyncSession`).
This dedicated service file provides pure Python helper methods to abstract all 
synchronous SQLAlchemy interactions away from the task orchestrator in `worker/tasks.py`.
"""
import logging
import tempfile
import yaml

from shared.db import SessionLocal
from shared.models import GenerationJob, JobStatus
from api.models.project import Project
from api.models.grouping import ProjectGrouping

# SaaS API Imports for Configuration reading
from api.models.team import Team
try:
    from api.models.team_config import TeamConfiguration
except ImportError:
    TeamConfiguration = None
from api.services.team_config_service import _deep_merge, SENSITIVE_KEYS
from api.core.security import decrypt_value
from api.core.default_config import DEFAULT_TEAM_CONFIG

logger = logging.getLogger(__name__)

def update_job_status(job_id: str, status: JobStatus, result: dict = None, error: str = None) -> None:
    """Helper to update job status in PostgreSQL using a sync session."""
    db = SessionLocal()
    try:
        job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
        if job:
            job.status = status
            if result is not None:
                job.result = result
            if error is not None:
                job.error = error
            db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update job {job_id}: {e}")
    finally:
        db.close()

def get_dynamic_config_path(job_id: str) -> str:
    """
    Fetch the decrypted team configurations from PG, merge with YAML defaults, 
    and dump to a temporary file for the isolated RAG pipeline to use.
    """
    db = SessionLocal()
    try:
        # Get Job to figure out the team_id
        job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
        if not job or not job.team_id:
            logger.warning(f"[Job {job_id}] No job or team found, falling back to pure defaults.")
            config_dict = {}
        else:
            team_config = db.query(TeamConfiguration).filter(TeamConfiguration.team_id == job.team_id).first()
            config_dict = {}
            if team_config:
                decrypted = team_config.config_data.copy()
                for k, v in decrypted.items():
                    if k in SENSITIVE_KEYS and isinstance(v, str):
                        decrypted[k] = decrypt_value(v)
                config_dict = decrypted

        # Deep merge with native defaults
        merged_config = _deep_merge(DEFAULT_TEAM_CONFIG, config_dict)
        
        # Dump to tempfile and return filepath
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump(merged_config, f)
            return f.name
    finally:
        db.close()

def save_project_grouping(project_name: str, team_id: str, clusters: dict) -> None:
    """Helper to persist endpoint groupings to the database."""
    if not clusters:
        return
    db = SessionLocal()
    try:
        project = db.query(Project).filter(
            Project.name == project_name,
            Project.team_id == team_id
        ).first()
        
        if not project:
            logger.warning(f"Could not find project {project_name} for team {team_id} to save grouping")
            return
            
        grouping = db.query(ProjectGrouping).filter(
            ProjectGrouping.project_id == project.id
        ).first()
        
        if grouping:
            grouping.clusters = clusters
        else:
            grouping = ProjectGrouping(
                project_id=project.id,
                clusters=clusters
            )
            db.add(grouping)
            
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save grouping for project {project_name}: {e}")
    finally:
        db.close()

def get_job_basic_details(job_id: str) -> dict:
    """Fetch basic routing details like team_id and submitted_by for worker pipeline init."""
    db = SessionLocal()
    try:
        job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
        if job:
            return {"team_id": job.team_id, "submitted_by": job.submitted_by}
        return {}
    finally:
        db.close()
