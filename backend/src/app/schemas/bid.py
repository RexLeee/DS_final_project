"""Bid schemas for request/response validation."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class BidCreate(BaseModel):
    """Schema for bid creation request."""

    campaign_id: UUID
    price: Decimal = Field(..., gt=0)


class BidResponse(BaseModel):
    """Schema for bid response."""

    bid_id: UUID
    campaign_id: UUID
    user_id: UUID
    price: Decimal
    score: float
    rank: int
    time_elapsed_ms: int
    bid_number: int
    created_at: datetime

    model_config = {"from_attributes": True}


class BidHistoryResponse(BaseModel):
    """Schema for bid history response."""

    bids: list[BidResponse]
    total: int
