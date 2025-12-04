"""Rate limiting middleware using Redis Token Bucket algorithm."""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.redis import get_redis


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis.

    Rate limits (from technical_spec.md Section 3.2):
    - User level: 10 req/s (for authenticated requests)
    - IP level: 100 req/s (for all requests)
    """

    def __init__(self, app, user_limit: int = 10, ip_limit: int = 100):
        super().__init__(app)
        self.user_limit = user_limit  # 10 req/s per user
        self.ip_limit = ip_limit      # 100 req/s per IP

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
        ip_allowed, ip_retry_after = await self._check_rate_limit(
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

            user_allowed, user_retry_after = await self._check_rate_limit(
                redis, user_key, self.user_limit
            )

            if not user_allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests for this user"},
                    headers={"Retry-After": str(user_retry_after)},
                )

        return await call_next(request)

    async def _check_rate_limit(
        self, redis, key: str, limit: int, window: int = 1
    ) -> tuple[bool, int]:
        """Check rate limit using sliding window counter.

        Args:
            redis: Redis client
            key: Rate limit key
            limit: Maximum requests per window
            window: Window size in seconds

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        now = time.time()
        window_start = now - window

        # Use Redis pipeline for atomic operations
        pipe = redis.pipeline()

        # Remove old entries outside the window
        pipe.zremrangebyscore(key, 0, window_start)

        # Count current requests in window
        pipe.zcard(key)

        # Add current request
        pipe.zadd(key, {str(now): now})

        # Set expiry on the key
        pipe.expire(key, window + 1)

        results = await pipe.execute()
        current_count = results[1]

        if current_count >= limit:
            # Calculate retry after
            oldest_result = await redis.zrange(key, 0, 0, withscores=True)
            if oldest_result:
                oldest_time = oldest_result[0][1]
                retry_after = int(oldest_time + window - now) + 1
            else:
                retry_after = 1
            return False, max(1, retry_after)

        return True, 0
