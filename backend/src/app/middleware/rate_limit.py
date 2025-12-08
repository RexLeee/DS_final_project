"""Rate limiting middleware using Redis with Lua script optimization."""

import random
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.redis import get_redis


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis with atomic Lua script.

    Rate limits (from technical_spec.md Section 3.2):
    - User level: 10 req/s (for authenticated requests)
    - IP level: 100 req/s (for all requests)

    Optimized with Lua script to reduce 4+ Redis operations to 1 atomic call.
    """

    # Lua script for atomic rate limit check (replaces 4+ Redis operations with 1)
    RATE_LIMIT_SCRIPT = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local limit = tonumber(ARGV[3])
    local request_id = ARGV[4]
    local window_start = now - window

    -- Remove old entries outside the window
    redis.call('ZREMRANGEBYSCORE', key, 0, window_start)

    -- Count current requests in window
    local count = redis.call('ZCARD', key)

    if count < limit then
        -- Add new request with unique ID to prevent collisions
        redis.call('ZADD', key, now, request_id)
        redis.call('EXPIRE', key, window + 1)
        return {1, 0}  -- allowed, retry_after=0
    else
        -- Get oldest entry for retry-after calculation
        local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
        local retry_after = 1
        if oldest and #oldest >= 2 then
            retry_after = math.ceil(oldest[2] + window - now) + 1
            if retry_after < 1 then retry_after = 1 end
        end
        return {0, retry_after}  -- not allowed, retry_after
    end
    """

    def __init__(self, app, user_limit: int = 10, ip_limit: int = 100):
        super().__init__(app)
        self.user_limit = user_limit  # 10 req/s per user
        self.ip_limit = ip_limit      # 100 req/s per IP
        self._rate_limit_script = None

    async def _get_rate_limit_script(self, redis):
        """Get or register the rate limit Lua script."""
        if self._rate_limit_script is None:
            self._rate_limit_script = redis.register_script(self.RATE_LIMIT_SCRIPT)
        return self._rate_limit_script

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"

        try:
            redis = await get_redis()
        except Exception:
            # If Redis unavailable, allow request
            return await call_next(request)

        # Check IP rate limit
        ip_key = f"ratelimit:ip:{client_ip}"
        ip_allowed, ip_retry_after = await self._check_rate_limit_lua(
            redis, ip_key, self.ip_limit
        )

        if not ip_allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests from this IP"},
                headers={"Retry-After": str(ip_retry_after)},
            )

        # Check user rate limit (if authenticated)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            # Extract user_id from JWT (simplified - in production decode JWT)
            # For now, use the token hash as identifier
            token = auth_header[7:]
            user_key = f"ratelimit:user:{hash(token) % 10000000}"

            user_allowed, user_retry_after = await self._check_rate_limit_lua(
                redis, user_key, self.user_limit
            )

            if not user_allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests for this user"},
                    headers={"Retry-After": str(user_retry_after)},
                )

        return await call_next(request)

    async def _check_rate_limit_lua(
        self, redis, key: str, limit: int, window: int = 1
    ) -> tuple[bool, int]:
        """Check rate limit using atomic Lua script.

        Combines all rate limit operations into a single atomic Redis call:
        1. Remove expired entries
        2. Count current entries
        3. Add new entry (if allowed)
        4. Set TTL

        Args:
            redis: Redis client
            key: Rate limit key
            limit: Maximum requests per window
            window: Window size in seconds

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        now = time.time()
        # Generate unique request ID to prevent score collisions
        request_id = f"{now}:{random.randint(0, 999999)}"

        script = await self._get_rate_limit_script(redis)
        result = await script(
            keys=[key],
            args=[now, window, limit, request_id],
        )

        allowed = bool(result[0])
        retry_after = int(result[1])

        return allowed, retry_after
