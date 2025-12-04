"""User service for registration and authentication."""

import random
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserRegister


class UserService:
    """Service class for user operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Get user by ID."""
        result = await self.db.execute(select(User).where(User.user_id == user_id))
        return result.scalar_one_or_none()

    async def create_user(self, user_data: UserRegister) -> User:
        """Create a new user with random weight.

        Args:
            user_data: User registration data

        Returns:
            Created user

        Raises:
            ValueError: If email already exists
        """
        # Check if email exists
        existing = await self.get_by_email(user_data.email)
        if existing:
            raise ValueError("Email already registered")

        # Generate random weight between 0.5 and 5.0
        weight = round(random.uniform(0.5, 5.0), 2)

        user = User(
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
            username=user_data.username,
            weight=Decimal(str(weight)),
            status="active",
            is_admin=False,
        )

        try:
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            return user
        except IntegrityError:
            await self.db.rollback()
            raise ValueError("Email already registered")

    async def authenticate(self, email: str, password: str) -> User | None:
        """Authenticate user by email and password.

        Args:
            email: User email
            password: Plain text password

        Returns:
            User if authentication successful, None otherwise
        """
        user = await self.get_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        if user.status != "active":
            return None
        return user
