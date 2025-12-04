"""Pytest configuration and fixtures for testing."""

import asyncio
from decimal import Decimal
from typing import Generator
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


# Event loop fixture for async tests
@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Mock Redis client fixture
@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis client."""
    redis = AsyncMock()

    # Mock common Redis operations
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.incr = AsyncMock(return_value=1)
    redis.decr = AsyncMock(return_value=0)
    redis.delete = AsyncMock(return_value=1)
    redis.zadd = AsyncMock(return_value=1)
    redis.zrevrange = AsyncMock(return_value=[])
    redis.zrevrank = AsyncMock(return_value=None)
    redis.zcard = AsyncMock(return_value=0)
    redis.hset = AsyncMock(return_value=1)
    redis.hgetall = AsyncMock(return_value={})
    redis.eval = AsyncMock(return_value=1)

    return redis


# Mock user fixture
@pytest.fixture
def mock_user() -> MagicMock:
    """Create a mock user object."""
    user = MagicMock()
    user.user_id = uuid4()
    user.email = "test@example.com"
    user.username = "testuser"
    user.weight = Decimal("2.5")
    user.is_admin = False
    return user


# Mock admin user fixture
@pytest.fixture
def mock_admin_user(mock_user: MagicMock) -> MagicMock:
    """Create a mock admin user object."""
    mock_user.is_admin = True
    return mock_user


# Mock campaign fixture
@pytest.fixture
def mock_campaign() -> MagicMock:
    """Create a mock campaign object."""
    from datetime import datetime, timedelta, timezone

    campaign = MagicMock()
    campaign.campaign_id = uuid4()
    campaign.product_id = uuid4()
    campaign.start_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    campaign.end_time = datetime.now(timezone.utc) + timedelta(minutes=5)
    campaign.alpha = Decimal("1.0")
    campaign.beta = Decimal("1000.0")
    campaign.gamma = Decimal("100.0")
    campaign.status = "active"
    return campaign


# Mock product fixture
@pytest.fixture
def mock_product() -> MagicMock:
    """Create a mock product object."""
    product = MagicMock()
    product.product_id = uuid4()
    product.name = "Test Product"
    product.stock = 10
    product.min_price = Decimal("1000.00")
    product.version = 1
    return product


# Default score calculation parameters
@pytest.fixture
def default_params() -> dict:
    """Return default score calculation parameters."""
    return {
        "alpha": Decimal("1.0"),
        "beta": Decimal("1000.0"),
        "gamma": Decimal("100.0"),
    }
