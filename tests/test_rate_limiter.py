import asyncio
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_rate_limiter_decrements_quota(client: AsyncClient):
    # 1. Register a fresh tenant
    reg_res = await client.post("/api/v1/tenants", json={"name": "Soran Corp"})
    api_key = reg_res.json()["api_key"]
    headers = {"X-API-KEY": api_key}

    # 2. First call should have full quota minus 1
    res1 = await client.get("/api/v1/tenants/me", headers=headers)
    assert res1.status_code == 200
    assert "X-RateLimit-Remaining" in res1.headers
    remaining1 = int(res1.headers["X-RateLimit-Remaining"])

    # 3. Second call must strictly decrement the remaining quota
    res2 = await client.get("/api/v1/tenants/me", headers=headers)
    assert res2.status_code == 200
    remaining2 = int(res2.headers["X-RateLimit-Remaining"])
    assert remaining2 == remaining1 - 1


@pytest.mark.asyncio
async def test_rate_limiter_blocks_concurrent_burst(client: AsyncClient):
    # Register tenant with 10 req/min limit on /tenants/me
    reg_res = await client.post("/api/v1/tenants", json={"name": "Tyrell Corp"})
    api_key = reg_res.json()["api_key"]
    headers = {"X-API-KEY": api_key}

    # Fire 15 concurrent requests against the 10-request quota
    tasks = [client.get("/api/v1/tenants/me", headers=headers) for _ in range(15)]
    responses = await asyncio.gather(*tasks)

    status_codes = [r.status_code for r in responses]
    success_count = status_codes.count(200)
    blocked_count = status_codes.count(429)

    # Exactly 10 must succeed, and 5 must be blocked with 429
    assert success_count == 10, f"Expected 10 successes, got {success_count}"
    assert blocked_count == 5, f"Expected 5 rate limited, got {blocked_count}"

    # Verify 429 payload and Retry-After header
    blocked_response = next(r for r in responses if r.status_code == 429)
    assert "Rate limit exceeded" in blocked_response.json()["detail"]
    assert "Retry-After" in blocked_response.headers