import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict
import httpx
from arq import Retry

logger = logging.getLogger(__name__)


def compute_webhook_signature(payload_str: str, secret: str) -> str:
    """Generates an HMAC-SHA256 signature for outbound payload verification."""
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_str.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


async def dispatch_webhook(
    ctx: Dict[Any, Any],
    tenant_id: str,
    event_type: str,
    payload: Dict[str, Any],
    target_url: str,
    secret: str,
) -> Dict[str, Any]:
    """
    Worker task: Transmits an signed HTTP POST webhook with automatic retry backoff.
    """
    job_try = ctx.get("job_try", 1)
    max_retries = 3

    body_content = {
        "event": event_type,
        "tenant_id": tenant_id,
        "timestamp": int(time.time()),
        "data": payload,
    }
    encoded_body = json.dumps(body_content, sort_keys=True)
    signature = compute_webhook_signature(encoded_body, secret)

    headers = {
        "Content-Type": "application/json",
        "X-TenantCore-Event": event_type,
        "X-TenantCore-Signature": f"sha256={signature}",
        "X-TenantCore-Delivery-Attempt": str(job_try),
    }

    # Reuse shared httpx client from worker context if available
    client: httpx.AsyncClient = ctx.get("http_client")
    owns_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=10.0)
        owns_client = True

    try:
        response = await client.post(target_url, content=encoded_body, headers=headers)

        if response.status_code >= 500:
            logger.warning(
                "Webhook %s delivery to %s failed with status %d (try %d)",
                event_type,
                target_url,
                response.status_code,
                job_try,
            )
            if job_try < max_retries:
                # Exponential backoff: 2s, 4s, 8s
                raise Retry(defer=2**job_try)
            return {"status": "failed", "http_code": response.status_code}

        return {"status": "delivered", "http_code": response.status_code}

    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.error(
            "Webhook network error to %s: %s (try %d)",
            target_url,
            str(exc),
            job_try,
        )
        if job_try < max_retries:
            raise Retry(defer=2**job_try) from exc
        return {"status": "error", "message": str(exc)}

    finally:
        if owns_client:
            await client.aclose()