"""Bid service for bidding operations."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bid import Bid
from app.models.campaign import Campaign
from app.models.user import User
from app.services.redis_service import RedisService


def calculate_score(
    price: Decimal,
    time_elapsed_ms: int,
    weight: Decimal,
    alpha: Decimal,
    beta: Decimal,
    gamma: Decimal,
) -> float:
    """Calculate bid score using formula: Score = α·P + β/(T+1) + γ·W

    Args:
        price: Bid price (P)
        time_elapsed_ms: Time elapsed since campaign start in milliseconds (T)
        weight: User's member weight (W)
        alpha: Price coefficient (α)
        beta: Time coefficient (β)
        gamma: Weight coefficient (γ)

    Returns:
        Calculated score
    """
    return float(
        alpha * price + beta / (time_elapsed_ms + 1) + gamma * weight
    )


class BidService:
    """Service class for bid operations."""

    def __init__(self, db: AsyncSession, redis_service: RedisService):
        self.db = db
        self.redis_service = redis_service

    async def get_campaign_with_validation(self, campaign_id: UUID) -> tuple[Campaign | None, str | None]:
        """Get campaign and validate it can be bid on.

        Args:
            campaign_id: Campaign UUID

        Returns:
            Tuple of (campaign, error_code) - error_code is None if valid
        """
        result = await self.db.execute(
            select(Campaign).where(Campaign.campaign_id == campaign_id)
        )
        campaign = result.scalar_one_or_none()

        if not campaign:
            return None, "CAMPAIGN_NOT_FOUND"

        # Check campaign status based on time
        now = datetime.now(timezone.utc)
        start = campaign.start_time.replace(tzinfo=timezone.utc) if campaign.start_time.tzinfo is None else campaign.start_time
        end = campaign.end_time.replace(tzinfo=timezone.utc) if campaign.end_time.tzinfo is None else campaign.end_time

        if now < start:
            return campaign, "CAMPAIGN_NOT_STARTED"
        if now >= end:
            return campaign, "CAMPAIGN_ENDED"

        return campaign, None

    async def create_or_update_bid(
        self,
        campaign_id: UUID,
        user: User,
        price: Decimal,
        product_id: UUID,
        min_price: Decimal,
        alpha: Decimal,
        beta: Decimal,
        gamma: Decimal,
        campaign_start_time: datetime,
    ) -> tuple[Bid, int]:
        """Create or update a bid.

        Args:
            campaign_id: Campaign UUID
            user: Current user
            price: Bid price
            product_id: Product UUID
            min_price: Minimum allowed price
            alpha, beta, gamma: Score calculation parameters
            campaign_start_time: Campaign start time for time_elapsed calculation

        Returns:
            Tuple of (bid, rank)

        Raises:
            ValueError: If price is below minimum
        """
        if price < min_price:
            raise ValueError("PRICE_TOO_LOW")

        # Calculate time elapsed
        now = datetime.now(timezone.utc)
        start = campaign_start_time.replace(tzinfo=timezone.utc) if campaign_start_time.tzinfo is None else campaign_start_time
        time_elapsed_ms = int((now - start).total_seconds() * 1000)

        # Calculate score
        score = calculate_score(
            price=price,
            time_elapsed_ms=time_elapsed_ms,
            weight=user.weight,
            alpha=alpha,
            beta=beta,
            gamma=gamma,
        )

        # Check for existing bid
        existing_bid_result = await self.db.execute(
            select(Bid).where(
                and_(
                    Bid.campaign_id == campaign_id,
                    Bid.user_id == user.user_id,
                )
            )
        )
        existing_bid = existing_bid_result.scalar_one_or_none()

        if existing_bid:
            # Update existing bid
            existing_bid.price = price
            existing_bid.score = Decimal(str(score))
            existing_bid.time_elapsed_ms = time_elapsed_ms
            existing_bid.bid_number += 1
            bid = existing_bid
        else:
            # Create new bid
            bid = Bid(
                campaign_id=campaign_id,
                user_id=user.user_id,
                product_id=product_id,
                price=price,
                score=Decimal(str(score)),
                time_elapsed_ms=time_elapsed_ms,
                bid_number=1,
            )
            self.db.add(bid)

        await self.db.commit()
        await self.db.refresh(bid)

        # Update Redis ranking with bid details
        await self.redis_service.update_ranking(
            str(campaign_id),
            str(user.user_id),
            score,
            price=float(price),
            username=user.username,
        )

        # Get user's current rank
        rank = await self.redis_service.get_user_rank(str(campaign_id), str(user.user_id))

        return bid, rank or 0

    async def get_user_bid_history(
        self, campaign_id: UUID, user_id: UUID
    ) -> list[Bid]:
        """Get user's bid history for a campaign.

        Note: Since we update in place, this returns the current bid.
        For full history, a separate bid_history table would be needed.

        Args:
            campaign_id: Campaign UUID
            user_id: User UUID

        Returns:
            List of bids (currently single bid per user per campaign)
        """
        result = await self.db.execute(
            select(Bid)
            .where(
                and_(
                    Bid.campaign_id == campaign_id,
                    Bid.user_id == user_id,
                )
            )
            .order_by(Bid.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_campaign_bids_count(self, campaign_id: UUID) -> int:
        """Get total number of bids in a campaign.

        Args:
            campaign_id: Campaign UUID

        Returns:
            Number of bids
        """
        result = await self.db.execute(
            select(func.count(Bid.bid_id)).where(Bid.campaign_id == campaign_id)
        )
        return result.scalar_one()
