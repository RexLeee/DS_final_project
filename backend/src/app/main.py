import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, bids, campaigns, orders, products, rankings, ws
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.middleware.rate_limit import RateLimitMiddleware
from app.services.redis_service import RedisService
from app.services.settlement_service import SettlementService
from app.services.ws_manager import broadcast_ranking_update, manager

logger = logging.getLogger(__name__)

# Background task control
_ranking_broadcast_task: asyncio.Task | None = None
_settlement_check_task: asyncio.Task | None = None


async def ranking_broadcast_loop():
    """Background task to broadcast ranking updates every 2 seconds."""
    while True:
        try:
            # Get all active campaign rooms
            active_campaigns = manager.get_active_campaigns()

            if active_campaigns:
                redis = await get_redis()
                redis_service = RedisService(redis)

                for campaign_id in active_campaigns:
                    try:
                        # Get campaign stock (K) from Redis cache
                        cached_params = await redis_service.get_cached_campaign(campaign_id)
                        if cached_params and "stock" in cached_params:
                            k = int(cached_params["stock"])
                        else:
                            k = 10  # fallback default

                        # Get ranking data from Redis
                        top_k = await redis_service.get_top_k(campaign_id, k)
                        total_participants = await redis_service.get_total_participants(
                            campaign_id
                        )
                        min_winning_score = await redis_service.get_min_winning_score(
                            campaign_id, k
                        )
                        max_score = await redis_service.get_max_score(campaign_id)

                        # Broadcast to all connected users
                        if top_k:  # Only broadcast if there are participants
                            await broadcast_ranking_update(
                                campaign_id=campaign_id,
                                top_k=top_k,
                                total_participants=total_participants,
                                min_winning_score=min_winning_score,
                                max_score=max_score,
                            )
                    except Exception as e:
                        logger.error(
                            f"Error broadcasting ranking for campaign {campaign_id}: {e}"
                        )

            await asyncio.sleep(2)  # Broadcast every 2 seconds

        except asyncio.CancelledError:
            logger.info("Ranking broadcast loop cancelled")
            break
        except Exception as e:
            logger.error(f"Error in ranking broadcast loop: {e}")
            await asyncio.sleep(2)


async def settlement_check_loop():
    """Background task to check and settle ended campaigns every 10 seconds."""
    while True:
        try:
            # Use async generator to get db session
            async for db in get_db():
                try:
                    redis = await get_redis()
                    redis_service = RedisService(redis)
                    settlement_service = SettlementService(db, redis_service)

                    # Get campaigns that need settlement
                    campaigns_to_settle = await settlement_service.get_campaigns_to_settle()

                    for campaign in campaigns_to_settle:
                        try:
                            logger.info(f"Starting settlement for campaign {campaign.campaign_id}")
                            orders = await settlement_service.settle_campaign(campaign.campaign_id)
                            logger.info(
                                f"Settled campaign {campaign.campaign_id}, "
                                f"created {len(orders)} orders"
                            )
                        except Exception as e:
                            logger.error(
                                f"Error settling campaign {campaign.campaign_id}: {e}"
                            )
                finally:
                    # Session will be closed by the generator
                    pass
                break  # Only run once per iteration

            await asyncio.sleep(10)  # Check every 10 seconds

        except asyncio.CancelledError:
            logger.info("Settlement check loop cancelled")
            break
        except Exception as e:
            logger.error(f"Error in settlement check loop: {e}")
            await asyncio.sleep(10)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    global _ranking_broadcast_task, _settlement_check_task

    # Startup
    logger.info("Starting background tasks")
    _ranking_broadcast_task = asyncio.create_task(ranking_broadcast_loop())
    _settlement_check_task = asyncio.create_task(settlement_check_loop())

    yield

    # Shutdown
    logger.info("Stopping background tasks")

    if _ranking_broadcast_task:
        _ranking_broadcast_task.cancel()
        try:
            await _ranking_broadcast_task
        except asyncio.CancelledError:
            pass

    if _settlement_check_task:
        _settlement_check_task.cancel()
        try:
            await _settlement_check_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Flash Sale System",
    version="1.0.0",
    description="Real-time Bidding & Flash Sale System",
    lifespan=lifespan,
)

# Rate Limiting Middleware (must be before CORS)
# Load testing config: user_limit=100, ip_limit=10000 (supports 1000 VUs from k6)
# Production recommendation: user_limit=10, ip_limit=100
app.add_middleware(RateLimitMiddleware, user_limit=100, ip_limit=10000)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include API routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(products.router, prefix="/api/v1/products", tags=["products"])
app.include_router(campaigns.router, prefix="/api/v1/campaigns", tags=["campaigns"])
app.include_router(bids.router, prefix="/api/v1/bids", tags=["bids"])
app.include_router(rankings.router, prefix="/api/v1/rankings", tags=["rankings"])
app.include_router(orders.router, prefix="/api/v1/orders", tags=["orders"])

# WebSocket router (no prefix, endpoint is /ws/{campaign_id})
app.include_router(ws.router, tags=["websocket"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
