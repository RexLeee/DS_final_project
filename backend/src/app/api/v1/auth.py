"""Authentication API endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
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
    """Login and get access token.

    Args:
        user_data: Login credentials (email, password)
        db: Database session

    Returns:
        JWT access token

    Raises:
        401: Invalid credentials
    """
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

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


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
