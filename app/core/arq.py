from typing import Optional
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import settings


def get_redis_settings() -> RedisSettings:
    """Derives arq Redis settings from central application configuration."""
    return RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        database=0,
    )


async def create_arq_pool() -> ArqRedis:
    """Initializes and returns an ArqRedis client pool for job enqueueing."""
    return await create_pool(get_redis_settings())