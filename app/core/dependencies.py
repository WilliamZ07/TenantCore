from typing import Annotated, AsyncGenerator
from fastapi import Depends, Header, HTTPException, Response, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.core.security import hash_api_key
from app.db.session import AsyncSessionFactory, get_db_session
from app.models.tenant import Tenant
from app.services.rate_limiter import SlidingWindowRateLimiter


async def get_api_key(
    x_api_key: Annotated[str | None, Header(description="Tenant API secret key")] = None,
) -> str:
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
    async for session in get_db_session(tenant_id=tenant.id):
        yield session


def rate_limit(limit: int = 60, window_seconds: int = 60):
    """
    Dependency factory that enforces a sliding window rate limit per tenant.
    Injects standard RFC HTTP rate-limiting headers.
    """
    async def dependency(
        tenant: Annotated[Tenant, Depends(get_current_tenant)],
        redis: Annotated[Redis, Depends(get_redis)],
        response: Response,
    ) -> None:
        limiter = SlidingWindowRateLimiter(redis)
        result = await limiter.check_rate_limit(
            tenant_id=tenant.id,
            action="api",
            limit=limit,
            window_seconds=window_seconds,
        )

        # Inject standard rate limit headers
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset_seconds)

        if not result.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Quota: {limit} requests per {window_seconds}s.",
                headers={"Retry-After": str(result.reset_seconds)},
            )

    return dependency