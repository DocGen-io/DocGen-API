"""
Redis Pub/Sub logging handler.

Publishes structured JSON log records to a Redis channel keyed by job_id,
enabling real-time log streaming via WebSocket on the API side.
"""
import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone

import redis

from worker.config import settings


class RedisLogHandler(logging.Handler):
    """Logging handler that publishes records to Redis Pub/Sub channel `logs:{job_id}`."""

    def __init__(self, job_id: str, redis_url: str = settings.REDIS_URL):
        super().__init__()
        self._channel = f"logs:{job_id}"
        self._client = redis.from_url(redis_url)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            payload = json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "message": self.format(record),
                "logger": record.name,
            })
            self._client.publish(self._channel, payload)
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        """Publish a sentinel so subscribers know the stream is done, then clean up."""
        try:
            self._client.publish(self._channel, json.dumps({"type": "complete"}))
        except Exception:
            pass
        finally:
            self._client.close()
            super().close()


@contextmanager
def job_log_stream(job_id: str):
    """Context manager to attach/detach a RedisLogHandler for the duration of a task.

    Usage::

        with job_log_stream(job_id):
            logger.info("Generating AST...")  # -> published to logs:{job_id}
    """
    handler = RedisLogHandler(job_id)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(message)s"))

    root = logging.getLogger()
    root.addHandler(handler)
    try:
        yield handler
    finally:
        root.removeHandler(handler)
        handler.close()
