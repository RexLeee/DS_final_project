"""User model for member data."""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, List

from sqlalchemy import Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.bid import Bid
    from app.models.order import Order


class User(Base, TimestampMixin):
    """User model representing a member."""

    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    username: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    weight: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("1.00"),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
    )

    # Relationships
    bids: Mapped[List["Bid"]] = relationship("Bid", back_populates="user")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="user")

    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_status", "status"),
    )
