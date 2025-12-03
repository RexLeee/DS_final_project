"""Campaign model for flash sale events."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.bid import Bid
    from app.models.order import Order
    from app.models.product import Product


class Campaign(Base):
    """Campaign model representing a flash sale event."""

    __tablename__ = "campaigns"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.product_id"),
        nullable=False,
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )
    alpha: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        nullable=False,
        default=Decimal("1.0000"),
    )
    beta: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        nullable=False,
        default=Decimal("1000.0000"),
    )
    gamma: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        nullable=False,
        default=Decimal("100.0000"),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default="now()",
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="campaigns")
    bids: Mapped[List["Bid"]] = relationship("Bid", back_populates="campaign")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="campaign")

    __table_args__ = (
        CheckConstraint("end_time > start_time", name="chk_campaign_time"),
        Index("idx_campaigns_status", "status"),
        Index("idx_campaigns_time", "start_time", "end_time"),
    )
