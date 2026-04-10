import logging
from sqlalchemy import select
import tempfile
import os
import yaml
from worker.celery_app import celery_app
from shared.db import SessionLocal
from shared.models import GenerationJob, JobStatus

# SaaS API Imports for Configuration reading
from api.models.team import Team
try:
    from api.models.team_config import TeamConfiguration
except ImportError:
    TeamConfiguration = None
from api.services.team_config_service import _deep_merge, SENSITIVE_KEYS
from api.core.security import decrypt_value
from api.core.default_config import DEFAULT_TEAM_CONFIG
from api.core.config import settings
from worker.redis_log_handler import job_log_stream
from shared.tracing import trace_job_context
try:
    PHOENIX_AVAILABLE = True
except ImportError:
    PHOENIX_AVAILABLE = False
from shared.models import JobLog

logger = logging.getLogger(__name__)

# Initialize Phoenix tracing in celery_app.py worker_process_init instead to avoid gRPC fork issues


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
def run_documentation_pipeline(self, job_id: str, source_type: str, path: str, project_name: str = None, credentials: str = None, api_dir: str = None):
    """
    Execute the full DocGen documentation pipeline as a background Celery task.
    Logs are streamed to Redis Pub/Sub channel `logs:{job_id}` in real-time.
    """
    config_path = None

    with job_log_stream(job_id) as log_handler:
        logger.info(f"[Job {job_id}] Starting documentation pipeline for {path}")
        _update_job_status(job_id, JobStatus.PROCESSING)

        try:
            # Dynamically compose the runtime config file for isolation
            config_path = _get_dynamic_config_path(job_id)

            db = SessionLocal()
            try:
                job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
            finally:
                db.close()

            # Import pipeline locally

            # Wrap pipeline execution in tracing context
            final_project_name = project_name or os.path.basename(os.path.normpath(path))

            # Inject injected runtime config file path
            logger.info(f"[Job {job_id}] Initializing pipeline...")
            from src.pipelines.documentation_pipeline import DocumentationPipeline
            pipeline = DocumentationPipeline(config_path=config_path,
             api_details={
                    'job_id': job_id,
                    'team_id': job.team_id if job else None,
                    'user_id': job.submitted_by if job else None,
                    'project_name': final_project_name
                }
            )

            with trace_job_context(job_id, project_name=final_project_name):
                result = pipeline.run(
                    source_type=source_type,
                    path=path,
                    credentials=credentials,
                    api_dir=api_dir,
                )

            _update_job_status(job_id, JobStatus.COMPLETED, result=result)
            logger.info(f"[Job {job_id}] Pipeline completed successfully")
            return result

        except Exception as exc:
            error_msg = str(exc)
            logger.error(f"[Job {job_id}] Pipeline failed: {error_msg}")
            
            # Cleanup on failure (Item 6)
            try:
                project_name = os.path.basename(path)
                output_dir = os.path.join("output", project_name)
                if os.path.exists(output_dir):
                    import shutil
                    shutil.rmtree(output_dir, ignore_errors=True)
                    logger.info(f"[Job {job_id}] Cleaned up failed output directory (if possible): {output_dir}")
            except Exception as e:
                logger.error(f"[Job {job_id}] Failed to cleanup output directory: {e}")

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
    logger.info(f"Targeting Weaviate index to patch document node={endpoint_id}")
    
    try:
        from haystack.document_stores.types import DuplicatePolicy
        from src.utils.weaviate_utils import get_weaviate_store, fetch_by_node_id
       
        with get_weaviate_store(url=settings.WEAVIATE_URL) as doc_store:
            docs = fetch_by_node_id(doc_store, endpoint_id)
            if not docs:
                logger.warning(f"No document found in Weaviate for node={endpoint_id}")
                return False
                
            old_doc = docs[0]
            # Mutate content and retain all meta
            old_doc.content = proposed_content
            # Enforce overwrite policy by writing the mutated document with same id
            doc_store.write_documents([old_doc], policy=DuplicatePolicy.OVERWRITE)
            logger.info(f"Successfully patched Weaviate node={endpoint_id}")
            return True
    finally:
        logger.info(f"Completed attempt to patch Weaviate node={endpoint_id}")


@celery_app.task(bind=True, name="worker.tasks.run_semantic_search_task")
def run_semantic_search_task(self, job_id: str, project_name: str, query: str):
    """
    Background task for semantic searching across endpoints.
    """
    # set_trace_job_id(job_id)
    _update_job_status(job_id, JobStatus.PROCESSING)
    try:
        from src.pipelines.query_pipeline import QueryPipeline
        pipeline = QueryPipeline()
        results = pipeline.run(query)
        _update_job_status(job_id, JobStatus.COMPLETED, result={"results": results})
        return results
    except Exception as exc:
        _update_job_status(job_id, JobStatus.FAILED, error=str(exc))
        raise self.retry(exc=exc, max_retries=0)


@celery_app.task(bind=True, name="worker.tasks.run_clustering_task")
def run_clustering_task(self, job_id: str, project_name: str, n_clusters: int = None):
    """
    Background task for grouping endpoints into semantic clusters.
    """
    # set_trace_job_id(job_id)
    _update_job_status(job_id, JobStatus.PROCESSING)
    try:
        from src.components.EndpointClusterer import EndpointClusterer
        clusterer = EndpointClusterer()
        results = clusterer.run(n_clusters=n_clusters)
        _update_job_status(job_id, JobStatus.COMPLETED, result=results)
        return results
    except Exception as exc:
        _update_job_status(job_id, JobStatus.FAILED, error=str(exc))
        raise self.retry(exc=exc, max_retries=0)


@celery_app.task(bind=True, name="worker.tasks.generate_examples_task")
def generate_examples_task(self, job_id: str, project_name: str, swagger_data: dict):
    """
    Background task for generating code examples.
    """
    # set_trace_job_id(job_id)
    _update_job_status(job_id, JobStatus.PROCESSING)
    try:
        from src.components.FetchExampleGenerator import FetchExampleGenerator
        generator = FetchExampleGenerator()
        results = generator.run(swagger_data=swagger_data)
        _update_job_status(job_id, JobStatus.COMPLETED, result={"examples": results})
        return results
    except Exception as exc:
        _update_job_status(job_id, JobStatus.FAILED, error=str(exc))
        raise self.retry(exc=exc, max_retries=0)

