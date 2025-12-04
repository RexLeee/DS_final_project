"""Bidding API endpoints."""

import asyncio
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.core.redis import get_redis
from app.models.campaign import Campaign
from app.schemas.bid import BidCreate, BidHistoryResponse, BidResponse
from app.services.bid_service import BidService
from app.services.redis_service import RedisService
from app.services.ws_manager import send_bid_accepted

router = APIRouter()


@router.post("", response_model=BidResponse, status_code=status.HTTP_201_CREATED)
async def submit_bid(
    bid_data: BidCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Submit or update a bid for a campaign."""
    redis_client = await get_redis()
    redis_service = RedisService(redis_client)
    bid_service = BidService(db, redis_service)

    # Validate campaign
    campaign, error_code = await bid_service.get_campaign_with_validation(bid_data.campaign_id)

    if error_code == "CAMPAIGN_NOT_FOUND":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )
    elif error_code == "CAMPAIGN_NOT_STARTED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "CAMPAIGN_NOT_STARTED", "message": "Campaign has not started yet"},
        )
    elif error_code == "CAMPAIGN_ENDED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "CAMPAIGN_ENDED", "message": "Campaign has ended"},
        )

    # Get campaign params (try Redis cache first, fall back to DB)
    cached_params = await redis_service.get_cached_campaign(str(bid_data.campaign_id))

    if cached_params:
        alpha = Decimal(cached_params["alpha"])
        beta = Decimal(cached_params["beta"])
        gamma = Decimal(cached_params["gamma"])
        min_price = Decimal(cached_params["min_price"])
        product_id = UUID(cached_params["product_id"])
    else:
        # Load from database with product
        from sqlalchemy import select
        result = await db.execute(
            select(Campaign)
            .options(selectinload(Campaign.product))
            .where(Campaign.campaign_id == bid_data.campaign_id)
        )
        campaign_with_product = result.scalar_one()
        alpha = campaign_with_product.alpha
        beta = campaign_with_product.beta
        gamma = campaign_with_product.gamma
        min_price = campaign_with_product.product.min_price
        product_id = campaign_with_product.product_id

    # Validate price
    if bid_data.price < min_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PRICE_TOO_LOW", "message": f"Price must be at least {min_price}"},
        )

    # Create or update bid
    try:
        bid, rank = await bid_service.create_or_update_bid(
            campaign_id=bid_data.campaign_id,
            user=current_user,
            price=bid_data.price,
            product_id=product_id,
            min_price=min_price,
            alpha=alpha,
            beta=beta,
            gamma=gamma,
            campaign_start_time=campaign.start_time,
        )
    except ValueError as e:
        if str(e) == "PRICE_TOO_LOW":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "PRICE_TOO_LOW", "message": f"Price must be at least {min_price}"},
            )
        raise

    # Send WebSocket notification (non-blocking)
    asyncio.create_task(
        send_bid_accepted(
            campaign_id=str(bid.campaign_id),
            user_id=str(current_user.user_id),
            bid_id=str(bid.bid_id),
            price=float(bid.price),
            score=float(bid.score),
            rank=rank,
            time_elapsed_ms=bid.time_elapsed_ms,
        )
    )

    return BidResponse(
        bid_id=bid.bid_id,
        campaign_id=bid.campaign_id,
        user_id=bid.user_id,
        price=bid.price,
        score=float(bid.score),
        rank=rank,
        time_elapsed_ms=bid.time_elapsed_ms,
        bid_number=bid.bid_number,
        created_at=bid.created_at,
    )


@router.get("/{campaign_id}/history", response_model=BidHistoryResponse)
async def get_bid_history(
    campaign_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get user's bid history for a campaign."""
    redis_client = await get_redis()
    redis_service = RedisService(redis_client)
    bid_service = BidService(db, redis_service)

    bids = await bid_service.get_user_bid_history(campaign_id, current_user.user_id)

    # Get current rank for each bid
    bid_responses = []
    for bid in bids:
        rank = await redis_service.get_user_rank(str(campaign_id), str(current_user.user_id))
        bid_responses.append(
            BidResponse(
                bid_id=bid.bid_id,
                campaign_id=bid.campaign_id,
                user_id=bid.user_id,
                price=bid.price,
                score=float(bid.score),
                rank=rank or 0,
                time_elapsed_ms=bid.time_elapsed_ms,
                bid_number=bid.bid_number,
                created_at=bid.created_at,
            )
        )

    return BidHistoryResponse(bids=bid_responses, total=len(bid_responses))
