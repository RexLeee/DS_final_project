"""Campaign service for CRUD operations."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.bid import Bid
from app.models.campaign import Campaign
from app.models.product import Product
from app.schemas.campaign import CampaignCreate, CampaignStats
from app.services.redis_service import RedisService


class CampaignService:
    """Service class for campaign operations."""

    def __init__(self, db: AsyncSession, redis_service: RedisService | None = None):
        self.db = db
        self.redis_service = redis_service

    def _get_campaign_status(self, campaign: Campaign) -> str:
        """Determine campaign status based on current time."""
        now = datetime.now(timezone.utc)
        start = campaign.start_time.replace(tzinfo=timezone.utc) if campaign.start_time.tzinfo is None else campaign.start_time
        end = campaign.end_time.replace(tzinfo=timezone.utc) if campaign.end_time.tzinfo is None else campaign.end_time

        if now < start:
            return "pending"
        elif now >= end:
            return "ended"
        else:
            return "active"

    async def get_all(self, skip: int = 0, limit: int = 100) -> tuple[list[Campaign], int]:
        """Get all campaigns with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (campaigns list, total count)
        """
        count_result = await self.db.execute(select(func.count(Campaign.campaign_id)))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Campaign)
            .order_by(Campaign.start_time.desc())
            .offset(skip)
            .limit(limit)
        )
        campaigns = list(result.scalars().all())

        return campaigns, total

    async def get_by_id(self, campaign_id: UUID) -> Campaign | None:
        """Get campaign by ID with product loaded.

        Args:
            campaign_id: Campaign UUID

        Returns:
            Campaign or None if not found
        """
        result = await self.db.execute(
            select(Campaign)
            .options(selectinload(Campaign.product))
            .where(Campaign.campaign_id == campaign_id)
        )
        return result.scalar_one_or_none()

    async def get_stats(self, campaign_id: UUID, stock: int) -> CampaignStats:
        """Get campaign statistics from Redis and database.

        Args:
            campaign_id: Campaign UUID
            stock: Product stock for min_winning_score calculation

        Returns:
            Campaign statistics
        """
        stats = CampaignStats()

        if self.redis_service:
            campaign_id_str = str(campaign_id)
            stats.total_participants = await self.redis_service.get_total_participants(campaign_id_str)

            if stats.total_participants > 0:
                # Get max score
                max_score = await self.redis_service.get_max_score(campaign_id_str)
                if max_score is not None:
                    stats.min_winning_score = max_score  # Will be updated below if applicable

                # Get min winning score (score at position K)
                if stats.total_participants >= stock:
                    min_winning = await self.redis_service.get_min_winning_score(campaign_id_str, stock)
                    if min_winning is not None:
                        stats.min_winning_score = min_winning

        # Get max price from database
        max_price_result = await self.db.execute(
            select(func.max(Bid.price))
            .where(Bid.campaign_id == campaign_id)
        )
        max_price = max_price_result.scalar_one_or_none()
        if max_price is not None:
            stats.max_price = max_price

        return stats

    async def create(self, campaign_data: CampaignCreate, product: Product) -> Campaign:
        """Create a new campaign.

        Args:
            campaign_data: Campaign creation data
            product: Product to associate with campaign

        Returns:
            Created campaign
        """
        # Convert timezone-aware to naive datetime (database uses TIMESTAMP WITHOUT TIME ZONE)
        start_time = campaign_data.start_time
        end_time = campaign_data.end_time
        if start_time.tzinfo is not None:
            start_time = start_time.replace(tzinfo=None)
        if end_time.tzinfo is not None:
            end_time = end_time.replace(tzinfo=None)

        campaign = Campaign(
            product_id=campaign_data.product_id,
            start_time=start_time,
            end_time=end_time,
            alpha=campaign_data.alpha,
            beta=campaign_data.beta,
            gamma=campaign_data.gamma,
            status="pending",
        )

        self.db.add(campaign)
        await self.db.commit()
        await self.db.refresh(campaign)

        # Cache campaign params in Redis
        if self.redis_service:
            cache_data = {
                "product_id": str(campaign_data.product_id),
                "start_time": campaign_data.start_time.isoformat(),
                "end_time": campaign_data.end_time.isoformat(),
                "alpha": str(campaign_data.alpha),
                "beta": str(campaign_data.beta),
                "gamma": str(campaign_data.gamma),
                "min_price": str(product.min_price),
                "stock": str(product.stock),
            }
            await self.redis_service.cache_campaign(str(campaign.campaign_id), cache_data)

        return campaign
