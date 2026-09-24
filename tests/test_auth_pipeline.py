import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_missing_api_key_returns_401(client: AsyncClient):
    response = await client.get("/api/v1/tenants/me")
    assert response.status_code == 401
    assert "Missing required API key" in response.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_api_key_returns_403(client: AsyncClient):
    headers = {"X-API-KEY": "sk_live_totally_fabricated_key_12345"}
    response = await client.get("/api/v1/tenants/me", headers=headers)
    assert response.status_code == 403
    assert "Invalid API key credentials" in response.json()["detail"]


@pytest.mark.asyncio
async def test_tenant_registration_and_auth_success(client: AsyncClient):
    reg_response = await client.post(
        "/api/v1/tenants",
        json={"name": "Weyland-Yutani Corp"},
    )
    assert reg_response.status_code == 201
    data = reg_response.json()
    assert "api_key" in data
    assert data["api_key"].startswith("sk_live_")
    api_key = data["api_key"]
    tenant_id = data["id"]

    auth_response = await client.get(
        "/api/v1/tenants/me",
        headers={"X-API-KEY": api_key},
    )
    assert auth_response.status_code == 200
    me_data = auth_response.json()
    assert me_data["id"] == tenant_id
    assert me_data["name"] == "Weyland-Yutani Corp"
    assert me_data["is_active"] is True