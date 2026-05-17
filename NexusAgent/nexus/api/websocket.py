"""NEXUS API — WebSocket endpoint with authentication."""
from __future__ import annotations

import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from nexus.core.config import get_settings

logger = logging.getLogger("nexus.websocket")
router = APIRouter()

connected_clients: dict[str, WebSocket] = {}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str | None = None):
    """WebSocket endpoint for real-time events."""
    settings = get_settings()

    # Auth check in production
    if settings.nexus_env == "production":
        if not token or token != settings.nexus_secret_key:
            await websocket.close(code=4001, reason="Invalid token")
            return

    await websocket.accept()
    client_id = id(websocket)
    connected_clients[client_id] = websocket
    logger.info(f"WebSocket client connected: {client_id}")

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                await handle_message(message, websocket)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {client_id}")
        connected_clients.pop(client_id, None)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        connected_clients.pop(client_id, None)


async def handle_message(message: dict, websocket: WebSocket):
    """Handle incoming WebSocket messages."""
    msg_type = message.get("type")

    if msg_type == "ping":
        await websocket.send_json({"type": "pong"})
    elif msg_type == "subscribe":
        channel = message.get("channel")
        await websocket.send_json({"type": "subscribed", "channel": channel})
    else:
        await websocket.send_json({"type": "error", "message": "Unknown message type"})


async def broadcast(event: dict):
    """Broadcast an event to all connected clients."""
    disconnected = []
    for client_id, client in connected_clients.items():
        try:
            await client.send_json(event)
        except Exception:
            disconnected.append(client_id)

    for client_id in disconnected:
        connected_clients.pop(client_id, None)
