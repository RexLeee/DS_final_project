"""Order service for order query operations."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order


class OrderService:
    """Service class for order operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_orders(
        self, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> tuple[list[Order], int]:
        """Get orders for a specific user.

        Args:
            user_id: User UUID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (orders list, total count)
        """
        # Get total count
        count_result = await self.db.execute(
            select(func.count(Order.order_id)).where(Order.user_id == user_id)
        )
        total = count_result.scalar_one()

        # Get orders
        result = await self.db.execute(
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        orders = list(result.scalars().all())

        return orders, total

    async def get_order_by_id(self, order_id: UUID) -> Order | None:
        """Get order by ID.

        Args:
            order_id: Order UUID

        Returns:
            Order or None if not found
        """
        result = await self.db.execute(
            select(Order).where(Order.order_id == order_id)
        )
        return result.scalar_one_or_none()

    async def get_campaign_orders(
        self, campaign_id: UUID, skip: int = 0, limit: int = 100
    ) -> tuple[list[Order], int]:
        """Get orders for a specific campaign.

        Used for consistency verification (PDF requirement: 證明沒有超賣).

        Args:
            campaign_id: Campaign UUID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (orders list, total count)
        """
        # Get total count
        count_result = await self.db.execute(
            select(func.count(Order.order_id)).where(Order.campaign_id == campaign_id)
        )
        total = count_result.scalar_one()

        # Get orders sorted by final_rank
        result = await self.db.execute(
            select(Order)
            .where(Order.campaign_id == campaign_id)
            .order_by(Order.final_rank.asc())
            .offset(skip)
            .limit(limit)
        )
        orders = list(result.scalars().all())

        return orders, total

    async def get_campaign_order_count(self, campaign_id: UUID) -> int:
        """Get order count for a specific campaign.

        Used for quick consistency verification.

        Args:
            campaign_id: Campaign UUID

        Returns:
            Total order count for the campaign
        """
        count_result = await self.db.execute(
            select(func.count(Order.order_id)).where(Order.campaign_id == campaign_id)
        )
        return count_result.scalar_one()
