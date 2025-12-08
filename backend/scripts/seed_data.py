"""Seed data script for development and testing.

Creates:
- 1 admin + 1000 test users with random weights (0.5-5.0)
- 5 test products with varying stock
- 1 active campaign with configurable duration

Environment Variables:
    CAMPAIGN_DURATION_MINUTES: Campaign duration in minutes (default: 10)

Usage:
    uv run python -m scripts.seed_data
    CAMPAIGN_DURATION_MINUTES=15 uv run python -m scripts.seed_data
"""

import asyncio
import os
import random
from datetime import datetime, timedelta
from decimal import Decimal

# Campaign duration from environment variable (default: 10 minutes)
CAMPAIGN_DURATION_MINUTES = int(os.getenv("CAMPAIGN_DURATION_MINUTES", "10"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker, engine
from app.core.redis import get_redis
from app.core.security import get_password_hash
from app.models import Campaign, Product, User
from app.services.redis_service import RedisService


async def seed_users(session: AsyncSession) -> list[User]:
    """Create 1 admin + 1000 test users with random weights.

    Users:
    - Admin: admin@test.com / admin123 (is_admin=True)
    - Email: user0001@test.com to user1000@test.com
    - Password: password123 (bcrypt hashed)
    - Weight: Random between 0.5 and 5.0
    """
    print("Seeding users...")

    # Check if users already exist
    result = await session.execute(select(User).limit(1))
    if result.scalar_one_or_none():
        print("  Users already exist, skipping...")
        result = await session.execute(select(User))
        return list(result.scalars().all())

    users = []

    # Create admin user
    admin = User(
        email="admin@test.com",
        password_hash=get_password_hash("admin123"),
        username="admin",
        weight=Decimal("1.0"),
        status="active",
        is_admin=True,
    )
    users.append(admin)
    print("  Created admin: admin@test.com / admin123")

    # Create 1000 test users for load testing (1000 VU requirement)
    password_hash = get_password_hash("password123")

    for i in range(1, 1001):
        weight = round(random.uniform(0.5, 5.0), 2)
        user = User(
            email=f"user{i:04d}@test.com",
            password_hash=password_hash,
            username=f"user{i:04d}",
            weight=Decimal(str(weight)),
            status="active",
        )
        users.append(user)

    session.add_all(users)
    await session.commit()

    # Refresh to get IDs
    for user in users:
        await session.refresh(user)

    print(f"  Created {len(users)} users")
    return users


async def seed_products(session: AsyncSession) -> list[Product]:
    """Create 5 test products with varying stock and prices."""
    print("Seeding products...")

    # Check if products already exist
    result = await session.execute(select(Product).limit(1))
    if result.scalar_one_or_none():
        print("  Products already exist, skipping...")
        result = await session.execute(select(Product))
        return list(result.scalars().all())

    products_data = [
        {
            "name": "限量球鞋 Air Max 2025",
            "description": "2025年度限量發售運動鞋，全球限量100雙",
            "image_url": "https://example.com/images/airmax2025.jpg",
            "stock": 10,
            "min_price": Decimal("1000.00"),
            "status": "active",
        },
        {
            "name": "經典復刻手錶",
            "description": "經典設計復刻版，限量發售50只",
            "image_url": "https://example.com/images/watch.jpg",
            "stock": 20,
            "min_price": Decimal("2000.00"),
            "status": "active",
        },
        {
            "name": "限量版公仔",
            "description": "知名設計師聯名款，全球限量200個",
            "image_url": "https://example.com/images/figure.jpg",
            "stock": 30,
            "min_price": Decimal("500.00"),
            "status": "active",
        },
        {
            "name": "高級耳機 Pro Max",
            "description": "旗艦級降噪耳機，限量版配色",
            "image_url": "https://example.com/images/headphones.jpg",
            "stock": 15,
            "min_price": Decimal("800.00"),
            "status": "active",
        },
        {
            "name": "藝術畫作 NFT 實體版",
            "description": "知名藝術家授權實體印刷版",
            "image_url": "https://example.com/images/art.jpg",
            "stock": 50,
            "min_price": Decimal("300.00"),
            "status": "active",
        },
    ]

    products = []
    for data in products_data:
        product = Product(**data)
        products.append(product)

    session.add_all(products)
    await session.commit()

    # Refresh to get IDs
    for product in products:
        await session.refresh(product)

    print(f"  Created {len(products)} products")
    return products


async def seed_campaign(session: AsyncSession, product: Product) -> Campaign:
    """Create 1 active campaign with the first product.

    Campaign settings:
    - Duration: CAMPAIGN_DURATION_MINUTES (default 10) from now
    - Stock (K): 10 (from product)
    - alpha: 1.0, beta: 1000.0, gamma: 100.0
    """
    print("Seeding campaign...")

    # Check if campaign already exists
    result = await session.execute(select(Campaign).limit(1))
    if result.scalar_one_or_none():
        print("  Campaign already exists, skipping...")
        result = await session.execute(select(Campaign).limit(1))
        return result.scalar_one()

    now = datetime.utcnow()
    campaign = Campaign(
        product_id=product.product_id,
        start_time=now,
        end_time=now + timedelta(minutes=CAMPAIGN_DURATION_MINUTES),
        alpha=Decimal("1.0000"),
        beta=Decimal("1000.0000"),
        gamma=Decimal("100.0000"),
        status="active",
    )

    session.add(campaign)
    await session.commit()
    await session.refresh(campaign)

    print(f"  Created campaign: {campaign.campaign_id}")
    print(f"    Product: {product.name}")
    print(f"    Duration: {CAMPAIGN_DURATION_MINUTES} minutes")
    print(f"    Start: {campaign.start_time}")
    print(f"    End: {campaign.end_time}")
    print(f"    Parameters: alpha={campaign.alpha}, beta={campaign.beta}, gamma={campaign.gamma}")

    return campaign


async def init_redis_stock(redis_service: RedisService, products: list[Product]) -> None:
    """Initialize Redis stock counters for all products."""
    print("Initializing Redis stock counters...")

    for product in products:
        await redis_service.init_stock(str(product.product_id), product.stock)
        print(f"  {product.name}: stock={product.stock}")


async def cache_campaign_data(
    redis_service: RedisService, campaign: Campaign, product: Product
) -> None:
    """Cache campaign parameters in Redis."""
    print("Caching campaign parameters...")

    # Calculate TTL: campaign duration + 1 hour buffer
    now = datetime.utcnow()
    duration = (campaign.end_time - now).total_seconds()
    ttl = int(duration + 3600)  # Add 1 hour buffer

    campaign_data = {
        "product_id": str(campaign.product_id),
        "start_time": campaign.start_time.isoformat(),
        "end_time": campaign.end_time.isoformat(),
        "alpha": str(campaign.alpha),
        "beta": str(campaign.beta),
        "gamma": str(campaign.gamma),
        "status": campaign.status,
        "min_price": str(product.min_price),
        "stock": str(product.stock),
    }

    await redis_service.cache_campaign(str(campaign.campaign_id), campaign_data, ttl)
    print(f"  Cached campaign {campaign.campaign_id} with TTL={ttl}s")


async def main():
    """Main seed function."""
    print("=" * 60)
    print("Flash Sale System - Seed Data Script")
    print("=" * 60)

    # Initialize database session
    async with async_session_maker() as session:
        # Seed data in order
        users = await seed_users(session)
        products = await seed_products(session)

        # Create campaign with first product (stock=10)
        campaign = await seed_campaign(session, products[0])

    # Initialize Redis
    redis = await get_redis()
    redis_service = RedisService(redis)

    # Initialize stock counters
    await init_redis_stock(redis_service, products)

    # Cache campaign data
    async with async_session_maker() as session:
        result = await session.execute(
            select(Campaign, Product)
            .join(Product, Campaign.product_id == Product.product_id)
            .limit(1)
        )
        row = result.first()
        if row:
            campaign, product = row
            await cache_campaign_data(redis_service, campaign, product)

    print("=" * 60)
    print("Seed data complete!")
    print(f"  Users: {len(users)}")
    print(f"  Products: {len(products)}")
    print(f"  Active Campaign: {campaign.campaign_id}")
    print("=" * 60)

    # Cleanup
    await redis.aclose()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
