"""Ranking query API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.core.redis import get_redis
from app.models.campaign import Campaign
from app.schemas.ranking import MyRankResponse, RankingItem, RankingResponse
from app.services.ranking_service import RankingService
from app.services.redis_service import RedisService
from sqlalchemy import select

router = APIRouter()


@router.get("/{campaign_id}", response_model=RankingResponse)
async def get_rankings(
    campaign_id: UUID,
    db: DbSession,
):
    """Get top K rankings for a campaign."""
    # Get campaign with product to know K (stock)
    result = await db.execute(
        select(Campaign)
        .options(selectinload(Campaign.product))
        .where(Campaign.campaign_id == campaign_id)
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    stock = campaign.product.stock

    redis_client = await get_redis()
    redis_service = RedisService(redis_client)
    ranking_service = RankingService(db, redis_service)

    # Get top K rankings
    rankings_data = await ranking_service.get_top_k_rankings(campaign_id, stock)

    # Get stats
    stats = await ranking_service.get_campaign_stats(campaign_id, stock)

    return RankingResponse(
        campaign_id=campaign_id,
        total_participants=stats["total_participants"],
        rankings=[RankingItem(**r) for r in rankings_data],
        min_winning_score=stats["min_winning_score"],
        max_score=stats["max_score"],
        updated_at=stats["updated_at"],
    )


@router.get("/{campaign_id}/me", response_model=MyRankResponse)
async def get_my_rank(
    campaign_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get current user's rank in a campaign."""
    # Get campaign with product to know K (stock)
    result = await db.execute(
        select(Campaign)
        .options(selectinload(Campaign.product))
        .where(Campaign.campaign_id == campaign_id)
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    stock = campaign.product.stock

    redis_client = await get_redis()
    redis_service = RedisService(redis_client)
    ranking_service = RankingService(db, redis_service)

    rank_info = await ranking_service.get_user_rank(
        campaign_id, current_user.user_id, stock
    )

    return MyRankResponse(**rank_info)
