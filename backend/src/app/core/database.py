from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    # Optimized for high concurrency with PgBouncer
    # PgBouncer handles connection multiplexing, allowing more app-level connections
    pool_size=8,           # Increased for 1000 VU load testing
    max_overflow=15,       # More burst capacity for flash sale peaks
    pool_timeout=5,        # Fail-fast: reduced from 10s to prevent request queuing
    pool_recycle=300,      # Reduced from 1800 to prevent stale connections
    pool_pre_ping=True,    # Verify connection health before use
    # PgBouncer transaction mode requires disabling prepared statement cache
    # This is critical for proper connection multiplexing
    connect_args={
        "prepared_statement_cache_size": 0,
    },
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
