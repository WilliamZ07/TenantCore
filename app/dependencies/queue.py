from arq.connections import ArqRedis
from fastapi import Request


async def get_queue(request: Request) -> ArqRedis | None:
    """Provides the active arq Redis client pool from application state if available."""
    return getattr(request.app.state, "arq_pool", None)