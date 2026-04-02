"""
Celery task definitions — thin wrappers only.

All business logic lives in the existing DocumentationPipeline.
The task simply:
  1. Updates job status to PROCESSING
  2. Delegates to DocumentationPipeline.run()
  3. Updates job status to COMPLETED or FAILED
"""
import logging
from worker.celery_app import celery_app
from shared.db import SessionLocal
from shared.models import GenerationJob, JobStatus

logger = logging.getLogger(__name__)


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


@celery_app.task(bind=True, name="worker.tasks.run_documentation_pipeline")
def run_documentation_pipeline(self, job_id: str, source_type: str, path: str, credentials: str = None):
    """
    Execute the full DocGen documentation pipeline as a background Celery task.

    This is a thin wrapper — no business logic here.
    The existing DocumentationPipeline is imported and called as-is.
    """
    logger.info(f"[Job {job_id}] Starting documentation pipeline for {path}")
    _update_job_status(job_id, JobStatus.PROCESSING)

    try:
        # Import here to avoid loading heavy ML libs at module level
        from src.pipelines.documentation_pipeline import DocumentationPipeline

        pipeline = DocumentationPipeline()
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
