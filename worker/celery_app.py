"""
Celery application initialization.

Uses Redis as both the message broker and result backend.
"""
from celery import Celery
from worker.config import settings

celery_app = Celery(
    "docgen_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,           # Re-deliver task if worker crashes mid-execution
    worker_prefetch_multiplier=1,  # Fair scheduling: grab one task at a time
)

# Auto-discover task modules
celery_app.autodiscover_tasks(["worker"])
