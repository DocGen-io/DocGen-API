from celery import Celery
from api.core.config import settings

# Lightweight Celery client — only used to dispatch tasks from the SaaS API to the Worker.
# This connects to the Redis broker defined in the project settings.
celery_client = Celery(
    "docgen_dispatcher",
    broker=settings.REDIS_URL,
)
