"""Unit and integration tests for API v1 endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Smoke test: /health endpoint returns 200 OK."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_telemetry_get(client: AsyncClient):
    """Test: /api/v1/telemetry returns telemetry schema."""
    response = await client.get("/api/v1/telemetry")
    assert response.status_code == 200
    assert "pitch_deg" in response.json()
