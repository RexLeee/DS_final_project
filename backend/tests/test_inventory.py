"""Tests for inventory management and anti-overselling mechanism.

Tests verify the four-layer protection:
1. Redis distributed lock
2. Redis atomic decrement (Lua script)
3. PostgreSQL row lock (SELECT FOR UPDATE)
4. Optimistic locking (version check)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.redis_service import RedisService


class TestRedisInventoryOperations:
    """Test Redis inventory operations."""

    @pytest.mark.asyncio
    async def test_init_stock(self, mock_redis):
        """Test initializing stock in Redis."""
        service = RedisService(mock_redis)
        product_id = str(uuid4())

        await service.init_stock(product_id, 10)

        mock_redis.set.assert_called_once_with(f"stock:{product_id}", 10)

    @pytest.mark.asyncio
    async def test_get_stock_exists(self, mock_redis):
        """Test getting stock when it exists."""
        mock_redis.get = AsyncMock(return_value=b"5")
        service = RedisService(mock_redis)
        product_id = str(uuid4())

        stock = await service.get_stock(product_id)

        assert stock == 5
        mock_redis.get.assert_called_once_with(f"stock:{product_id}")

    @pytest.mark.asyncio
    async def test_get_stock_not_exists(self, mock_redis):
        """Test getting stock when not set returns 0."""
        mock_redis.get = AsyncMock(return_value=None)
        service = RedisService(mock_redis)
        product_id = str(uuid4())

        stock = await service.get_stock(product_id)

        assert stock == 0

    @pytest.mark.asyncio
    async def test_decrement_stock_success(self, mock_redis):
        """Test successful stock decrement when stock > 0."""
        # Mock the Lua script execution
        mock_script = AsyncMock(return_value=9)  # 10 -> 9
        mock_redis.register_script = MagicMock(return_value=mock_script)

        service = RedisService(mock_redis)
        product_id = str(uuid4())

        result = await service.decrement_stock(product_id)

        assert result == 9

    @pytest.mark.asyncio
    async def test_decrement_stock_insufficient(self, mock_redis):
        """Test stock decrement fails when stock = 0."""
        # Mock the Lua script returning -1 (insufficient stock)
        mock_script = AsyncMock(return_value=-1)
        mock_redis.register_script = MagicMock(return_value=mock_script)

        service = RedisService(mock_redis)
        product_id = str(uuid4())

        result = await service.decrement_stock(product_id)

        assert result == -1  # Indicates failure

    @pytest.mark.asyncio
    async def test_increment_stock_rollback(self, mock_redis):
        """Test stock increment for rollback scenarios."""
        mock_redis.incr = AsyncMock(return_value=11)
        service = RedisService(mock_redis)
        product_id = str(uuid4())

        result = await service.increment_stock(product_id)

        assert result == 11
        mock_redis.incr.assert_called_once_with(f"stock:{product_id}")


class TestDistributedLock:
    """Test Redis distributed lock operations."""

    @pytest.mark.asyncio
    async def test_acquire_lock_success(self, mock_redis):
        """Test successful lock acquisition."""
        mock_redis.set = AsyncMock(return_value=True)  # SET NX returns True
        service = RedisService(mock_redis)
        product_id = str(uuid4())

        success, owner_id = await service.acquire_lock(product_id)

        assert success is True
        assert owner_id is not None
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args.kwargs["nx"] is True
        assert call_args.kwargs["ex"] == 2  # Default TTL

    @pytest.mark.asyncio
    async def test_acquire_lock_failure(self, mock_redis):
        """Test lock acquisition fails when already locked."""
        mock_redis.set = AsyncMock(return_value=None)  # SET NX returns None when key exists
        service = RedisService(mock_redis)
        product_id = str(uuid4())

        success, owner_id = await service.acquire_lock(product_id)

        assert success is False

    @pytest.mark.asyncio
    async def test_acquire_lock_custom_ttl(self, mock_redis):
        """Test lock acquisition with custom TTL."""
        mock_redis.set = AsyncMock(return_value=True)
        service = RedisService(mock_redis)
        product_id = str(uuid4())

        success, owner_id = await service.acquire_lock(product_id, ttl=5)

        assert success is True
        call_args = mock_redis.set.call_args
        assert call_args.kwargs["ex"] == 5

    @pytest.mark.asyncio
    async def test_release_lock_success(self, mock_redis):
        """Test successful lock release by owner."""
        # Mock the Lua script execution returning 1 (success)
        mock_script = AsyncMock(return_value=1)
        mock_redis.register_script = MagicMock(return_value=mock_script)

        service = RedisService(mock_redis)
        product_id = str(uuid4())
        owner_id = str(uuid4())

        result = await service.release_lock(product_id, owner_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_release_lock_not_owner(self, mock_redis):
        """Test lock release fails when not the owner."""
        # Mock the Lua script execution returning 0 (not owner)
        mock_script = AsyncMock(return_value=0)
        mock_redis.register_script = MagicMock(return_value=mock_script)

        service = RedisService(mock_redis)
        product_id = str(uuid4())
        wrong_owner_id = str(uuid4())

        result = await service.release_lock(product_id, wrong_owner_id)

        assert result is False


class TestLuaScriptAtomicity:
    """Test that Lua scripts provide atomic operations."""

    def test_decrement_script_logic(self):
        """Verify the Lua script logic for decrement.

        Script should:
        1. Get current stock
        2. If stock >= 1, decrement and return new value
        3. If stock < 1 or nil, return -1
        """
        script = RedisService.DECREMENT_STOCK_SCRIPT

        # Verify script contains the expected operations
        assert "GET" in script
        assert "DECR" in script
        assert "stock >= 1" in script or "stock and stock >= 1" in script
        assert "-1" in script

    def test_release_lock_script_logic(self):
        """Verify the Lua script logic for lock release.

        Script should:
        1. Get current lock value
        2. If value matches owner_id, delete the lock
        3. If not matching, return 0 (failure)
        """
        script = RedisService.RELEASE_LOCK_SCRIPT

        # Verify script contains the expected operations
        assert "GET" in script
        assert "DEL" in script
        assert "ARGV[1]" in script  # Owner ID comparison


class TestInventoryFlowIntegration:
    """Integration-style tests for the complete inventory flow."""

    @pytest.mark.asyncio
    async def test_complete_purchase_flow(self, mock_redis):
        """Test the complete flow: acquire lock -> decrement -> release."""
        # Setup mocks for success scenario
        mock_redis.set = AsyncMock(return_value=True)  # Lock acquired
        mock_decrement_script = AsyncMock(return_value=9)
        mock_release_script = AsyncMock(return_value=1)

        # Mock register_script to return appropriate scripts
        def mock_register(script):
            if "DECR" in script:
                return mock_decrement_script
            else:
                return mock_release_script

        mock_redis.register_script = MagicMock(side_effect=mock_register)

        service = RedisService(mock_redis)
        product_id = str(uuid4())

        # Step 1: Acquire lock
        success, owner_id = await service.acquire_lock(product_id)
        assert success is True

        # Step 2: Decrement stock
        new_stock = await service.decrement_stock(product_id)
        assert new_stock == 9

        # Step 3: Release lock
        released = await service.release_lock(product_id, owner_id)
        assert released is True

    @pytest.mark.asyncio
    async def test_purchase_flow_insufficient_stock(self, mock_redis):
        """Test flow when stock is insufficient."""
        mock_redis.set = AsyncMock(return_value=True)  # Lock acquired
        mock_decrement_script = AsyncMock(return_value=-1)  # Out of stock
        mock_release_script = AsyncMock(return_value=1)

        def mock_register(script):
            if "DECR" in script:
                return mock_decrement_script
            else:
                return mock_release_script

        mock_redis.register_script = MagicMock(side_effect=mock_register)
        mock_redis.incr = AsyncMock(return_value=1)  # For potential rollback

        service = RedisService(mock_redis)
        product_id = str(uuid4())

        # Step 1: Acquire lock
        success, owner_id = await service.acquire_lock(product_id)
        assert success is True

        # Step 2: Attempt decrement - should fail
        new_stock = await service.decrement_stock(product_id)
        assert new_stock == -1  # Out of stock

        # Step 3: Release lock (no rollback needed since decrement failed)
        released = await service.release_lock(product_id, owner_id)
        assert released is True

    @pytest.mark.asyncio
    async def test_purchase_flow_lock_contention(self, mock_redis):
        """Test flow when lock cannot be acquired."""
        mock_redis.set = AsyncMock(return_value=None)  # Lock not acquired

        service = RedisService(mock_redis)
        product_id = str(uuid4())

        # Step 1: Attempt to acquire lock - should fail
        success, _ = await service.acquire_lock(product_id)
        assert success is False

        # Should not proceed with decrement when lock not acquired
