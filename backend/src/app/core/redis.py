from typing import Optional

import redis.asyncio as redis
from redis.asyncio import ConnectionPool

from app.core.config import settings

redis_pool: Optional[ConnectionPool] = None
redis_client: Optional[redis.Redis] = None


def get_redis_pool() -> ConnectionPool:
    """Get or create Redis connection pool with optimized settings."""
    global redis_pool
    if redis_pool is None:
        redis_pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=100,           # Limit connections per worker
            decode_responses=True,
            encoding="utf-8",
            socket_timeout=5.0,            # Prevent hanging connections
            socket_connect_timeout=5.0,    # Fast connect timeout
            retry_on_timeout=True,         # Auto-retry on timeout
        )
    return redis_pool


async def get_redis() -> redis.Redis:
    """Get Redis client using connection pool."""
    global redis_client
    if redis_client is None:
        pool = get_redis_pool()
        redis_client = redis.Redis(connection_pool=pool)
    return redis_client


async def close_redis() -> None:
    """Close Redis client and connection pool."""
    global redis_client, redis_pool
    if redis_client is not None:
        await redis_client.close()
        redis_client = None
    if redis_pool is not None:
        await redis_pool.disconnect()
        redis_pool = None
