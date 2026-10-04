from contextlib import asynccontextmanager
from fastapi import FastAPI

import app.models
from app.core.arq import create_arq_pool
from app.core.config import settings
from app.core.redis import get_redis_client
from app.db.session import engine
from app.routers.v1.invoices import router as invoices_router
from app.routers.v1.tenants import router as tenants_router
from app.routers.v1.webhooks import router as webhooks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize the arq Redis client pool and bind to app.state
    app.state.arq_pool = await create_arq_pool()
    yield
    # Shutdown: Cleanly drain and close the background pool and database engine
    await app.state.arq_pool.close()
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.include_router(tenants_router, prefix="/api/v1")
app.include_router(invoices_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")


@app.get("/health", tags=["System"])
async def health_check():
    redis_client = get_redis_client()
    redis_status = "unhealthy"
    try:
        if await redis_client.ping():
            redis_status = "connected"
    except Exception as e:
        redis_status = f"error: {str(e)}"
    finally:
        await redis_client.aclose()

    arq_status = (
        "ready"
        if hasattr(app.state, "arq_pool") and app.state.arq_pool
        else "unavailable"
    )

    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "database_isolation": "PostgreSQL RLS Active",
        "redis_cache": redis_status,
        "task_queue": arq_status,
    }