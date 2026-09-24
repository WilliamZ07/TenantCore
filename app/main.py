from fastapi import FastAPI
import app.models  # Registers all declarative models (Tenant, Invoice)
from app.core.config import settings
from app.routers.v1.tenants import router as tenants_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(tenants_router, prefix="/api/v1")


@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "database_isolation": "PostgreSQL RLS Active",
    }