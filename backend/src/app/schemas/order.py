"""Order schemas for request/response validation."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class OrderResponse(BaseModel):
    """Schema for order response."""

    order_id: UUID
    campaign_id: UUID
    user_id: UUID
    product_id: UUID
    final_price: Decimal
    final_score: float
    final_rank: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderListResponse(BaseModel):
    """Schema for order list response."""

    orders: list[OrderResponse]
    total: int
