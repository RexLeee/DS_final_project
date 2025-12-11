"""Bidding API endpoints."""

import asyncio
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, BidServiceDep, RedisServiceDep
from app.schemas.bid import BidCreate, BidHistoryResponse, BidResponse
from app.services.ws_manager import send_bid_accepted

router = APIRouter()


@router.post("", response_model=BidResponse, status_code=status.HTTP_201_CREATED)
async def submit_bid(
    bid_data: BidCreate,
    current_user: CurrentUser,
    bid_service: BidServiceDep,
):
    """Submit or update a bid for a campaign.

    P1 Optimization: Uses dependency injection for BidService instead of
    creating new instances per request, reducing GC pressure.
    """

    # Validate campaign (uses Redis cache first, returns cached dict or Campaign object)
    campaign_data, error_code = await bid_service.get_campaign_with_validation(bid_data.campaign_id)

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

    # P0 Optimization: campaign_data is now always a dict with pre-converted types
    # (float for alpha/beta/gamma/min_price, UUID for product_id, datetime for start_time)
    # This eliminates 6+ type conversions per request
    alpha = campaign_data["alpha"]  # Already float
    beta = campaign_data["beta"]
    gamma = campaign_data["gamma"]
    min_price = campaign_data["min_price"]
    product_id = campaign_data["product_id"]
    campaign_start_time = campaign_data["start_time"]

    # Validate price (convert bid_data.price to float for comparison)
    bid_price = float(bid_data.price)
    if bid_price < min_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PRICE_TOO_LOW", "message": f"Price must be at least {min_price}"},
        )

    # Create or update bid (all params are now float)
    try:
        bid, rank = await bid_service.create_or_update_bid(
            campaign_id=bid_data.campaign_id,
            user=current_user,
            price=bid_price,
            product_id=product_id,
            min_price=min_price,
            alpha=alpha,
            beta=beta,
            gamma=gamma,
            campaign_start_time=campaign_start_time,
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
    current_user: CurrentUser,
    bid_service: BidServiceDep,
    redis_service: RedisServiceDep,
):
    """Get user's bid history for a campaign.

    P1 Optimization: Uses dependency injection for services.
    """

    bids = await bid_service.get_user_bid_history(campaign_id, current_user.user_id)

    # P1 Optimization: Query rank once outside loop (same user + same campaign = same rank)
    # Before: N Redis queries in loop (N = number of bid history entries)
    # After: 1 Redis query + reuse in loop
    rank = await redis_service.get_user_rank(str(campaign_id), str(current_user.user_id))
    current_rank = rank or 0

    bid_responses = []
    for bid in bids:
        bid_responses.append(
            BidResponse(
                bid_id=bid.bid_id,
                campaign_id=bid.campaign_id,
                user_id=bid.user_id,
                price=bid.price,
                score=float(bid.score),
                rank=current_rank,
                time_elapsed_ms=bid.time_elapsed_ms,
                bid_number=bid.bid_number,
                created_at=bid.created_at,
            )
        )

    return BidHistoryResponse(bids=bid_responses, total=len(bid_responses))
