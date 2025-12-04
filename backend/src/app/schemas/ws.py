"""WebSocket event schemas for real-time communication."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class RankingEntry(BaseModel):
    """Single entry in the ranking list."""

    rank: int
    user_id: str
    score: float
    username: str | None = None


class RankingUpdateData(BaseModel):
    """Data payload for ranking update event."""

    campaign_id: str
    top_k: list[RankingEntry]
    total_participants: int
    min_winning_score: float | None
    max_score: float | None
    timestamp: datetime


class RankingUpdateEvent(BaseModel):
    """Ranking update event pushed to all users in a campaign room."""

    event: Literal["ranking_update"] = "ranking_update"
    data: RankingUpdateData


class BidAcceptedData(BaseModel):
    """Data payload for bid accepted event."""

    bid_id: str
    campaign_id: str
    price: float
    score: float
    rank: int
    time_elapsed_ms: int
    timestamp: datetime


class BidAcceptedEvent(BaseModel):
    """Bid accepted event pushed to the user who placed the bid."""

    event: Literal["bid_accepted"] = "bid_accepted"
    data: BidAcceptedData


class StatsUpdateData(BaseModel):
    """Data payload for stats update event."""

    campaign_id: str
    total_participants: int
    total_bids: int
    timestamp: datetime


class StatsUpdateEvent(BaseModel):
    """Statistics update event pushed periodically."""

    event: Literal["stats_update"] = "stats_update"
    data: StatsUpdateData


class CampaignEndedData(BaseModel):
    """Data payload for campaign ended event."""

    campaign_id: str
    is_winner: bool
    final_rank: int | None = None
    final_score: float | None = None
    final_price: float | None = None


class CampaignEndedEvent(BaseModel):
    """Campaign ended event pushed when a campaign is settled."""

    event: Literal["campaign_ended"] = "campaign_ended"
    data: CampaignEndedData


# Type alias for all WebSocket events
WSEvent = RankingUpdateEvent | BidAcceptedEvent | StatsUpdateEvent | CampaignEndedEvent
