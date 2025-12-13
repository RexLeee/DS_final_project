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
            .options(selectinload(Campaign.product))
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

            # P5 Optimization: Try stats snapshot cache first (5s TTL)
            # This eliminates 3 Redis ZSET operations for frequently accessed stats
            cached_stats = await self.redis_service.get_cached_campaign_stats_snapshot(campaign_id_str)
            if cached_stats:
                stats.total_participants = cached_stats.get("total_participants", 0)
                stats.min_winning_score = cached_stats.get("min_winning_score")
                # Still get fresh max_price since it changes frequently
                max_price = await self.redis_service.get_max_price(campaign_id_str)
                if max_price is not None:
                    stats.max_price = max_price
                return stats

            # P1 Optimization: Use batch method for all Redis stats (3 RTT → 1 RTT)
            # Before: 3 separate Redis calls (get_total_participants, get_max_score, get_min_winning_score)
            # After: 1 pipeline call with all 3 queries
            batch_stats = await self.redis_service.get_campaign_stats_batch(campaign_id_str, stock)

            stats.total_participants = batch_stats["total_participants"]

            if stats.total_participants > 0:
                max_score = batch_stats["max_score"]
                if max_score is not None:
                    stats.min_winning_score = max_score  # Default to max if less than K participants

                # Use min_winning_score if we have enough participants
                if stats.total_participants >= stock:
                    min_winning = batch_stats["min_winning_score"]
                    if min_winning is not None:
                        stats.min_winning_score = min_winning

            # P5 Optimization: Cache stats snapshot for 5 seconds
            import asyncio
            asyncio.create_task(
                self.redis_service.cache_campaign_stats_snapshot(
                    campaign_id_str,
                    {
                        "total_participants": stats.total_participants,
                        "min_winning_score": stats.min_winning_score,
                    }
                )
            )

            # P1 Optimization: Get max_price from Redis cache if available
            max_price = await self.redis_service.get_max_price(campaign_id_str)
            if max_price is not None:
                stats.max_price = max_price
                return stats

        # Fallback: Get max price from database if not in Redis
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
            quota=product.stock,  # 快照庫存作為得標名額
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
