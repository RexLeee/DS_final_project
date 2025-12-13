"""WebSocket connection manager for real-time communication."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

from app.schemas.ws import (
    BidAcceptedData,
    BidAcceptedEvent,
    CampaignEndedData,
    CampaignEndedEvent,
    RankingEntry,
    RankingUpdateData,
    RankingUpdateEvent,
)

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections organized by campaign rooms.

    Structure: {campaign_id: {user_id: WebSocket}}
    """

    def __init__(self):
        # {campaign_id: {user_id: websocket}}
        self.active_connections: dict[str, dict[str, WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self, campaign_id: str, user_id: str, websocket: WebSocket
    ) -> None:
        """Accept connection and add to campaign room.

        Args:
            campaign_id: Campaign UUID string
            user_id: User UUID string
            websocket: WebSocket connection
        """
        await websocket.accept()

        async with self._lock:
            if campaign_id not in self.active_connections:
                self.active_connections[campaign_id] = {}

            # If user already has a connection, close the old one
            if user_id in self.active_connections[campaign_id]:
                try:
                    old_ws = self.active_connections[campaign_id][user_id]
                    await old_ws.close()
                except Exception:
                    pass

            self.active_connections[campaign_id][user_id] = websocket
            logger.info(
                f"WebSocket connected: campaign={campaign_id}, user={user_id}, "
                f"room_size={len(self.active_connections[campaign_id])}"
            )

    async def disconnect(self, campaign_id: str, user_id: str) -> None:
        """Remove connection from campaign room.

        Args:
            campaign_id: Campaign UUID string
            user_id: User UUID string
        """
        async with self._lock:
            if campaign_id in self.active_connections:
                if user_id in self.active_connections[campaign_id]:
                    del self.active_connections[campaign_id][user_id]
                    logger.info(
                        f"WebSocket disconnected: campaign={campaign_id}, user={user_id}"
                    )

                # Clean up empty rooms
                if not self.active_connections[campaign_id]:
                    del self.active_connections[campaign_id]

    async def send_to_user(
        self, campaign_id: str, user_id: str, message: dict[str, Any]
    ) -> bool:
        """Send message to a specific user in a campaign.

        Args:
            campaign_id: Campaign UUID string
            user_id: User UUID string
            message: JSON-serializable message dict

        Returns:
            True if message was sent, False if user not connected
        """
        if campaign_id not in self.active_connections:
            return False

        if user_id not in self.active_connections[campaign_id]:
            return False

        websocket = self.active_connections[campaign_id][user_id]
        try:
            await websocket.send_json(message)
            return True
        except Exception as e:
            logger.warning(f"Failed to send to user {user_id}: {e}")
            await self.disconnect(campaign_id, user_id)
            return False

    async def broadcast_to_campaign(
        self, campaign_id: str, message: dict[str, Any]
    ) -> int:
        """Broadcast message to all users in a campaign room using concurrent sends.

        Args:
            campaign_id: Campaign UUID string
            message: JSON-serializable message dict

        Returns:
            Number of users successfully sent to
        """
        if campaign_id not in self.active_connections:
            return 0

        # Create a copy to avoid modification during iteration
        connections = dict(self.active_connections.get(campaign_id, {}))

        if not connections:
            return 0

        # Define async send function for each user
        async def send_to_one(user_id: str, ws: WebSocket) -> tuple[str, bool]:
            try:
                await ws.send_json(message)
                return (user_id, True)
            except Exception as e:
                logger.warning(f"Failed to broadcast to user {user_id}: {e}")
                return (user_id, False)

        # Send to all users concurrently using asyncio.gather
        results = await asyncio.gather(
            *[send_to_one(uid, ws) for uid, ws in connections.items()],
            return_exceptions=True,
        )

        # Process results and clean up disconnected users
        sent_count = 0
        disconnected_users = []

        for result in results:
            if isinstance(result, Exception):
                continue
            user_id, success = result
            if success:
                sent_count += 1
            else:
                disconnected_users.append(user_id)

        # Clean up disconnected users
        for user_id in disconnected_users:
            await self.disconnect(campaign_id, user_id)

        return sent_count

    def get_room_size(self, campaign_id: str) -> int:
        """Get number of connected users in a campaign room."""
        return len(self.active_connections.get(campaign_id, {}))

    def get_active_campaigns(self) -> list[str]:
        """Get list of campaign IDs with active connections."""
        return list(self.active_connections.keys())

    def get_connected_users(self, campaign_id: str) -> list[str]:
        """Get list of user IDs connected to a campaign."""
        return list(self.active_connections.get(campaign_id, {}).keys())


# Global singleton instance
manager = ConnectionManager()


async def send_bid_accepted(
    campaign_id: str,
    user_id: str,
    bid_id: str,
    price: float,
    score: float,
    rank: int,
    time_elapsed_ms: int,
) -> bool:
    """Send bid accepted event to a user.

    Args:
        campaign_id: Campaign UUID string
        user_id: User UUID string
        bid_id: Bid UUID string
        price: Bid price
        score: Calculated score
        rank: Current rank
        time_elapsed_ms: Time elapsed since campaign start

    Returns:
        True if sent successfully
    """
    event = BidAcceptedEvent(
        data=BidAcceptedData(
            bid_id=bid_id,
            campaign_id=campaign_id,
            price=price,
            score=score,
            rank=rank,
            time_elapsed_ms=time_elapsed_ms,
            timestamp=datetime.now(timezone.utc),
        )
    )
    return await manager.send_to_user(campaign_id, user_id, event.model_dump(mode="json"))


async def broadcast_ranking_update(
    campaign_id: str,
    top_k: list[dict[str, Any]],
    total_participants: int,
    min_winning_score: float | None,
    max_score: float | None,
) -> int:
    """Broadcast ranking update to all users in a campaign.

    Args:
        campaign_id: Campaign UUID string
        top_k: List of top K rankings from Redis
        total_participants: Total number of participants
        min_winning_score: Minimum score to be in top K
        max_score: Maximum score

    Returns:
        Number of users notified
    """
    ranking_entries = [
        RankingEntry(
            rank=r["rank"],
            user_id=r["user_id"],
            score=r["score"],
            price=r.get("price", 0),
            username=r.get("username"),
        )
        for r in top_k
    ]

    event = RankingUpdateEvent(
        data=RankingUpdateData(
            campaign_id=campaign_id,
            top_k=ranking_entries,
            total_participants=total_participants,
            min_winning_score=min_winning_score,
            max_score=max_score,
            timestamp=datetime.now(timezone.utc),
        )
    )
    return await manager.broadcast_to_campaign(campaign_id, event.model_dump(mode="json"))


async def broadcast_campaign_ended(
    campaign_id: str,
    winners: dict[str, dict[str, Any]],
) -> int:
    """Broadcast campaign ended event to all users.

    Args:
        campaign_id: Campaign UUID string
        winners: Dict of {user_id: {rank, score, price}} for winners

    Returns:
        Number of users notified
    """
    connected_users = manager.get_connected_users(campaign_id)
    sent_count = 0

    for user_id in connected_users:
        is_winner = user_id in winners
        winner_data = winners.get(user_id, {})

        event = CampaignEndedEvent(
            data=CampaignEndedData(
                campaign_id=campaign_id,
                is_winner=is_winner,
                final_rank=winner_data.get("rank") if is_winner else None,
                final_score=winner_data.get("score") if is_winner else None,
                final_price=winner_data.get("price") if is_winner else None,
            )
        )

        if await manager.send_to_user(campaign_id, user_id, event.model_dump(mode="json")):
            sent_count += 1

    return sent_count
