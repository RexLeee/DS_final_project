from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    # Optimized for 12 vCPU GCP quota limit with PgBouncer
    # Formula: maxReplicas(12) × workers(1) × (pool_size + max_overflow) = 12 × 25 = 300 max app connections
    # PgBouncer: 6 pods × 30 max_db_connections = 180 DB connections
    # Cloud SQL max_connections should be set to 200 in GCP Console
    pool_size=15,          # Base pool size per pod
    max_overflow=10,       # Reduced to prevent exceeding PgBouncer capacity (was 25)
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
