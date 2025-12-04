"""Settlement service for campaign settlement operations."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bid import Bid
from app.models.campaign import Campaign
from app.models.order import Order
from app.services.redis_service import RedisService


class SettlementService:
    """Service class for campaign settlement operations."""

    def __init__(self, db: AsyncSession, redis_service: RedisService):
        self.db = db
        self.redis_service = redis_service

    async def check_campaign_needs_settlement(self, campaign_id: UUID) -> bool:
        """Check if a campaign needs settlement.

        Args:
            campaign_id: Campaign UUID

        Returns:
            True if campaign has ended and needs settlement
        """
        result = await self.db.execute(
            select(Campaign).where(Campaign.campaign_id == campaign_id)
        )
        campaign = result.scalar_one_or_none()

        if not campaign:
            return False

        now = datetime.now(timezone.utc)
        end = campaign.end_time.replace(tzinfo=timezone.utc) if campaign.end_time.tzinfo is None else campaign.end_time

        # Campaign has ended and status is not yet "ended"
        return now >= end and campaign.status != "ended"

    async def settle_campaign(self, campaign_id: UUID) -> list[Order]:
        """Settle a campaign by creating orders for top K winners.

        Args:
            campaign_id: Campaign UUID

        Returns:
            List of created orders
        """
        # Get campaign with product
        result = await self.db.execute(
            select(Campaign).where(Campaign.campaign_id == campaign_id)
        )
        campaign = result.scalar_one_or_none()

        if not campaign:
            raise ValueError("Campaign not found")

        # Check if already settled
        if campaign.status == "ended":
            return []

        # Get product stock (K)
        from sqlalchemy.orm import selectinload
        result = await self.db.execute(
            select(Campaign)
            .options(selectinload(Campaign.product))
            .where(Campaign.campaign_id == campaign_id)
        )
        campaign = result.scalar_one()
        stock = campaign.product.stock
        product_id = campaign.product_id

        # Get top K from Redis
        campaign_id_str = str(campaign_id)
        top_k = await self.redis_service.get_top_k(campaign_id_str, stock)

        orders = []

        for ranking in top_k:
            user_id = UUID(ranking["user_id"])
            rank = ranking["rank"]
            score = ranking["score"]

            # Acquire distributed lock for stock
            acquired, owner_id = await self.redis_service.acquire_lock(
                str(product_id), ttl=5
            )

            if not acquired:
                continue  # Skip if can't acquire lock

            try:
                # Decrement stock atomically
                new_stock = await self.redis_service.decrement_stock(str(product_id))

                if new_stock < 0:
                    # Insufficient stock, rollback
                    await self.redis_service.increment_stock(str(product_id))
                    continue

                # Get bid to get the final price
                bid_result = await self.db.execute(
                    select(Bid).where(
                        and_(
                            Bid.campaign_id == campaign_id,
                            Bid.user_id == user_id,
                        )
                    )
                )
                bid = bid_result.scalar_one_or_none()

                if not bid:
                    # No bid found, rollback stock
                    await self.redis_service.increment_stock(str(product_id))
                    continue

                # Create order
                order = Order(
                    campaign_id=campaign_id,
                    user_id=user_id,
                    product_id=product_id,
                    final_price=bid.price,
                    final_score=Decimal(str(score)),
                    final_rank=rank,
                    status="confirmed",
                )
                self.db.add(order)
                orders.append(order)

            finally:
                # Release lock
                await self.redis_service.release_lock(str(product_id), owner_id)

        # Update campaign status to ended
        await self.db.execute(
            update(Campaign)
            .where(Campaign.campaign_id == campaign_id)
            .values(status="ended")
        )

        await self.db.commit()

        # Refresh orders to get created_at
        for order in orders:
            await self.db.refresh(order)

        return orders

    async def get_campaigns_to_settle(self) -> list[Campaign]:
        """Get list of campaigns that need settlement.

        Returns:
            List of campaigns that have ended but not settled
        """
        now = datetime.now(timezone.utc)

        result = await self.db.execute(
            select(Campaign).where(
                and_(
                    Campaign.status != "ended",
                    Campaign.end_time < now,
                )
            )
        )
        return list(result.scalars().all())
