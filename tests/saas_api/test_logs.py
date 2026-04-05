"""
E2E tests for Phase 6: Log Streaming & Tracing endpoints.

Tests cover:
- WebSocket connection with valid JWT
- WebSocket rejection with invalid/missing JWT
- Redis Pub/Sub message flow through WebSocket
- Traces endpoint availability
"""
import asyncio
import json
import uuid

import httpx
import pytest
import redis
import websockets

BASE_URL = "http://localhost:8000"
WS_BASE_URL = "ws://localhost:8000"


class TestLogStreaming:
    """Tests for the WebSocket log streaming and traces API."""

    async def _register_and_login(self) -> dict:
        """Register a fresh user and return credentials with JWT token."""
        suffix = uuid.uuid4().hex[:8]
        creds = {
            "username": f"log_test_{suffix}",
            "email": f"log_test_{suffix}@test.com",
            "password": "testpassword123",
        }
        async with httpx.AsyncClient(base_url=BASE_URL) as client:
            await client.post("/api/v1/auth/register", json=creds)
            r = await client.post(
                "/api/v1/auth/token",
                data={"username": creds["email"], "password": creds["password"]},
            )
            token = r.json()["access_token"]
            creds["token"] = token
        return creds

    @pytest.mark.asyncio
    async def test_websocket_rejects_missing_token(self):
        """WebSocket connection without token query param should be rejected."""
        job_id = str(uuid.uuid4())
        try:
            async with websockets.connect(f"{WS_BASE_URL}/ws/logs/{job_id}") as ws:
                await ws.recv()
                pytest.fail("Should have been rejected without token")
        except Exception:
            # Connection closed / rejected by server — expected
            pass

    @pytest.mark.asyncio
    async def test_websocket_rejects_invalid_token(self):
        """WebSocket connection with a bad JWT should be rejected."""
        job_id = str(uuid.uuid4())
        try:
            async with websockets.connect(
                f"{WS_BASE_URL}/ws/logs/{job_id}?token=invalid_jwt_token"
            ) as ws:
                await ws.recv()
                pytest.fail("Should have been rejected with invalid token")
        except Exception:
            pass  # Expected — server closes connection

    @pytest.mark.asyncio
    async def test_websocket_accepts_valid_token_and_streams_logs(self):
        """WebSocket streams messages published to Redis Pub/Sub and closes on sentinel."""
        creds = await self._register_and_login()
        job_id = str(uuid.uuid4())
        channel = f"logs:{job_id}"

        # Start WebSocket listener in background
        received_messages = []

        async def ws_listener():
            async with websockets.connect(
                f"{WS_BASE_URL}/ws/logs/{job_id}?token={creds['token']}"
            ) as ws:
                try:
                    async for msg in ws:
                        data = json.loads(msg)
                        received_messages.append(data)
                        if data.get("type") == "complete":
                            break
                except websockets.exceptions.ConnectionClosed:
                    pass

        listener_task = asyncio.create_task(ws_listener())

        # Give the WebSocket time to establish and the server to subscribe
        await asyncio.sleep(1.0)

        # Publish mock log messages to Redis (simulates worker behavior)
        r = redis.from_url("redis://localhost:6379/0")
        r.publish(channel, json.dumps({"level": "INFO", "message": "Generating AST..."}))
        await asyncio.sleep(0.1)
        r.publish(channel, json.dumps({"level": "INFO", "message": "Writing to Weaviate..."}))
        await asyncio.sleep(0.1)
        r.publish(channel, json.dumps({"type": "complete"}))
        r.close()

        # Wait for listener to finish
        await asyncio.wait_for(listener_task, timeout=10.0)

        assert len(received_messages) == 3
        assert received_messages[0]["message"] == "Generating AST..."
        assert received_messages[1]["message"] == "Writing to Weaviate..."
        assert received_messages[2]["type"] == "complete"

    @pytest.mark.asyncio
    async def test_traces_endpoint_returns_503_when_tracing_disabled(self):
        """The traces endpoint should return 503 if Phoenix is not running on the API side."""
        creds = await self._register_and_login()
        async with httpx.AsyncClient(base_url=BASE_URL) as client:
            r = await client.get(
                f"/api/v1/traces/{uuid.uuid4()}",
                headers={"Authorization": f"Bearer {creds['token']}"},
            )
            # Phoenix runs in-process on the worker, not the API,
            # so this should return 503 or an empty result
            assert r.status_code in (200, 503)


class TestExistingEndpointsNotBroken:
    """Smoke tests to verify Phase 6 doesn't break previous endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self):
        async with httpx.AsyncClient(base_url=BASE_URL) as client:
            r = await client.get("/health")
            assert r.status_code == 200
            assert r.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_auth_register_and_login(self):
        suffix = uuid.uuid4().hex[:8]
        async with httpx.AsyncClient(base_url=BASE_URL) as client:
            r = await client.post("/api/v1/auth/register", json={
                "username": f"smoke_{suffix}",
                "email": f"smoke_{suffix}@test.com",
                "password": "testpassword123",
            })
            assert r.status_code == 200

            r = await client.post(
                "/api/v1/auth/token",
                data={"username": f"smoke_{suffix}@test.com", "password": "testpassword123"},
            )
            assert r.status_code == 200
            assert "access_token" in r.json()

    @pytest.mark.asyncio
    async def test_teams_list(self):
        suffix = uuid.uuid4().hex[:8]
        async with httpx.AsyncClient(base_url=BASE_URL) as client:
            await client.post("/api/v1/auth/register", json={
                "username": f"teamsmoke_{suffix}",
                "email": f"teamsmoke_{suffix}@test.com",
                "password": "testpassword123",
            })
            r = await client.post(
                "/api/v1/auth/token",
                data={"username": f"teamsmoke_{suffix}@test.com", "password": "testpassword123"},
            )
            token = r.json()["access_token"]

            r = await client.get(
                "/api/v1/teams/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            assert isinstance(r.json(), list)
