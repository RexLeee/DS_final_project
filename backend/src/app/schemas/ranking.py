"""Ranking schemas for request/response validation."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class RankingItem(BaseModel):
    """Schema for a single ranking item."""

    rank: int
    user_id: UUID
    username: str
    score: float
    price: Decimal


class RankingResponse(BaseModel):
    """Schema for ranking response."""

    campaign_id: UUID
    total_participants: int
    rankings: list[RankingItem]
    min_winning_score: float | None
    max_score: float | None
    updated_at: datetime


class MyRankResponse(BaseModel):
    """Schema for user's own rank in a campaign."""

    campaign_id: UUID
    user_id: UUID
    rank: int | None
    score: float | None
    is_winning: bool
    total_participants: int
