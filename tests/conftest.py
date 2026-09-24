import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.session import engine
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db_pool():
    """
    Guarantees all pooled connections are cleanly closed inside the active test's
    event loop, preventing loop-mismatch errors in subsequent tests.
    """
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    """Provides an isolated HTTP async test client bound to the FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac