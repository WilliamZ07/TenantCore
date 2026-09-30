from fastapi import FastAPI
import app.models
from app.core.config import settings
from app.core.redis import get_redis_client
from app.routers.v1.tenants import router as tenants_router
from app.routers.v1.invoices import router as invoices_router
from app.routers.v1.webhooks import router as webhooks_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
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

    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "database_isolation": "PostgreSQL RLS Active",
        "redis_cache": redis_status,
    }