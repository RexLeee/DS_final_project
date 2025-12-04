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
