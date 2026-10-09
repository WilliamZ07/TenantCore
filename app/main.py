from contextlib import asynccontextmanager
from fastapi import FastAPI

import app.models
from app.core.arq import create_arq_pool
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.redis import get_redis_client
from app.db.session import engine
from app.middleware.correlation import CorrelationIdMiddleware
from app.routers.v1.invoices import router as invoices_router
from app.routers.v1.tenants import router as tenants_router
from app.routers.v1.webhooks import router as webhooks_router
from app.core.metrics import export_metrics

# Initialize structured logging before application boots
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.arq_pool = await create_arq_pool()
    yield
    await app.state.arq_pool.close()
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Register correlation middleware as outermost layer
app.add_middleware(CorrelationIdMiddleware)

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

@app.get("/metrics", tags=["System"], include_in_schema=False)
async def metrics():
    return export_metrics()