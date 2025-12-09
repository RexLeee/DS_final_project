"""API dependencies for authentication and database access."""

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import decode_access_token
from app.models.user import User
from app.services.redis_service import RedisService
from app.services.user_service import UserService

security = HTTPBearer()


def _user_from_cache(user_id: UUID, data: dict[str, str]) -> User:
    """Reconstruct a User object from cached data.

    Creates a detached User instance without hitting the database.
    Uses object.__setattr__ to bypass SQLAlchemy's attribute instrumentation,
    which allows us to create a valid detached object without a session.

    Args:
        user_id: User UUID
        data: Cached user data from Redis

    Returns:
        User instance (detached from session)
    """
    # Create User instance normally (this initializes _sa_instance_state)
    user = User(
        email=data.get("email", ""),
        password_hash="",  # Not cached for security
        username=data.get("username", ""),
        weight=Decimal(data.get("weight", "1.0")),
        status=data.get("status", "active"),
        is_admin=data.get("is_admin", "False").lower() == "true",
    )
    # Set user_id using object.__setattr__ to bypass SQLAlchemy instrumentation
    # since user_id is typically set by the database
    object.__setattr__(user, 'user_id', user_id)
    return user


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Get current authenticated user from JWT token with Redis caching.

    Uses Redis cache to reduce database queries for authenticated requests.
    Cache TTL is 30 seconds to balance performance and consistency.

    Args:
        credentials: HTTP Bearer token
        db: Database session

    Returns:
        Current user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Try Redis cache first
    redis = await get_redis()
    redis_service = RedisService(redis)
    cached_user = await redis_service.get_cached_user(user_id)

    if cached_user:
        # Verify user is still active
        if cached_user.get("status") != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is not active",
            )
        # Return cached user (avoids DB query)
        return _user_from_cache(user_uuid, cached_user)

    # Cache miss - query database
    user_service = UserService(db)
    user = await user_service.get_by_id(user_uuid)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active",
        )

    # Cache user for future requests
    await redis_service.cache_user(
        user_id,
        {
            "username": user.username,
            "email": user.email,
            "weight": str(user.weight),
            "status": user.status,
            "is_admin": str(user.is_admin),
        },
    )

    return user


async def get_current_admin_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current user and verify they are an admin.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user if admin

    Raises:
        HTTPException: If user is not an admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


# Type aliases for cleaner dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(get_current_admin_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
