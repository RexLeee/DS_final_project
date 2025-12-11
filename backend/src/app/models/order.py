"""Order model for successful bids."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.product import Product
    from app.models.user import User


class Order(Base):
    """Order model representing a successful bid/purchase."""

    __tablename__ = "orders"

    order_id: Mapped[uuid.UUID] = mapped_column(
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
    final_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    final_score: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False,
    )
    final_rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="orders")
    user: Mapped["User"] = relationship("User", back_populates="orders")
    product: Mapped["Product"] = relationship("Product", back_populates="orders")

    __table_args__ = (
        CheckConstraint("final_rank > 0", name="chk_order_rank_positive"),
        UniqueConstraint("campaign_id", "user_id", name="uq_order_campaign_user"),
        # P2 Optimization: Composite indexes for common query patterns
        # ORDER BY created_at DESC queries with campaign_id or user_id filter
        Index("idx_orders_campaign_created", "campaign_id", "created_at"),
        Index("idx_orders_user_created", "user_id", "created_at"),
        Index("idx_orders_status", "status"),
    )
