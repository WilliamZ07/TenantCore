import hashlib
import hmac
import json
import uuid
import pytest
from httpx import AsyncClient
from app.routers.v1.webhooks import WEBHOOK_SECRET


def sign_payload(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_webhook_payment_processing(client: AsyncClient):
    # 1. Provision tenant & create invoice
    res = await client.post("/api/v1/tenants", json={"name": "Webhook Corp"})
    api_key = res.json()["api_key"]
    tenant_id = res.json()["id"]

    inv_res = await client.post(
        "/api/v1/invoices",
        json={"customer_name": "Umbrella Corp", "amount": 12000.00, "currency": "USD"},
        headers={"X-API-KEY": api_key},
    )
    invoice_id = inv_res.json()["id"]

    # Move to issued
    await client.patch(
        f"/api/v1/invoices/{invoice_id}/status",
        json={"status": "issued"},
        headers={"X-API-KEY": api_key},
    )

    # 2. Forge payment.succeeded webhook
    event_id = f"evt_{uuid.uuid4().hex}"
    payload = {
        "event_id": event_id,
        "event_type": "payment.succeeded",
        "data": {
            "invoice_id": invoice_id,
            "tenant_id": tenant_id,
        },
    }
    payload_bytes = json.dumps(payload).encode("utf-8")
    valid_signature = sign_payload(payload_bytes, WEBHOOK_SECRET)

    # 3. Deliver webhook
    wh_res = await client.post(
        "/api/v1/webhooks/payments",
        content=payload_bytes,
        headers={"X-Signature": valid_signature, "Content-Type": "application/json"},
    )
    assert wh_res.status_code == 200
    assert wh_res.json()["status"] == "success"

    # 4. Verify invoice is now paid
    verify_res = await client.get(f"/api/v1/invoices/{invoice_id}", headers={"X-API-KEY": api_key})
    assert verify_res.status_code == 200
    assert verify_res.json()["status"] == "paid"

    # 5. Replay exact same webhook -> Must return idempotent acknowledgment
    replay_res = await client.post(
        "/api/v1/webhooks/payments",
        content=payload_bytes,
        headers={"X-Signature": valid_signature, "Content-Type": "application/json"},
    )
    assert replay_res.status_code == 200
    assert "idempotent duplicate" in replay_res.json()["detail"]