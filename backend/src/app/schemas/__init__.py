"""Pydantic schemas for request/response validation."""

from app.schemas.bid import BidCreate, BidHistoryResponse, BidResponse
from app.schemas.campaign import (
    CampaignCreate,
    CampaignDetailResponse,
    CampaignListResponse,
    CampaignResponse,
    CampaignStats,
)
from app.schemas.product import ProductCreate, ProductListResponse, ProductResponse
from app.schemas.user import TokenResponse, UserLogin, UserRegister, UserResponse

__all__ = [
    "UserRegister",
    "UserLogin",
    "UserResponse",
    "TokenResponse",
    "ProductCreate",
    "ProductResponse",
    "ProductListResponse",
    "CampaignCreate",
    "CampaignResponse",
    "CampaignDetailResponse",
    "CampaignListResponse",
    "CampaignStats",
    "BidCreate",
    "BidResponse",
    "BidHistoryResponse",
]
