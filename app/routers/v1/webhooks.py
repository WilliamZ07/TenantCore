import json
import uuid
from typing import Annotated
from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_redis_client
from app.core.security import verify_webhook_signature
from app.db.session import AsyncSessionFactory
from app.models.invoice import Invoice
from app.schemas.invoice import InvoiceStatus

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

WEBHOOK_SECRET = "whsec_test_secret_key_998877"


@router.post(
    "/payments",
    status_code=status.HTTP_200_OK,
    summary="Ingest external payment provider webhook",
)
async def handle_payment_webhook(
    request: Request,
    x_signature: Annotated[str | None, Header(description="HMAC-SHA256 signature")] = None,
):
    """
    Consumes payment events, verifies cryptographic signature,
    and applies idempotent status transitions.
    """
    raw_body = await request.body()

    if not x_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required X-Signature header.",
        )

    # 1. Cryptographic HMAC verification
    if not verify_webhook_signature(raw_body, x_signature, WEBHOOK_SECRET):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook signature.",
        )

    payload = json.loads(raw_body.decode("utf-8"))
    event_id = payload.get("event_id")
    event_type = payload.get("event_type")
    data = payload.get("data", {})

    if not event_id or not event_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed webhook payload: missing event_id or event_type.",
        )

    # 2. Redis-based idempotency check on event_id
    redis = get_redis_client()
    try:
        event_key = f"webhook:processed:{event_id}"
        # Set if Not Exists with 72-hour TTL
        is_new_event = await redis.set(event_key, "1", ex=259200, nx=True)
        if not is_new_event:
            # Event already processed: return 200 immediately to acknowledge receipt
            return {"status": "success", "detail": "Event already processed (idempotent duplicate)"}

        # 3. Process payment confirmation
        if event_type == "payment.succeeded":
            invoice_id_raw = data.get("invoice_id")
            tenant_id_raw = data.get("tenant_id")

            if not invoice_id_raw or not tenant_id_raw:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing invoice_id or tenant_id in webhook data.",
                )

            invoice_uuid = uuid.UUID(invoice_id_raw)
            tenant_uuid = uuid.UUID(tenant_id_raw)

            # Open session and set context for tenant to update invoice under RLS
            async with AsyncSessionFactory() as session:
                async with session.begin():
                    from sqlalchemy import text
                    await session.execute(
                        text("SELECT set_config('app.current_tenant', :id, true)"),
                        {"id": str(tenant_uuid)},
                    )

                    result = await session.execute(
                        select(Invoice).where(Invoice.id == invoice_uuid)
                    )
                    invoice = result.scalar_one_or_none()
                    if not invoice:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail="Target invoice not found under tenant context.",
                        )

                    # Update status directly to paid
                    invoice.status = InvoiceStatus.PAID.value
                    await session.flush()

        return {"status": "success", "event_id": event_id}
    finally:
        await redis.aclose()