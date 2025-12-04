"""Ranking service for ranking query operations."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bid import Bid
from app.models.user import User
from app.services.redis_service import RedisService


class RankingService:
    """Service class for ranking operations."""

    def __init__(self, db: AsyncSession, redis_service: RedisService):
        self.db = db
        self.redis_service = redis_service

    async def get_top_k_rankings(
        self, campaign_id: UUID, k: int
    ) -> list[dict]:
        """Get top K rankings for a campaign with user details.

        Args:
            campaign_id: Campaign UUID
            k: Number of top rankings to return

        Returns:
            List of ranking dicts with user details
        """
        campaign_id_str = str(campaign_id)

        # Get top K from Redis
        redis_rankings = await self.redis_service.get_top_k(campaign_id_str, k)

        if not redis_rankings:
            return []

        # Get user IDs
        user_ids = [UUID(r["user_id"]) for r in redis_rankings]

        # Batch query user info and bids
        users_result = await self.db.execute(
            select(User).where(User.user_id.in_(user_ids))
        )
        users = {str(u.user_id): u for u in users_result.scalars().all()}

        bids_result = await self.db.execute(
            select(Bid).where(
                Bid.campaign_id == campaign_id,
                Bid.user_id.in_(user_ids),
            )
        )
        bids = {str(b.user_id): b for b in bids_result.scalars().all()}

        # Build ranking list
        rankings = []
        for r in redis_rankings:
            user_id = r["user_id"]
            user = users.get(user_id)
            bid = bids.get(user_id)

            if user and bid:
                rankings.append({
                    "rank": r["rank"],
                    "user_id": UUID(user_id),
                    "username": user.username,
                    "score": r["score"],
                    "price": bid.price,
                })

        return rankings

    async def get_campaign_stats(
        self, campaign_id: UUID, stock: int
    ) -> dict:
        """Get campaign ranking statistics.

        Args:
            campaign_id: Campaign UUID
            stock: Product stock (K for top K)

        Returns:
            Dict with total_participants, max_score, min_winning_score
        """
        campaign_id_str = str(campaign_id)

        total = await self.redis_service.get_total_participants(campaign_id_str)
        max_score = await self.redis_service.get_max_score(campaign_id_str)
        min_winning_score = None

        if total >= stock:
            min_winning_score = await self.redis_service.get_min_winning_score(
                campaign_id_str, stock
            )

        return {
            "total_participants": total,
            "max_score": max_score,
            "min_winning_score": min_winning_score,
            "updated_at": datetime.now(timezone.utc),
        }

    async def get_user_rank(
        self, campaign_id: UUID, user_id: UUID, stock: int
    ) -> dict:
        """Get a specific user's rank in a campaign.

        Args:
            campaign_id: Campaign UUID
            user_id: User UUID
            stock: Product stock (K for determining if winning)

        Returns:
            Dict with user's rank info
        """
        campaign_id_str = str(campaign_id)
        user_id_str = str(user_id)

        rank = await self.redis_service.get_user_rank(campaign_id_str, user_id_str)
        score = await self.redis_service.get_user_score(campaign_id_str, user_id_str)
        total = await self.redis_service.get_total_participants(campaign_id_str)

        is_winning = rank is not None and rank <= stock

        return {
            "campaign_id": campaign_id,
            "user_id": user_id,
            "rank": rank,
            "score": score,
            "is_winning": is_winning,
            "total_participants": total,
        }
