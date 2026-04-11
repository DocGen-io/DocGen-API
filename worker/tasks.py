import logging
import os
from worker.celery_app import celery_app
from shared.models import JobStatus
from api.core.config import settings
from worker.redis_log_handler import job_log_stream
from shared.tracing import trace_job_context

try:
    PHOENIX_AVAILABLE = True
except ImportError:
    PHOENIX_AVAILABLE = False
    
from shared.models import JobLog
from datetime import datetime

from api.services.worker_service import (
    update_job_status,
    get_dynamic_config_path,
    save_project_grouping,
    get_job_basic_details
)

logger = logging.getLogger(__name__)

# Initialize Phoenix tracing in celery_app.py worker_process_init instead to avoid gRPC fork issues

@celery_app.task(bind=True, name="worker.tasks.run_documentation_pipeline")
def run_documentation_pipeline(self, job_id: str, source_type: str, path: str, project_name: str = None, credentials: str = None, api_dir: str = None):
    """
    Execute the full DocGen documentation pipeline as a background Celery task.
    Logs are streamed to Redis Pub/Sub channel `logs:{job_id}` in real-time.
    """
    config_path = None

    with job_log_stream(job_id) as log_handler:
        logger.info(f"[Job {job_id}] Starting documentation pipeline for {path}")
        update_job_status(job_id, JobStatus.PROCESSING)

        try:
            # Dynamically compose the runtime config file for isolation
            config_path = get_dynamic_config_path(job_id)

            # Get job context securely
            job_details = get_job_basic_details(job_id)
            team_id = job_details.get("team_id")
            user_id = job_details.get("submitted_by")

            # Import pipeline locally

            # Wrap pipeline execution in tracing context
            final_project_name = project_name or os.path.basename(os.path.normpath(path))

            # Inject injected runtime config file path
            logger.info(f"[Job {job_id}] Initializing pipeline...")
            from src.pipelines.documentation_pipeline import DocumentationPipeline
            pipeline = DocumentationPipeline(config_path=config_path,
             api_details={
                    'job_id': job_id,
                    'team_id': team_id,
                    'user_id': user_id,
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

            update_job_status(job_id, JobStatus.COMPLETED, result=result)
            
            # Persist clusters if they were generated automatically
            if result.get("clusters") and team_id:
                save_project_grouping(final_project_name, team_id, result["clusters"])
            
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

            update_job_status(job_id, JobStatus.FAILED, error=error_msg)
            raise self.retry(exc=exc, max_retries=0)
        finally:
            # Always clean up the temporary config file
            if config_path and os.path.exists(config_path):
                os.remove(config_path)
            
            from src.utils.weaviateStore import WeaviateStore
            WeaviateStore.close()

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
    update_job_status(job_id, JobStatus.PROCESSING)
    try:
        from src.pipelines.query_pipeline import QueryPipeline
        pipeline = QueryPipeline()
        results = pipeline.run(query)
        update_job_status(job_id, JobStatus.COMPLETED, result={"results": results})
        return results
    except Exception as exc:
        update_job_status(job_id, JobStatus.FAILED, error=str(exc))
        raise self.retry(exc=exc, max_retries=0)
    finally:
        from src.utils.weaviateStore import WeaviateStore
        WeaviateStore.close()

@celery_app.task(bind=True, name="worker.tasks.run_clustering_task")
def run_clustering_task(self, job_id: str, project_name: str, n_clusters: int = None):
    """
    Background task for grouping endpoints into semantic clusters.
    """
    # set_trace_job_id(job_id)
    update_job_status(job_id, JobStatus.PROCESSING)
    try:
        from src.components.EndpointClusterer import EndpointClusterer
        
        job_details = get_job_basic_details(job_id)
        team_id = job_details.get("team_id") if job_details else None

        clusterer = EndpointClusterer()
        results = clusterer.run(
            n_clusters=n_clusters,
            api_details={'project_name': project_name, 'team_id': team_id} if team_id else None,
            force=True
        )
        
        update_job_status(job_id, JobStatus.COMPLETED, result=results)
        
        # Persist manual clustering results
        if results.get("clusters") and team_id:
            save_project_grouping(project_name, team_id, results["clusters"])
            
        return results
    except Exception as exc:
        update_job_status(job_id, JobStatus.FAILED, error=str(exc))
        raise self.retry(exc=exc, max_retries=0)
    finally:
        from src.utils.weaviateStore import WeaviateStore
        WeaviateStore.close()

@celery_app.task(bind=True, name="worker.tasks.generate_examples_task")
def generate_examples_task(self, job_id: str, project_name: str, team_id: str, path: str, method: str):
    """
    Background task for generating code examples using Weaviate documentation.
    """
    # set_trace_job_id(job_id)
    update_job_status(job_id, JobStatus.PROCESSING)
    try:
        from src.components.FetchExampleGenerator import FetchExampleGenerator
        
        generator = FetchExampleGenerator(weaviate_url=settings.WEAVIATE_URL)
        results = generator.run(
            team_id=team_id,
            project_name=project_name,
            path=path,
            method=method
        )
        update_job_status(job_id, JobStatus.COMPLETED, result=results)
        return results
    except Exception as exc:
        update_job_status(job_id, JobStatus.FAILED, error=str(exc))
        raise self.retry(exc=exc, max_retries=0)
    finally:
        from src.utils.weaviateStore import WeaviateStore
        WeaviateStore.close()

@celery_app.task(bind=True, name="worker.tasks.list_endpoints_task")
def list_endpoints_task(self, job_id: str, project_name: str, team_id: str):
    """
    Background task to fetch all endpoints for a project from Weaviate
    using the RAG Service Layer.
    """
    update_job_status(job_id, JobStatus.PROCESSING)
    try:
        from src.serviceLayer.endpoint_service import EndpointService
        
        service = EndpointService(weaviate_url=settings.WEAVIATE_URL)
        endpoints = service.fetch_project_endpoints(project_name=project_name, team_id=team_id)
        
        update_job_status(job_id, JobStatus.COMPLETED, result={"endpoints": endpoints})
        return endpoints
    except Exception as exc:
        logger.error(f"[Job {job_id}] list_endpoints_task failed: {exc}")
        update_job_status(job_id, JobStatus.FAILED, error=str(exc))
        raise self.retry(exc=exc, max_retries=0)
    finally:
        from src.utils.weaviateStore import WeaviateStore
        WeaviateStore.close()
