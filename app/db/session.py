import uuid
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import settings

engine = create_async_engine(
    settings.async_database_uri,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session(tenant_id: uuid.UUID) -> AsyncGenerator[AsyncSession, None]:
    """
    Yields an isolated database session with tenant context bound via set_config.
    Setting is_local=true scopes the variable strictly to the active transaction block.
    """
    session = AsyncSessionFactory()
    try:
        await session.begin()
        await session.execute(
            text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()