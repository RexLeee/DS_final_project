"""Bid model for user bidding records."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.product import Product
    from app.models.user import User


class Bid(Base):
    """Bid model representing a user's bid in a campaign."""

    __tablename__ = "bids"

    bid_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.campaign_id"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.product_id"),
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    score: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
    )
    time_elapsed_ms: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    bid_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="bids")
    user: Mapped["User"] = relationship("User", back_populates="bids")
    product: Mapped["Product"] = relationship("Product", back_populates="bids")

    __table_args__ = (
        CheckConstraint("price > 0", name="chk_bid_price_positive"),
        # Unique constraint enables PostgreSQL UPSERT for atomic operations
        Index("idx_bids_campaign_user", "campaign_id", "user_id", unique=True),
        Index("idx_bids_campaign_score", "campaign_id", "score"),
    )
