from typing import Annotated, AsyncGenerator
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_api_key
from app.db.session import AsyncSessionFactory, get_db_session
from app.models.tenant import Tenant


async def get_api_key(
    x_api_key: Annotated[str | None, Header(description="Tenant API secret key")] = None,
) -> str:
    """Extracts and validates the presence of the X-API-KEY header."""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required API key. Provide header: 'X-API-KEY'.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key.strip()


async def get_current_tenant(
    api_key: Annotated[str, Depends(get_api_key)],
) -> Tenant:
    """
    Authenticates tenant via SHA-256 hash lookup.
    Executes without pre-injected tenant context because app.current_tenant is NULL,
    which satisfies our tenant_self_isolation_policy bootstrap rule.
    """
    key_hash = hash_api_key(api_key)

    async with AsyncSessionFactory() as session:
        query = select(Tenant).where(Tenant.api_key_hash == key_hash)
        result = await session.execute(query)
        tenant = result.scalar_one_or_none()

        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API key credentials.",
            )

        if not tenant.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant account is deactivated. Contact platform support.",
            )

        return tenant


async def get_isolated_db(
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency yielding an isolated SQLAlchemy session bound strictly to the caller tenant.
    All queries executed on this session have PostgreSQL RLS policies applied.
    """
    async for session in get_db_session(tenant_id=tenant.id):
        yield session