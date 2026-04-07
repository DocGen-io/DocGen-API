"""
Celery worker configuration for DocGen-API.
"""
from celery import Celery
from celery.signals import worker_process_init, celeryd_after_setup
from worker.config import settings
from shared.db import SessionLocal
from shared.models import JobLog
from shared.tracing import launch_phoenix, instrument_app

celery_app = Celery(
    "docgen_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["worker.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
)

# Auto-discover task modules
celery_app.autodiscover_tasks(["worker"])


@celeryd_after_setup.connect
def setup_phoenix_server(sender, instance, **kwargs):
    """Launch Phoenix server once in the main process."""
    launch_phoenix()


@worker_process_init.connect
def init_worker_tracing(*args, **kwargs):
    """Instrument each child worker process."""
    instrument_app()
