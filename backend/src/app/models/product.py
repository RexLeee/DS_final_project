"""Product model for merchandise data."""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, List

from sqlalchemy import CheckConstraint, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.bid import Bid
    from app.models.campaign import Campaign
    from app.models.order import Order


class Product(Base, TimestampMixin):
    """Product model representing a merchandise item."""

    __tablename__ = "products"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    image_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    stock: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    min_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
    )

    # Relationships
    campaigns: Mapped[List["Campaign"]] = relationship(
        "Campaign", back_populates="product"
    )
    bids: Mapped[List["Bid"]] = relationship("Bid", back_populates="product")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="product")

    __table_args__ = (
        CheckConstraint("stock >= 0", name="chk_product_stock_positive"),
        CheckConstraint("min_price > 0", name="chk_product_min_price_positive"),
    )
