"""Product service for CRUD operations."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.schemas.product import ProductCreate
from app.services.redis_service import RedisService


class ProductService:
    """Service class for product operations."""

    def __init__(self, db: AsyncSession, redis_service: RedisService | None = None):
        self.db = db
        self.redis_service = redis_service

    async def get_all(self, skip: int = 0, limit: int = 100) -> tuple[list[Product], int]:
        """Get all products with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (products list, total count)
        """
        # Get total count
        count_result = await self.db.execute(select(func.count(Product.product_id)))
        total = count_result.scalar_one()

        # Get products
        result = await self.db.execute(
            select(Product)
            .where(Product.status == "active")
            .order_by(Product.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        products = list(result.scalars().all())

        return products, total

    async def get_by_id(self, product_id: UUID) -> Product | None:
        """Get product by ID.

        Args:
            product_id: Product UUID

        Returns:
            Product or None if not found
        """
        result = await self.db.execute(
            select(Product).where(Product.product_id == product_id)
        )
        return result.scalar_one_or_none()

    async def create(self, product_data: ProductCreate) -> Product:
        """Create a new product.

        Args:
            product_data: Product creation data

        Returns:
            Created product
        """
        product = Product(
            name=product_data.name,
            description=product_data.description,
            image_url=product_data.image_url,
            stock=product_data.stock,
            min_price=product_data.min_price,
            status="active",
            version=0,
        )

        self.db.add(product)
        await self.db.commit()
        await self.db.refresh(product)

        # Initialize Redis stock counter
        if self.redis_service:
            await self.redis_service.init_stock(str(product.product_id), product.stock)

        return product
