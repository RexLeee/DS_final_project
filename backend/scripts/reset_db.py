"""Reset database to empty state.

Clears all data from:
- orders
- bids
- campaigns
- products
- users

Also clears Redis data.

Usage:
    cd backend && uv run python -m scripts.reset_db
"""

import asyncio

from sqlalchemy import text

from app.core.database import async_session_maker, engine
from app.core.redis import get_redis


async def reset_database():
    """Clear all data from the database."""
    print("=" * 60)
    print("Resetting database to empty state...")
    print("=" * 60)

    async with async_session_maker() as session:
        # Delete in correct order due to foreign key constraints
        tables = ["orders", "bids", "campaigns", "products", "users"]

        for table in tables:
            result = await session.execute(text(f"DELETE FROM {table}"))
            print(f"  Deleted {result.rowcount} rows from {table}")

        await session.commit()
        print("\nDatabase cleared successfully!")


async def reset_redis():
    """Clear all Redis data."""
    print("\nResetting Redis...")

    try:
        redis = await get_redis()
        await redis.flushdb()
        print("  Redis flushed successfully!")
        await redis.aclose()
    except Exception as e:
        print(f"  Warning: Could not clear Redis: {e}")
        print("  (This is OK if Redis is not running locally)")


async def main():
    await reset_database()
    await reset_redis()

    print("\n" + "=" * 60)
    print("Reset complete!")
    print("=" * 60)
    print("\nTo re-seed the database, run:")
    print("  cd backend && uv run python -m scripts.seed_data")
    print("=" * 60)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
