"""Tests for ranking service operations.

Tests verify Redis sorted set operations for:
- Updating user rankings
- Getting top K users
- Getting user rank
- Getting minimum winning score
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.services.redis_service import RedisService


class TestRankingOperations:
    """Test ranking operations using Redis sorted sets."""

    @pytest.mark.asyncio
    async def test_update_ranking(self, mock_redis):
        """Test adding/updating user to ranking."""
        service = RedisService(mock_redis)
        campaign_id = str(uuid4())
        user_id = str(uuid4())
        score = 1500.0

        await service.update_ranking(campaign_id, user_id, score)

        mock_redis.zadd.assert_called_once_with(
            f"bid:{campaign_id}",
            {user_id: score}
        )

    @pytest.mark.asyncio
    async def test_update_ranking_overwrites(self, mock_redis):
        """Test that updating ranking overwrites previous score."""
        service = RedisService(mock_redis)
        campaign_id = str(uuid4())
        user_id = str(uuid4())

        # First bid
        await service.update_ranking(campaign_id, user_id, 1000.0)
        # Second bid (higher)
        await service.update_ranking(campaign_id, user_id, 1500.0)

        # Should have been called twice
        assert mock_redis.zadd.call_count == 2
        # Last call should have the higher score
        last_call = mock_redis.zadd.call_args_list[-1]
        assert last_call[0][1][user_id] == 1500.0

    @pytest.mark.asyncio
    async def test_get_top_k(self, mock_redis):
        """Test getting top K ranked users."""
        # Mock ZREVRANGE response: list of (member, score) tuples
        mock_redis.zrevrange = AsyncMock(return_value=[
            (b"user1", 1500.0),
            (b"user2", 1400.0),
            (b"user3", 1300.0),
        ])

        service = RedisService(mock_redis)
        campaign_id = str(uuid4())

        results = await service.get_top_k(campaign_id, k=3)

        assert len(results) == 3
        assert results[0]["rank"] == 1
        assert results[0]["user_id"] == b"user1"
        assert results[0]["score"] == 1500.0
        assert results[1]["rank"] == 2
        assert results[2]["rank"] == 3

    @pytest.mark.asyncio
    async def test_get_top_k_less_than_k_users(self, mock_redis):
        """Test getting top K when fewer than K users exist."""
        mock_redis.zrevrange = AsyncMock(return_value=[
            (b"user1", 1500.0),
            (b"user2", 1400.0),
        ])

        service = RedisService(mock_redis)
        campaign_id = str(uuid4())

        results = await service.get_top_k(campaign_id, k=5)

        assert len(results) == 2  # Only 2 users exist

    @pytest.mark.asyncio
    async def test_get_top_k_empty(self, mock_redis):
        """Test getting top K when no users in ranking."""
        mock_redis.zrevrange = AsyncMock(return_value=[])

        service = RedisService(mock_redis)
        campaign_id = str(uuid4())

        results = await service.get_top_k(campaign_id, k=10)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_user_rank(self, mock_redis):
        """Test getting user's rank (1-indexed)."""
        # ZREVRANK returns 0-indexed rank
        mock_redis.zrevrank = AsyncMock(return_value=2)  # 3rd place (0-indexed)

        service = RedisService(mock_redis)
        campaign_id = str(uuid4())
        user_id = str(uuid4())

        rank = await service.get_user_rank(campaign_id, user_id)

        assert rank == 3  # 1-indexed rank

    @pytest.mark.asyncio
    async def test_get_user_rank_first_place(self, mock_redis):
        """Test getting first place user's rank."""
        mock_redis.zrevrank = AsyncMock(return_value=0)  # First place (0-indexed)

        service = RedisService(mock_redis)
        campaign_id = str(uuid4())
        user_id = str(uuid4())

        rank = await service.get_user_rank(campaign_id, user_id)

        assert rank == 1  # 1-indexed first place

    @pytest.mark.asyncio
    async def test_get_user_rank_not_in_ranking(self, mock_redis):
        """Test getting rank for user not in ranking."""
        mock_redis.zrevrank = AsyncMock(return_value=None)

        service = RedisService(mock_redis)
        campaign_id = str(uuid4())
        user_id = str(uuid4())

        rank = await service.get_user_rank(campaign_id, user_id)

        assert rank is None

    @pytest.mark.asyncio
    async def test_get_user_score(self, mock_redis):
        """Test getting user's score."""
        mock_redis.zscore = AsyncMock(return_value=1234.56)

        service = RedisService(mock_redis)
        campaign_id = str(uuid4())
        user_id = str(uuid4())

        score = await service.get_user_score(campaign_id, user_id)

        assert score == 1234.56

    @pytest.mark.asyncio
    async def test_get_user_score_not_in_ranking(self, mock_redis):
        """Test getting score for user not in ranking."""
        mock_redis.zscore = AsyncMock(return_value=None)

        service = RedisService(mock_redis)
        campaign_id = str(uuid4())
        user_id = str(uuid4())

        score = await service.get_user_score(campaign_id, user_id)

        assert score is None

    @pytest.mark.asyncio
    async def test_get_total_participants(self, mock_redis):
        """Test getting total number of participants."""
        mock_redis.zcard = AsyncMock(return_value=42)

        service = RedisService(mock_redis)
        campaign_id = str(uuid4())

        total = await service.get_total_participants(campaign_id)

        assert total == 42
        mock_redis.zcard.assert_called_once_with(f"bid:{campaign_id}")

    @pytest.mark.asyncio
    async def test_get_total_participants_empty(self, mock_redis):
        """Test getting total participants when none exist."""
        mock_redis.zcard = AsyncMock(return_value=0)

        service = RedisService(mock_redis)
        campaign_id = str(uuid4())

        total = await service.get_total_participants(campaign_id)

        assert total == 0


class TestMinWinningScore:
    """Test minimum winning score calculations."""

    @pytest.mark.asyncio
    async def test_get_min_winning_score(self, mock_redis):
        """Test getting minimum winning score (Kth highest score)."""
        # K=3, so we get the 3rd highest score
        mock_redis.zrevrange = AsyncMock(return_value=[
            (b"user3", 1300.0),  # The Kth element
        ])

        service = RedisService(mock_redis)
        campaign_id = str(uuid4())

        min_score = await service.get_min_winning_score(campaign_id, k=3)

        assert min_score == 1300.0
        # Should request element at index k-1 to k-1 (single element)
        mock_redis.zrevrange.assert_called_with(
            f"bid:{campaign_id}", 2, 2, withscores=True
        )

    @pytest.mark.asyncio
    async def test_get_min_winning_score_less_than_k_users(self, mock_redis):
        """Test min winning score when fewer than K participants."""
        mock_redis.zrevrange = AsyncMock(return_value=[])  # Less than K users

        service = RedisService(mock_redis)
        campaign_id = str(uuid4())

        min_score = await service.get_min_winning_score(campaign_id, k=5)

        assert min_score is None  # Not enough participants

    @pytest.mark.asyncio
    async def test_get_max_score(self, mock_redis):
        """Test getting maximum score in campaign."""
        mock_redis.zrevrange = AsyncMock(return_value=[
            (b"top_user", 2000.0),
        ])

        service = RedisService(mock_redis)
        campaign_id = str(uuid4())

        max_score = await service.get_max_score(campaign_id)

        assert max_score == 2000.0
        mock_redis.zrevrange.assert_called_with(
            f"bid:{campaign_id}", 0, 0, withscores=True
        )

    @pytest.mark.asyncio
    async def test_get_max_score_empty(self, mock_redis):
        """Test getting max score when no participants."""
        mock_redis.zrevrange = AsyncMock(return_value=[])

        service = RedisService(mock_redis)
        campaign_id = str(uuid4())

        max_score = await service.get_max_score(campaign_id)

        assert max_score is None


class TestRankingOrder:
    """Test that ranking maintains correct order."""

    @pytest.mark.asyncio
    async def test_ranking_order_by_score(self, mock_redis):
        """Verify that higher scores rank higher."""
        # Simulated ranking data
        mock_redis.zrevrange = AsyncMock(return_value=[
            (b"user_high", 2000.0),   # Rank 1
            (b"user_mid", 1500.0),    # Rank 2
            (b"user_low", 1000.0),    # Rank 3
        ])

        service = RedisService(mock_redis)
        campaign_id = str(uuid4())

        results = await service.get_top_k(campaign_id, k=10)

        # Verify descending order
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

        # Verify correct ranking assignment
        for i, result in enumerate(results):
            assert result["rank"] == i + 1


class TestCampaignCache:
    """Test campaign cache operations."""

    @pytest.mark.asyncio
    async def test_cache_campaign(self, mock_redis):
        """Test caching campaign parameters."""
        service = RedisService(mock_redis)
        campaign_id = str(uuid4())
        data = {
            "product_id": str(uuid4()),
            "alpha": "1.0",
            "beta": "1000.0",
            "gamma": "100.0",
            "min_price": "100.00",
            "stock": "10",
        }

        await service.cache_campaign(campaign_id, data)

        mock_redis.hset.assert_called_once()
        call_args = mock_redis.hset.call_args
        assert call_args.kwargs["mapping"]["stock"] == "10"

    @pytest.mark.asyncio
    async def test_get_cached_campaign(self, mock_redis):
        """Test getting cached campaign parameters."""
        mock_redis.hgetall = AsyncMock(return_value={
            b"product_id": b"some-uuid",
            b"stock": b"10",
            b"alpha": b"1.0",
        })

        service = RedisService(mock_redis)
        campaign_id = str(uuid4())

        data = await service.get_cached_campaign(campaign_id)

        assert data is not None
        mock_redis.hgetall.assert_called_once_with(f"campaign:{campaign_id}")

    @pytest.mark.asyncio
    async def test_get_cached_campaign_not_exists(self, mock_redis):
        """Test getting non-existent cached campaign."""
        mock_redis.hgetall = AsyncMock(return_value={})

        service = RedisService(mock_redis)
        campaign_id = str(uuid4())

        data = await service.get_cached_campaign(campaign_id)

        assert data is None

    @pytest.mark.asyncio
    async def test_invalidate_campaign_cache(self, mock_redis):
        """Test invalidating campaign cache."""
        mock_redis.delete = AsyncMock(return_value=1)

        service = RedisService(mock_redis)
        campaign_id = str(uuid4())

        result = await service.invalidate_campaign_cache(campaign_id)

        assert result is True
        mock_redis.delete.assert_called_once_with(f"campaign:{campaign_id}")
