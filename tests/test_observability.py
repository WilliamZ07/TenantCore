import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_auto_generates_request_id(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 10
    assert "X-Process-Time-Ms" in response.headers


@pytest.mark.asyncio
async def test_preserves_incoming_request_id(client: AsyncClient):
    custom_id = "custom-trace-uuid-12345"
    response = await client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_id


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint(client: AsyncClient):
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text or "python_gc_objects_collected_total" in response.text