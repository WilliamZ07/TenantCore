from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_tenant, get_isolated_db
from app.core.security import generate_tenant_api_key
from app.db.session import AsyncSessionFactory
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate, TenantProvisionResponse, TenantResponse

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.post(
    "",
    response_model=TenantProvisionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Onboard a new corporate tenant",
)
async def register_tenant(payload: TenantCreate):
    """
    Provisions a new tenant, hashes the generated API key,
    and returns the raw secret key exactly once.
    """
    plaintext_key, key_hash = generate_tenant_api_key()

    async with AsyncSessionFactory() as session:
        async with session.begin():
            tenant = Tenant(
                name=payload.name,
                api_key_hash=key_hash,
                is_active=True,
            )
            session.add(tenant)
            await session.flush()
            await session.refresh(tenant)

    return TenantProvisionResponse(
        id=tenant.id,
        name=tenant.name,
        is_active=tenant.is_active,
        created_at=tenant.created_at,
        api_key=plaintext_key,
    )


@router.get(
    "/me",
    response_model=TenantResponse,
    summary="Get authenticated tenant metadata",
)
async def get_authenticated_tenant_profile(
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
):
    """
    Returns metadata for the calling tenant.
    Demonstrates zero-trust API key resolution through our dependency chain.
    """
    return tenant