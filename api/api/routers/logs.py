"""
WebSocket endpoint for real-time log streaming.

Subscribes to the Redis Pub/Sub channel `logs:{job_id}` and streams
each log message as JSON to the connected WebSocket client.
"""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import jwt, JWTError
from redis.asyncio import from_url as async_redis_from_url

from api.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Logs"])

LOG_STREAM_TIMEOUT_SECONDS = 300  # 5-minute inactivity timeout


def _authenticate_token(token: str) -> str:
    """Decode a JWT token and return the user_id (sub claim). Raises ValueError on failure."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise ValueError("Missing subject")
        return user_id
    except JWTError as exc:
        raise ValueError(f"Invalid token: {exc}")


@router.websocket("/ws/logs/{job_id}")
async def stream_job_logs(websocket: WebSocket, job_id: str, token: str = Query(...)):
    """
    Stream worker logs for a specific job over WebSocket.

    Authentication is via a `token` query parameter containing a valid JWT.
    The client connects to: `ws://.../ws/logs/{job_id}?token=<jwt>`

    Messages are JSON objects with: timestamp, level, message, logger.
    A final `{"type": "complete"}` sentinel is sent when the job finishes.
    """
    # ── Authenticate ──────────────────────────────────────────────────
    try:
        _authenticate_token(token)
    except ValueError as exc:
        logger.error(f"WebSocket auth failed for token: {exc}")
        await websocket.close(code=4001, reason="Authentication failed")
        return

    await websocket.accept()

    # ── Subscribe to Redis Pub/Sub channel ────────────────────────────
    redis_conn = async_redis_from_url(settings.REDIS_URL)
    pubsub = redis_conn.pubsub()
    channel = f"logs:{job_id}"

    try:
        await pubsub.subscribe(channel)
        logger.info(f"WebSocket client subscribed to {channel}")

        deadline = asyncio.get_event_loop().time() + LOG_STREAM_TIMEOUT_SECONDS

        while True:
            # Check deadline
            if asyncio.get_event_loop().time() > deadline:
                await websocket.send_json({"type": "timeout", "message": "No activity"})
                break

            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=1.0,
            )

            if message is None:
                # No message yet — yield to event loop and poll again
                await asyncio.sleep(0.05)
                continue

            data = message["data"]
            if isinstance(data, bytes):
                data = data.decode("utf-8")

            # Forward raw JSON string to the client
            await websocket.send_text(data)

            # Reset deadline on activity
            deadline = asyncio.get_event_loop().time() + LOG_STREAM_TIMEOUT_SECONDS

            # Check for the "complete" sentinel from the worker
            try:
                parsed = json.loads(data)
                if parsed.get("type") == "complete":
                    break
            except (json.JSONDecodeError, TypeError):
                pass

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected from {channel}")
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await redis_conn.close()
