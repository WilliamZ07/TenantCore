from typing import Any, Dict
import httpx
from arq.connections import RedisSettings

from app.core.arq import get_redis_settings
from app.tasks.webhooks import dispatch_webhook


async def startup(ctx: Dict[Any, Any]) -> None:
    """Pre-warms an HTTP client session across worker executions."""
    ctx["http_client"] = httpx.AsyncClient(timeout=10.0)


async def shutdown(ctx: Dict[Any, Any]) -> None:
    """Gracefully disposes worker resources on shutdown."""
    client: httpx.AsyncClient = ctx.get("http_client")
    if client:
        await client.aclose()


class WorkerSettings:
    """arq Worker process configuration."""

    functions = [dispatch_webhook]
    redis_settings: RedisSettings = get_redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 20
    job_timeout = 60