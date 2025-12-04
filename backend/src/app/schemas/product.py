"""Product schemas for request/response validation."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    """Schema for product creation request."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    image_url: str | None = Field(None, max_length=500)
    stock: int = Field(..., ge=0)
    min_price: Decimal = Field(..., gt=0)


class ProductResponse(BaseModel):
    """Schema for product response."""

    product_id: UUID
    name: str
    description: str | None
    image_url: str | None
    stock: int
    min_price: Decimal
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    """Schema for product list response."""

    products: list[ProductResponse]
    total: int
