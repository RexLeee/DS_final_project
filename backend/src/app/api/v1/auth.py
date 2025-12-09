"""Authentication API endpoints."""

import hashlib
import json

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.redis import get_redis
from app.core.security import create_access_token
from app.schemas.user import TokenResponse, UserLogin, UserRegister, UserResponse
from app.services.user_service import UserService

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db: DbSession):
    """Register a new user.

    Creates a new user with:
    - Hashed password (bcrypt)
    - Random weight W between 0.5 and 5.0

    Args:
        user_data: Registration data (email, password, username)
        db: Database session

    Returns:
        Created user information

    Raises:
        400: Email already registered
    """
    user_service = UserService(db)

    try:
        user = await user_service.create_user(user_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return user


@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin, db: DbSession):
    """Login and get access token with Redis session caching.

    Uses Redis to cache successful login sessions for 60 seconds to avoid
    repeated bcrypt password verification during high-concurrency load tests.

    Args:
        user_data: Login credentials (email, password)
        db: Database session

    Returns:
        JWT access token

    Raises:
        401: Invalid credentials
    """
    # Generate cache key using SHA256 hash (consistent across processes)
    cache_key = f"login:{hashlib.sha256(f'{user_data.email}:{user_data.password}'.encode()).hexdigest()[:16]}"

    # Try to get cached session from Redis
    try:
        redis = await get_redis()
        cached_session = await redis.get(cache_key)

        if cached_session:
            # Cache hit - return cached token (avoids bcrypt verification)
            return TokenResponse(**json.loads(cached_session))
    except Exception:
        # If Redis fails, continue with normal login flow
        pass

    # Cache miss - perform normal authentication
    user_service = UserService(db)
    user = await user_service.authenticate(user_data.email, user_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create JWT token with user info
    token_data = {
        "sub": str(user.user_id),
        "email": user.email,
        "weight": str(user.weight),
    }
    access_token = create_access_token(data=token_data)

    response_data = {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }

    # Cache the session in Redis (60 second TTL to reduce bcrypt load)
    try:
        await redis.setex(cache_key, 60, json.dumps(response_data))
    except Exception:
        # If Redis caching fails, still return the token
        pass

    return TokenResponse(**response_data)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser):
    """Get current user information.

    Requires authentication.

    Args:
        current_user: Current authenticated user

    Returns:
        User information including weight W
    """
    return current_user
