import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_tenant, get_isolated_db, rate_limit
from app.core.redis import get_redis
from app.models.invoice import Invoice
from app.models.tenant import Tenant
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceResponse,
    InvoiceStatus,
    InvoiceStatusUpdate,
    VALID_TRANSITIONS,
)
from app.services.idempotency import IdempotencyService

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.post(
    "",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new invoice (idempotent)",
    dependencies=[Depends(rate_limit(limit=30, window_seconds=60))],
)
async def create_invoice(
    payload: InvoiceCreate,
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_isolated_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    idempotency_key: Annotated[str | None, Header(description="Unique client idempotency key")] = None,
):
    """
    Creates an invoice under the authenticated tenant's RLS scope with idempotency support.
    """
    idempotency_service = IdempotencyService(redis)

    if idempotency_key:
        # 1. Check for previously cached execution
        cached = await idempotency_service.get_cached_response(tenant.id, idempotency_key)
        if cached:
            if cached.get("status") == "processing":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A request with this Idempotency-Key is currently in progress.",
                )
            return JSONResponse(
                status_code=cached["status_code"],
                content=cached["body"],
                headers={"X-Cache-Lookup": "HIT - Idempotent Replay"},
            )

        # 2. Acquire in-flight lock
        locked = await idempotency_service.lock_key(tenant.id, idempotency_key)
        if not locked:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A concurrent request with this Idempotency-Key is already running.",
            )

    # 3. Execute business logic under RLS
    invoice = Invoice(
        tenant_id=tenant.id,
        customer_name=payload.customer_name,
        amount=payload.amount,
        currency=payload.currency,
        status=InvoiceStatus.DRAFT.value,
    )
    db.add(invoice)
    await db.flush()
    await db.refresh(invoice)

    response_data = {
        "id": str(invoice.id),
        "tenant_id": str(invoice.tenant_id),
        "customer_name": invoice.customer_name,
        "amount": str(invoice.amount),
        "currency": invoice.currency,
        "status": invoice.status,
        "created_at": invoice.created_at.isoformat(),
    }

    # 4. Cache response if idempotency key was supplied
    if idempotency_key:
        await idempotency_service.store_response(
            tenant_id=tenant.id,
            idempotency_key=idempotency_key,
            status_code=status.HTTP_201_CREATED,
            response_body=response_data,
        )

    return response_data


@router.get(
    "",
    response_model=list[InvoiceResponse],
    summary="List all invoices for authenticated tenant",
    dependencies=[Depends(rate_limit(limit=60, window_seconds=60))],
)
async def list_invoices(
    db: Annotated[AsyncSession, Depends(get_isolated_db)],
):
    """
    Returns all invoices visible to the current transaction.
    Zero application-level tenant filtering: Postgres RLS automatically filters rows.
    """
    result = await db.execute(select(Invoice).order_by(Invoice.created_at.desc()))
    return result.scalars().all()


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Get invoice by ID",
    dependencies=[Depends(rate_limit(limit=60, window_seconds=60))],
)
async def get_invoice(
    invoice_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_isolated_db)],
):
    """
    Fetches a single invoice. Returns 404 if the invoice does not exist OR
    if it belongs to another tenant (RLS hides the row entirely).
    """
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found.",
        )
    return invoice


@router.patch(
    "/{invoice_id}/status",
    response_model=InvoiceResponse,
    summary="Transition invoice status",
    dependencies=[Depends(rate_limit(limit=30, window_seconds=60))],
)
async def update_invoice_status(
    invoice_id: uuid.UUID,
    payload: InvoiceStatusUpdate,
    db: Annotated[AsyncSession, Depends(get_isolated_db)],
):
    """
    Transitions invoice through the financial state machine:
    draft -> issued -> paid / void
    """
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found.",
        )

    current_status = InvoiceStatus(invoice.status)
    new_status = payload.status

    allowed_next_states = VALID_TRANSITIONS.get(current_status, set())
    if new_status not in allowed_next_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Illegal state transition from '{current_status.value}' to '{new_status.value}'. "
                f"Allowed transitions: {[s.value for s in allowed_next_states]}"
            ),
        )

    invoice.status = new_status.value
    await db.flush()
    await db.refresh(invoice)
    return invoice