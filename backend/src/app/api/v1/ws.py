"""WebSocket endpoint for real-time bidding updates."""

import logging
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.security import decode_access_token
from app.services.ws_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/{campaign_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    campaign_id: str,
    token: str = Query(..., description="JWT access token"),
):
    """WebSocket endpoint for real-time campaign updates.

    Connection URL: ws://host/ws/{campaign_id}?token={jwt_token}

    Events pushed to client:
    - ranking_update: Periodic ranking updates (every 1-2 seconds)
    - bid_accepted: When user's bid is accepted
    - campaign_ended: When campaign ends

    Client can send:
    - ping: Server responds with pong (heartbeat)
    """
    # Authenticate user from token
    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_id = payload.get("sub")
    if user_id is None:
        await websocket.close(code=4001, reason="Invalid token payload")
        return

    # Validate campaign_id format
    try:
        UUID(campaign_id)
    except ValueError:
        await websocket.close(code=4002, reason="Invalid campaign ID")
        return

    # Accept connection and join campaign room
    await manager.connect(campaign_id, user_id, websocket)

    try:
        while True:
            # Wait for messages from client (heartbeat)
            data = await websocket.receive_text()

            # Handle ping/pong heartbeat
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: campaign={campaign_id}, user={user_id}")
    except Exception as e:
        logger.error(f"WebSocket error: campaign={campaign_id}, user={user_id}, error={e}")
    finally:
        await manager.disconnect(campaign_id, user_id)
