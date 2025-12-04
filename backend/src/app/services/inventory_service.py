"""Inventory service implementing four-layer anti-overselling protection.

Follows technical_spec.md Section 5.1 Four-Layer Protection Mechanism:
- Layer 1: Redis Distributed Lock (SET NX EX)
- Layer 2: Redis Atomic Decrement (Lua script)
- Layer 3: PostgreSQL Row-Level Lock (SELECT FOR UPDATE)
- Layer 4: Optimistic Locking (version check)
"""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.services.redis_service import RedisService


class InsufficientStockError(Exception):
    """Raised when stock is insufficient."""

    pass


class ConcurrencyError(Exception):
    """Raised when optimistic lock conflict occurs."""

    pass


class InventoryService:
    """Four-layer protection: Redis Lock -> Redis Decrement -> PG Lock -> Optimistic Lock."""

    def __init__(self, db: AsyncSession, redis_service: RedisService):
        """Initialize inventory service.

        Args:
            db: SQLAlchemy async session
            redis_service: Redis service instance
        """
        self.db = db
        self.redis_service = redis_service

    async def decrement_stock_with_protection(
        self, product_id: UUID, owner_id: str | None = None
    ) -> tuple[bool, str]:
        """Decrement stock with four-layer protection.

        Flow:
        1. Acquire distributed lock (Layer 1)
        2. Redis atomic decrement (Layer 2)
        3. PostgreSQL SELECT FOR UPDATE (Layer 3)
        4. Optimistic lock version check (Layer 4)

        Args:
            product_id: Product UUID
            owner_id: Optional lock owner ID (auto-generated if None)

        Returns:
            Tuple of (success, owner_id) - owner_id needed for lock release
        """
        product_id_str = str(product_id)

        # Layer 1: Acquire distributed lock
        acquired, owner_id = await self.redis_service.acquire_lock(
            product_id_str, owner_id=owner_id, ttl=2
        )
        if not acquired:
            return (False, owner_id)

        try:
            # Layer 2: Redis atomic decrement
            new_stock = await self.redis_service.decrement_stock(product_id_str)
            if new_stock < 0:
                # Stock insufficient in Redis, Lua script didn't decrement
                # No rollback needed
                return (False, owner_id)

            try:
                # Layer 3 & 4: PostgreSQL with row lock + optimistic locking
                await self._db_decrement_with_lock(product_id)
                return (True, owner_id)

            except (InsufficientStockError, ConcurrencyError):
                # Rollback Redis stock
                await self.redis_service.increment_stock(product_id_str)
                return (False, owner_id)

        except Exception:
            # Rollback Redis on any unexpected error
            await self.redis_service.increment_stock(product_id_str)
            raise

        # Note: Lock is released by caller after order creation

    async def _db_decrement_with_lock(self, product_id: UUID) -> Product:
        """Decrement stock in DB with row-level lock and optimistic locking.

        Layer 3: SELECT ... FOR UPDATE
        Layer 4: UPDATE with version check

        Args:
            product_id: Product UUID

        Returns:
            Updated product

        Raises:
            ValueError: Product not found
            InsufficientStockError: Stock < 1
            ConcurrencyError: Version conflict
        """
        # Layer 3: SELECT FOR UPDATE (row-level lock)
        result = await self.db.execute(
            select(Product).where(Product.product_id == product_id).with_for_update()
        )
        product = result.scalar_one_or_none()

        if not product:
            raise ValueError(f"Product {product_id} not found")

        if product.stock < 1:
            raise InsufficientStockError(f"Product {product_id} has no stock")

        current_version = product.version

        # Layer 4: Optimistic lock update
        result = await self.db.execute(
            update(Product)
            .where(Product.product_id == product_id)
            .where(Product.version == current_version)
            .where(Product.stock >= 1)
            .values(stock=Product.stock - 1, version=Product.version + 1)
            .returning(Product.stock, Product.version)
        )

        updated = result.first()
        if updated is None:
            raise ConcurrencyError(f"Concurrent update conflict for product {product_id}")

        return product

    async def release_lock(self, product_id: UUID, owner_id: str) -> bool:
        """Release the distributed lock.

        Args:
            product_id: Product UUID
            owner_id: Lock owner ID from decrement_stock_with_protection

        Returns:
            True if lock released, False if not owner
        """
        return await self.redis_service.release_lock(str(product_id), owner_id)

    async def rollback_stock(self, product_id: UUID) -> None:
        """Rollback Redis stock (increment).

        Used when order creation fails after successful stock decrement.

        Args:
            product_id: Product UUID
        """
        await self.redis_service.increment_stock(str(product_id))
