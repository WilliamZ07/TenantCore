from typing import Annotated
from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_current_tenant, rate_limit
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
    dependencies=[Depends(rate_limit(limit=10, window_seconds=60))],
)
async def get_authenticated_tenant_profile(
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
):
    return tenant