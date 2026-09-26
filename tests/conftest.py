import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.redis import redis_pool
from app.db.session import engine
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def cleanup_pools():
    """
    Guarantees all pooled connections (PostgreSQL and Redis) are cleanly closed
    inside the active test's event loop, preventing loop-mismatch errors in
    subsequent tests.
    """
    yield
    await engine.dispose()
    await redis_pool.disconnect()


@pytest_asyncio.fixture
async def client():
    """Provides an isolated HTTP async test client bound to the FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac