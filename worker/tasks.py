import logging
import tempfile
import os
import yaml
from worker.celery_app import celery_app
from shared.db import SessionLocal
from shared.models import GenerationJob, JobStatus

# SaaS API Imports for Configuration reading
from api.models.team_config import TeamConfiguration
from api.services.team_config_service import _deep_merge, SENSITIVE_KEYS
from api.core.security import decrypt_value
from api.core.default_config import DEFAULT_TEAM_CONFIG
from src.utils.tenant_context import set_tenant
from src.utils.weaviate_utils import get_weaviate_store, fetch_by_node_id
from haystack.document_stores.types import DuplicatePolicy
from api.core.config import settings
from worker.redis_log_handler import job_log_stream
from worker.tracing import init_tracing

logger = logging.getLogger(__name__)

# Initialize Phoenix tracing (idempotent — only acts on first call)
init_tracing()


def _update_job_status(job_id: str, status: JobStatus, result: dict = None, error: str = None):
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

def _get_dynamic_config_path(job_id: str) -> str:
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


@celery_app.task(bind=True, name="worker.tasks.run_documentation_pipeline")
def run_documentation_pipeline(self, job_id: str, source_type: str, path: str, credentials: str = None):
    """
    Execute the full DocGen documentation pipeline as a background Celery task.
    Logs are streamed to Redis Pub/Sub channel `logs:{job_id}` in real-time.
    """
    config_path = None

    with job_log_stream(job_id):
        logger.info(f"[Job {job_id}] Starting documentation pipeline for {path}")
        _update_job_status(job_id, JobStatus.PROCESSING)

        try:
            # Dynamically compose the runtime config file for isolation
            config_path = _get_dynamic_config_path(job_id)

            # Scope Weaviate to this team's tenant shard (no-op if team_id is None)
            tenant_token = None
            db = SessionLocal()
            try:
                job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
                if job and job.team_id:
                    tenant_token = set_tenant(str(job.team_id))
            finally:
                db.close()

            # Import pipeline locally
            from src.pipelines.documentation_pipeline import DocumentationPipeline

            # Inject injected runtime config file path
            logger.info(f"[Job {job_id}] Initializing pipeline...")
            pipeline = DocumentationPipeline(config_path=config_path)
            result = pipeline.run(
                source_type=source_type,
                path=path,
                credentials=credentials,
            )

            _update_job_status(job_id, JobStatus.COMPLETED, result=result)
            logger.info(f"[Job {job_id}] Pipeline completed successfully")
            return result

        except Exception as exc:
            error_msg = str(exc)
            logger.error(f"[Job {job_id}] Pipeline failed: {error_msg}")
            _update_job_status(job_id, JobStatus.FAILED, error=error_msg)
            raise self.retry(exc=exc, max_retries=0)
        finally:
            # Always clean up the temporary config file
            if config_path and os.path.exists(config_path):
                os.remove(config_path)

@celery_app.task(bind=True, name="worker.tasks.update_weaviate_documentation_chunk")
def update_weaviate_documentation_chunk(self, team_id: str, endpoint_id: str, proposed_content: str):
    """
    Overwrites a specific chunk of documentation in Weaviate with the proposed PR content.
    Isolated per team_id.
    """
    logger.info(f"Targeting Weaviate index to patch document node={endpoint_id} for tenant={team_id}")
    
    tenant_token = set_tenant(team_id)
    try:
       
        with get_weaviate_store(url=settings.WEAVIATE_URL) as doc_store:
            docs = fetch_by_node_id(doc_store, endpoint_id)
            if not docs:
                logger.error(f"Cannot patch document {endpoint_id}. Document not found in Weaviate for tenant {team_id}.")
                return False
                
            old_doc = docs[0]
            # Mutate content and retain all meta
            old_doc.content = proposed_content
            # Enforce overwrite policy by writing the mutated document with same id
            doc_store.write_documents([old_doc], policy=DuplicatePolicy.OVERWRITE)
            logger.info(f"Successfully patched Weaviate node={endpoint_id} for tenant={team_id}")
            return True
    finally:
        from src.utils.tenant_context import tenant_context
        tenant_context.reset(tenant_token)

