import hashlib
import hmac
import json
import pytest
from arq import Retry
import httpx

from app.tasks.webhooks import compute_webhook_signature, dispatch_webhook


@pytest.mark.asyncio
async def test_compute_webhook_signature():
    payload = json.dumps({"test": "data"}, sort_keys=True)
    secret = "test_secret_key"
    sig = compute_webhook_signature(payload, secret)

    expected = hmac.new(
        secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    assert sig == expected


@pytest.mark.asyncio
async def test_dispatch_webhook_successful_delivery():
    # Mock httpx AsyncClient transport
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-TenantCore-Event"] == "invoice.paid"
        assert "X-TenantCore-Signature" in request.headers
        assert request.headers["X-TenantCore-Delivery-Attempt"] == "1"
        return httpx.Response(200, json={"received": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        ctx = {"http_client": mock_client, "job_try": 1}
        result = await dispatch_webhook(
            ctx=ctx,
            tenant_id="00000000-0000-0000-0000-000000000001",
            event_type="invoice.paid",
            payload={"invoice_id": "inv_123", "amount": 250.0},
            target_url="https://mock-client.test/webhook",
            secret="super_secret_signing_key",
        )

        assert result["status"] == "delivered"
        assert result["http_code"] == 200


@pytest.mark.asyncio
async def test_dispatch_webhook_triggers_retry_on_500():
    def server_error_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="Bad Gateway")

    transport = httpx.MockTransport(server_error_handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        ctx = {"http_client": mock_client, "job_try": 1}

        # Arq Retry must be raised on attempt 1 when downstream returns >= 500
        with pytest.raises(Retry) as exc_info:
            await dispatch_webhook(
                ctx=ctx,
                tenant_id="00000000-0000-0000-0000-000000000001",
                event_type="invoice.paid",
                payload={"invoice_id": "inv_123"},
                target_url="https://failing-endpoint.test/webhook",
                secret="super_secret_signing_key",
            )

        assert exc_info.value.defer_score is not None