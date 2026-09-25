from typing import AsyncGenerator
from redis.asyncio import ConnectionPool, Redis
from app.core.config import settings

# Shared connection pool for non-blocking asynchronous Redis commands
redis_pool = ConnectionPool.from_url(
    settings.redis_url,
    max_connections=50,
    decode_responses=True,
)


def get_redis_client() -> Redis:
    """Returns a Redis client using the shared connection pool."""
    return Redis(connection_pool=redis_pool)


async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI dependency yielding an async Redis connection."""
    client = get_redis_client()
    try:
        yield client
    finally:
        await client.aclose()