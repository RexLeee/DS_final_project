from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    # Optimized for high-concurrency 1000 VU load testing with PgBouncer
    # Formula: maxReplicas(50) × workers(1) × pool_size(8) = 400 app connections
    # PgBouncer: 6 pods × 30 max_db_connections = 180 DB connections
    # Cloud SQL max_connections should be set to 200 in GCP Console
    pool_size=8,           # Increased for high concurrency (was 5)
    max_overflow=15,       # Increased burst capacity (was 10)
    pool_timeout=30,       # Increased to prevent pool exhaustion errors (was 3)
    pool_recycle=180,      # Connection recycling for freshness
    pool_pre_ping=True,    # Verify connection health before use
    # PgBouncer transaction mode requires disabling prepared statement cache
    # This is critical for proper connection multiplexing
    connect_args={
        "prepared_statement_cache_size": 0,
        "command_timeout": 30,  # Increased for high concurrency (was 10)
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
