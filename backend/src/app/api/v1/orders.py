"""Order query API endpoints."""

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.order import OrderListResponse, OrderResponse
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
