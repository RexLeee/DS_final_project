"""Redis service for ranking, inventory, locks, and campaign cache operations."""

import uuid
from typing import Any

from redis.asyncio import Redis


class RedisService:
    """Service class for Redis operations following technical_spec.md Section 2.2 and 5.1."""

    # Lua script for atomic stock decrement (check and decrement)
    DECREMENT_STOCK_SCRIPT = """
    local stock = tonumber(redis.call("GET", KEYS[1]))
    if stock and stock >= 1 then
        return redis.call("DECR", KEYS[1])
    else
        return -1
    end
    """

    # Lua script for safe lock release (only delete own lock)
    RELEASE_LOCK_SCRIPT = """
    if redis.call("GET", KEYS[1]) == ARGV[1] then
        return redis.call("DEL", KEYS[1])
    else
        return 0
    end
    """

    def __init__(self, redis: Redis):
        """Initialize Redis service with a Redis client.

        Args:
            redis: Async Redis client instance
        """
        self.redis = redis
        self._decrement_script = None
        self._release_lock_script = None

    async def _get_decrement_script(self):
        """Get or register the decrement stock Lua script."""
        if self._decrement_script is None:
            self._decrement_script = self.redis.register_script(self.DECREMENT_STOCK_SCRIPT)
        return self._decrement_script

    async def _get_release_lock_script(self):
        """Get or register the release lock Lua script."""
        if self._release_lock_script is None:
            self._release_lock_script = self.redis.register_script(self.RELEASE_LOCK_SCRIPT)
        return self._release_lock_script

    # ==================== Ranking Operations ====================

    async def update_ranking(
        self,
        campaign_id: str,
        user_id: str,
        score: float,
        price: float | None = None,
        username: str | None = None,
    ) -> None:
        """Update user's ranking in a campaign.

        Uses ZADD to add or update user's score in the sorted set.
        Also stores bid details (price, username) in a hash.
        Key pattern: bid:{campaign_id} (sorted set), bid_details:{campaign_id} (hash)

        Args:
            campaign_id: Campaign UUID string
            user_id: User UUID string
            score: Calculated score for ranking
            price: Bid price (optional)
            username: User's username (optional)
        """
        key = f"bid:{campaign_id}"
        await self.redis.zadd(key, {user_id: score})

        # Store bid details if provided
        if price is not None or username is not None:
            details_key = f"bid_details:{campaign_id}:{user_id}"
            details = {}
            if price is not None:
                details["price"] = str(price)
            if username is not None:
                details["username"] = username
            await self.redis.hset(details_key, mapping=details)

    async def get_top_k(self, campaign_id: str, k: int) -> list[dict[str, Any]]:
        """Get top K ranked users for a campaign with bid details.

        Uses ZREVRANGE to get highest scores first.
        Uses Redis Pipeline to batch fetch bid details (eliminates N+1 problem).

        Args:
            campaign_id: Campaign UUID string
            k: Number of top users to return

        Returns:
            List of dicts with user_id, score, rank, price, and username
        """
        key = f"bid:{campaign_id}"
        # ZREVRANGE returns list of (member, score) tuples with withscores=True
        results = await self.redis.zrevrange(key, 0, k - 1, withscores=True)

        if not results:
            return []

        # Use Pipeline to batch fetch all details (eliminates N+1 problem)
        pipe = self.redis.pipeline()
        for user_id, score in results:
            details_key = f"bid_details:{campaign_id}:{user_id}"
            pipe.hgetall(details_key)

        details_results = await pipe.execute()

        rankings = []
        for (rank, (user_id, score)), details in zip(
            enumerate(results, start=1), details_results
        ):
            entry = {
                "rank": rank,
                "user_id": user_id,
                "score": float(score),
            }

            if details:
                if "price" in details:
                    entry["price"] = float(details["price"])
                if "username" in details:
                    entry["username"] = details["username"]

            rankings.append(entry)
        return rankings

    async def get_user_rank(self, campaign_id: str, user_id: str) -> int | None:
        """Get user's rank in a campaign (1-based).

        Uses ZREVRANK which returns 0-based rank.

        Args:
            campaign_id: Campaign UUID string
            user_id: User UUID string

        Returns:
            1-based rank or None if user not in ranking
        """
        key = f"bid:{campaign_id}"
        rank = await self.redis.zrevrank(key, user_id)
        if rank is not None:
            return rank + 1  # Convert to 1-based
        return None

    async def get_user_score(self, campaign_id: str, user_id: str) -> float | None:
        """Get user's score in a campaign.

        Args:
            campaign_id: Campaign UUID string
            user_id: User UUID string

        Returns:
            Score or None if user not in ranking
        """
        key = f"bid:{campaign_id}"
        score = await self.redis.zscore(key, user_id)
        if score is not None:
            return float(score)
        return None

    async def get_total_participants(self, campaign_id: str) -> int:
        """Get total number of participants in a campaign.

        Args:
            campaign_id: Campaign UUID string

        Returns:
            Number of participants
        """
        key = f"bid:{campaign_id}"
        return await self.redis.zcard(key)

    async def get_min_winning_score(self, campaign_id: str, k: int) -> float | None:
        """Get the minimum score among top K (the Kth highest score).

        Args:
            campaign_id: Campaign UUID string
            k: Number of winning positions (stock)

        Returns:
            Minimum winning score or None if less than K participants
        """
        key = f"bid:{campaign_id}"
        # Get the Kth element (0-indexed, so k-1)
        results = await self.redis.zrevrange(key, k - 1, k - 1, withscores=True)
        if results:
            return float(results[0][1])
        return None

    async def get_max_score(self, campaign_id: str) -> float | None:
        """Get the maximum score in a campaign.

        Args:
            campaign_id: Campaign UUID string

        Returns:
            Maximum score or None if no participants
        """
        key = f"bid:{campaign_id}"
        results = await self.redis.zrevrange(key, 0, 0, withscores=True)
        if results:
            return float(results[0][1])
        return None

    # ==================== Inventory Operations ====================

    async def init_stock(self, product_id: str, quantity: int) -> None:
        """Initialize stock counter for a product.

        Key pattern: stock:{product_id}

        Args:
            product_id: Product UUID string
            quantity: Initial stock quantity
        """
        key = f"stock:{product_id}"
        await self.redis.set(key, quantity)

    async def get_stock(self, product_id: str) -> int:
        """Get current stock for a product.

        Args:
            product_id: Product UUID string

        Returns:
            Current stock or 0 if not set
        """
        key = f"stock:{product_id}"
        stock = await self.redis.get(key)
        return int(stock) if stock is not None else 0

    async def decrement_stock(self, product_id: str) -> int:
        """Atomically decrement stock using Lua script.

        Only decrements if stock >= 1.
        Key pattern: stock:{product_id}

        Args:
            product_id: Product UUID string

        Returns:
            New stock value after decrement, or -1 if insufficient stock
        """
        key = f"stock:{product_id}"
        script = await self._get_decrement_script()
        result = await script(keys=[key])
        return int(result)

    async def increment_stock(self, product_id: str) -> int:
        """Increment stock (for rollback scenarios).

        Args:
            product_id: Product UUID string

        Returns:
            New stock value after increment
        """
        key = f"stock:{product_id}"
        return await self.redis.incr(key)

    # ==================== Distributed Lock Operations ====================

    async def acquire_lock(
        self, product_id: str, owner_id: str | None = None, ttl: int = 2
    ) -> tuple[bool, str]:
        """Acquire a distributed lock for a product.

        Key pattern: lock:product:{product_id}
        Uses SET NX EX for atomic lock acquisition.

        Args:
            product_id: Product UUID string
            owner_id: Unique identifier for lock owner (auto-generated if None)
            ttl: Lock timeout in seconds (default 2s to prevent deadlock)

        Returns:
            Tuple of (success, owner_id)
        """
        key = f"lock:product:{product_id}"
        if owner_id is None:
            owner_id = str(uuid.uuid4())

        acquired = await self.redis.set(key, owner_id, nx=True, ex=ttl)
        return (acquired is not None, owner_id)

    async def release_lock(self, product_id: str, owner_id: str) -> bool:
        """Release a distributed lock (only if owner matches).

        Uses Lua script to ensure only the lock owner can release.

        Args:
            product_id: Product UUID string
            owner_id: The owner_id returned from acquire_lock

        Returns:
            True if lock was released, False if not owner or not locked
        """
        key = f"lock:product:{product_id}"
        script = await self._get_release_lock_script()
        result = await script(keys=[key], args=[owner_id])
        return int(result) == 1

    # ==================== Campaign Cache Operations ====================

    async def cache_campaign(
        self, campaign_id: str, data: dict[str, Any], ttl: int | None = None
    ) -> None:
        """Cache campaign parameters in Redis Hash.

        Key pattern: campaign:{campaign_id}

        Args:
            campaign_id: Campaign UUID string
            data: Campaign data dict (all values will be converted to strings)
            ttl: Optional TTL in seconds
        """
        key = f"campaign:{campaign_id}"
        # Convert all values to strings for Redis hash
        string_data = {k: str(v) for k, v in data.items()}
        await self.redis.hset(key, mapping=string_data)
        if ttl is not None:
            await self.redis.expire(key, ttl)

    async def get_cached_campaign(self, campaign_id: str) -> dict[str, str] | None:
        """Get cached campaign parameters.

        Args:
            campaign_id: Campaign UUID string

        Returns:
            Campaign data dict or None if not cached
        """
        key = f"campaign:{campaign_id}"
        data = await self.redis.hgetall(key)
        return data if data else None

    async def invalidate_campaign_cache(self, campaign_id: str) -> bool:
        """Invalidate (delete) campaign cache.

        Args:
            campaign_id: Campaign UUID string

        Returns:
            True if cache was deleted, False if didn't exist
        """
        key = f"campaign:{campaign_id}"
        result = await self.redis.delete(key)
        return result > 0

    async def set_campaign_ttl(self, campaign_id: str, ttl: int) -> bool:
        """Set TTL on existing campaign cache.

        Args:
            campaign_id: Campaign UUID string
            ttl: TTL in seconds

        Returns:
            True if TTL was set, False if key doesn't exist
        """
        key = f"campaign:{campaign_id}"
        return await self.redis.expire(key, ttl)


    # ==================== User Cache Operations ====================

    USER_CACHE_TTL = 30  # 30 seconds TTL for user cache

    async def cache_user(self, user_id: str, user_data: dict[str, Any]) -> None:
        """Cache user data in Redis Hash with short TTL.

        Key pattern: user:{user_id}

        Args:
            user_id: User UUID string
            user_data: User data dict (values will be converted to strings)
        """
        key = f"user:{user_id}"
        # Convert all values to strings for Redis hash
        string_data = {k: str(v) for k, v in user_data.items()}
        pipe = self.redis.pipeline()
        pipe.hset(key, mapping=string_data)
        pipe.expire(key, self.USER_CACHE_TTL)
        await pipe.execute()

    async def get_cached_user(self, user_id: str) -> dict[str, str] | None:
        """Get cached user data.

        Args:
            user_id: User UUID string

        Returns:
            User data dict or None if not cached
        """
        key = f"user:{user_id}"
        data = await self.redis.hgetall(key)
        return data if data else None

    async def invalidate_user_cache(self, user_id: str) -> bool:
        """Invalidate (delete) user cache.

        Should be called when user status changes.

        Args:
            user_id: User UUID string

        Returns:
            True if cache was deleted, False if didn't exist
        """
        key = f"user:{user_id}"
        result = await self.redis.delete(key)
        return result > 0

    # ==================== Campaign Stats Batch Operations ====================

    async def get_campaign_stats_batch(
        self, campaign_id: str, k: int
    ) -> dict[str, Any]:
        """Get all campaign stats in a single pipeline call.

        Combines total participants, max score, and min winning score queries.

        Args:
            campaign_id: Campaign UUID string
            k: Number of winning positions (stock)

        Returns:
            Dict with total_participants, max_score, min_winning_score
        """
        key = f"bid:{campaign_id}"

        pipe = self.redis.pipeline()
        pipe.zcard(key)  # total participants
        pipe.zrevrange(key, 0, 0, withscores=True)  # max score (rank 1)
        pipe.zrevrange(key, k - 1, k - 1, withscores=True)  # Kth score (min winning)

        results = await pipe.execute()

        total = results[0]
        max_score = float(results[1][0][1]) if results[1] else None
        min_winning = float(results[2][0][1]) if results[2] else None

        return {
            "total_participants": total,
            "max_score": max_score,
            "min_winning_score": min_winning,
        }


# Dependency injection helper
async def get_redis_service(redis: Redis) -> RedisService:
    """Create a RedisService instance.

    Args:
        redis: Redis client from get_redis()

    Returns:
        RedisService instance
    """
    return RedisService(redis)
