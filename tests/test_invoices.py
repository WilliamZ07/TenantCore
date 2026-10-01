import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_invoice_isolation_and_state_machine(client: AsyncClient):
    # 1. Provision Tenant A & Tenant B
    res_a = await client.post("/api/v1/tenants", json={"name": "Org A"})
    key_a = res_a.json()["api_key"]

    res_b = await client.post("/api/v1/tenants", json={"name": "Org B"})
    key_b = res_b.json()["api_key"]

    # 2. Org A creates an invoice
    inv_res = await client.post(
        "/api/v1/invoices",
        json={"customer_name": "Globex Corp", "amount": 2500.00, "currency": "USD"},
        headers={"X-API-KEY": key_a},
    )
    assert inv_res.status_code == 201
    invoice_a_id = inv_res.json()["id"]

    # 3. Org B lists invoices -> Must see 0 invoices (RLS in action)
    list_b = await client.get("/api/v1/invoices", headers={"X-API-KEY": key_b})
    assert list_b.status_code == 200
    assert len(list_b.json()) == 0

    # 4. Org B attempts direct lookup of Org A's invoice -> Must return 404
    direct_b = await client.get(f"/api/v1/invoices/{invoice_a_id}", headers={"X-API-KEY": key_b})
    assert direct_b.status_code == 404

    # 5. State Machine: Illegal direct transition draft -> paid must fail (400)
    bad_transition = await client.patch(
        f"/api/v1/invoices/{invoice_a_id}/status",
        json={"status": "paid"},
        headers={"X-API-KEY": key_a},
    )
    assert bad_transition.status_code == 400
    assert "Illegal state transition" in bad_transition.json()["detail"]

    # 6. Valid transition: draft -> issued -> paid
    t1 = await client.patch(
        f"/api/v1/invoices/{invoice_a_id}/status",
        json={"status": "issued"},
        headers={"X-API-KEY": key_a},
    )
    assert t1.status_code == 200
    assert t1.json()["status"] == "issued"

    t2 = await client.patch(
        f"/api/v1/invoices/{invoice_a_id}/status",
        json={"status": "paid"},
        headers={"X-API-KEY": key_a},
    )
    assert t2.status_code == 200
    assert t2.json()["status"] == "paid"


@pytest.mark.asyncio
async def test_idempotent_invoice_creation(client: AsyncClient):
    # Provision tenant
    res = await client.post("/api/v1/tenants", json={"name": "Idempotent Org"})
    api_key = res.json()["api_key"]
    idempotency_key = str(uuid.uuid4())

    headers = {
        "X-API-KEY": api_key,
        "Idempotency-Key": idempotency_key,
    }
    payload = {"customer_name": "Initech", "amount": 750.00, "currency": "USD"}

    # First request: Creates invoice
    res1 = await client.post("/api/v1/invoices", json=payload, headers=headers)
    assert res1.status_code == 201
    data1 = res1.json()

    # Second request: Replays identical request with same key
    res2 = await client.post("/api/v1/invoices", json=payload, headers=headers)
    assert res2.status_code == 201
    assert res2.headers.get("X-Cache-Lookup") == "HIT - Idempotent Replay"
    data2 = res2.json()

    # Assert exact data identity (no second row created)
    assert data1["id"] == data2["id"]

    # Verify database has strictly 1 record
    list_res = await client.get("/api/v1/invoices", headers=headers)
    assert len(list_res.json()) == 1