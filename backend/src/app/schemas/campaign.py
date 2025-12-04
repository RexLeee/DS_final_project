"""Campaign schemas for request/response validation."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.product import ProductResponse


class CampaignCreate(BaseModel):
    """Schema for campaign creation request."""

    product_id: UUID
    start_time: datetime
    end_time: datetime
    alpha: Decimal = Field(default=Decimal("1.0"))
    beta: Decimal = Field(default=Decimal("1000.0"))
    gamma: Decimal = Field(default=Decimal("100.0"))


class CampaignStats(BaseModel):
    """Schema for campaign statistics."""

    total_participants: int = 0
    max_price: Decimal | None = None
    min_winning_score: float | None = None


class CampaignResponse(BaseModel):
    """Schema for campaign response."""

    campaign_id: UUID
    product_id: UUID
    start_time: datetime
    end_time: datetime
    alpha: Decimal
    beta: Decimal
    gamma: Decimal
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CampaignDetailResponse(BaseModel):
    """Schema for campaign detail response with product and stats."""

    campaign_id: UUID
    product: ProductResponse
    start_time: datetime
    end_time: datetime
    alpha: Decimal
    beta: Decimal
    gamma: Decimal
    status: str
    stats: CampaignStats
    created_at: datetime


class CampaignListResponse(BaseModel):
    """Schema for campaign list response."""

    campaigns: list[CampaignResponse]
    total: int
