"""Product management API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import AdminUser, DbSession
from app.core.redis import get_redis
from app.schemas.product import ProductCreate, ProductListResponse, ProductResponse
from app.services.product_service import ProductService
from app.services.redis_service import RedisService

router = APIRouter()


@router.get("", response_model=ProductListResponse)
async def list_products(
    db: DbSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    """Get all products with pagination."""
    service = ProductService(db)
    products, total = await service.get_all(skip=skip, limit=limit)
    return ProductListResponse(products=products, total=total)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    db: DbSession,
):
    """Get product by ID."""
    service = ProductService(db)
    product = await service.get_by_id(product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return product


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_data: ProductCreate,
    db: DbSession,
    admin: AdminUser,
):
    """Create a new product (admin only)."""
    redis_client = await get_redis()
    redis_service = RedisService(redis_client)
    service = ProductService(db, redis_service)
    product = await service.create(product_data)
    return product
