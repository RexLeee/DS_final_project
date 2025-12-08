"""Order query API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.schemas.order import CampaignOrdersResponse, OrderListResponse, OrderResponse
from app.services.campaign_service import CampaignService
from app.services.order_service import OrderService

router = APIRouter()


@router.get("", response_model=OrderListResponse)
async def get_my_orders(
    db: DbSession,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    """Get current user's orders."""
    service = OrderService(db)
    orders, total = await service.get_user_orders(
        user_id=current_user.user_id,
        skip=skip,
        limit=limit,
    )

    return OrderListResponse(
        orders=[
            OrderResponse(
                order_id=o.order_id,
                campaign_id=o.campaign_id,
                user_id=o.user_id,
                product_id=o.product_id,
                final_price=o.final_price,
                final_score=float(o.final_score),
                final_rank=o.final_rank,
                status=o.status,
                created_at=o.created_at,
            )
            for o in orders
        ],
        total=total,
    )


@router.get("/campaign/{campaign_id}", response_model=CampaignOrdersResponse)
async def get_campaign_orders(
    campaign_id: UUID,
    db: DbSession,
    admin_user: AdminUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get orders for a specific campaign (admin only).

    Used for consistency verification after load testing.
    PDF Requirement: 證明沒有超賣（成交數≦庫存數）

    Args:
        campaign_id: Campaign UUID
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return

    Returns:
        Campaign orders with consistency check result
    """
    # Get campaign with product info
    campaign_service = CampaignService(db)
    campaign = await campaign_service.get_by_id(campaign_id)

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign {campaign_id} not found",
        )

    # Get stock from product
    stock = campaign.product.stock if campaign.product else 0

    # Get orders
    order_service = OrderService(db)
    orders, total = await order_service.get_campaign_orders(
        campaign_id=campaign_id,
        skip=skip,
        limit=limit,
    )

    # Check consistency: orders <= stock
    is_consistent = total <= stock

    return CampaignOrdersResponse(
        campaign_id=campaign_id,
        orders=[
            OrderResponse(
                order_id=o.order_id,
                campaign_id=o.campaign_id,
                user_id=o.user_id,
                product_id=o.product_id,
                final_price=o.final_price,
                final_score=float(o.final_score),
                final_rank=o.final_rank,
                status=o.status,
                created_at=o.created_at,
            )
            for o in orders
        ],
        total=total,
        stock=stock,
        is_consistent=is_consistent,
    )
