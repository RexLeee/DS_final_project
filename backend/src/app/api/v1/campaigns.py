"""Campaign management API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import AdminUser, DbSession
from app.core.redis import get_redis
from app.schemas.campaign import (
    CampaignCreate,
    CampaignDetailResponse,
    CampaignListResponse,
    CampaignResponse,
    CampaignWithProductResponse,
)
from app.services.campaign_service import CampaignService
from app.services.product_service import ProductService
from app.services.redis_service import RedisService

router = APIRouter()


@router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    db: DbSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    """Get all campaigns with pagination."""
    service = CampaignService(db)
    campaigns, total = await service.get_all(skip=skip, limit=limit)

    # Update status based on current time
    campaign_responses = []
    for campaign in campaigns:
        response = CampaignWithProductResponse(
            campaign_id=campaign.campaign_id,
            product_id=campaign.product_id,
            product=campaign.product,
            start_time=campaign.start_time,
            end_time=campaign.end_time,
            alpha=campaign.alpha,
            beta=campaign.beta,
            gamma=campaign.gamma,
            quota=campaign.quota,
            status=service._get_campaign_status(campaign),
            created_at=campaign.created_at,
        )
        campaign_responses.append(response)

    return CampaignListResponse(campaigns=campaign_responses, total=total)


@router.get("/{campaign_id}", response_model=CampaignDetailResponse)
async def get_campaign(
    campaign_id: UUID,
    db: DbSession,
):
    """Get campaign by ID with product and stats."""
    redis_client = await get_redis()
    redis_service = RedisService(redis_client)
    service = CampaignService(db, redis_service)

    campaign = await service.get_by_id(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )

    # Get stats from Redis (use quota for winner determination)
    stats = await service.get_stats(campaign_id, campaign.quota)

    return CampaignDetailResponse(
        campaign_id=campaign.campaign_id,
        product=campaign.product,
        start_time=campaign.start_time,
        end_time=campaign.end_time,
        alpha=campaign.alpha,
        beta=campaign.beta,
        gamma=campaign.gamma,
        quota=campaign.quota,
        status=service._get_campaign_status(campaign),
        stats=stats,
        created_at=campaign.created_at,
    )


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    campaign_data: CampaignCreate,
    db: DbSession,
    admin: AdminUser,
):
    """Create a new campaign (admin only)."""
    # Verify product exists
    product_service = ProductService(db)
    product = await product_service.get_by_id(campaign_data.product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product not found",
        )

    # Validate times
    if campaign_data.end_time <= campaign_data.start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_time must be after start_time",
        )

    redis_client = await get_redis()
    redis_service = RedisService(redis_client)
    service = CampaignService(db, redis_service)

    campaign = await service.create(campaign_data, product)

    return CampaignResponse(
        campaign_id=campaign.campaign_id,
        product_id=campaign.product_id,
        start_time=campaign.start_time,
        end_time=campaign.end_time,
        alpha=campaign.alpha,
        beta=campaign.beta,
        gamma=campaign.gamma,
        quota=campaign.quota,
        status=service._get_campaign_status(campaign),
        created_at=campaign.created_at,
    )
