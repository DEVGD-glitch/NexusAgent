"""
NEXUS Event Broadcaster — Real-time pub/sub for agent activity streaming.

Provides a singleton EventBroadcaster that any part of the backend can use
to broadcast events, and WebSocket subscribers receive them in real-time.

Event types:
  - agent_thinking  : Agent is reasoning / planning
  - agent_action    : Agent has decided on an action
  - tool_call       : A tool is about to be invoked
  - tool_result     : A tool has returned a result
  - file_create     : A new file was created
  - file_edit       : An existing file was modified
  - code_building   : Code is being compiled / built
  - task_step       : A step in a multi-step task is starting
  - task_done       : A task has completed
  - error           : An error occurred
  - avatar_expression : Avatar facial expression change
  - stream_token    : A single token from LLM streaming

Usage:
    from nexus.core.events import get_broadcaster

    broadcaster = get_broadcaster()
    await broadcaster.broadcast("agent_thinking", {"thought": "Analyzing request..."})
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# All valid event types that can be broadcast
VALID_EVENT_TYPES = frozenset({
    "agent_thinking",
    "agent_action",
    "tool_call",
    "tool_result",
    "file_create",
    "file_edit",
    "code_building",
    "task_step",
    "task_done",
    "error",
    "avatar_expression",
    "avatar_expression_change",
    "avatar_speaking_start",
    "avatar_speaking_end",
    "stream_token",
    "viz_event",
})


@dataclass
class _Subscriber:
    """Internal representation of a WebSocket subscriber."""
    websocket: WebSocket
    queue: asyncio.Queue
    subscriber_id: str
    connected_at: float = field(default_factory=time.time)


class EventBroadcaster:
    """
    Thread-safe async pub/sub broadcaster for real-time agent events.

    Each subscriber gets its own asyncio.Queue so slow consumers don't
    block fast ones. Events are broadcast to all connected subscribers.

    Designed as a singleton — use get_broadcaster() to obtain the instance.
    """

    def __init__(self):
        self._subscribers: dict[str, _Subscriber] = {}
        self._lock = threading.Lock()
        self._event_count: int = 0

    # ── Subscribe / Unsubscribe ────────────────────────────────────

    async def subscribe(self, websocket: WebSocket) -> str:
        """
        Register a WebSocket as a subscriber.

        Returns the subscriber_id for tracking.
        """
        subscriber_id = str(uuid.uuid4())[:8]
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)

        sub = _Subscriber(
            websocket=websocket,
            queue=queue,
            subscriber_id=subscriber_id,
        )

        with self._lock:
            self._subscribers[subscriber_id] = sub

        logger.info(
            "WebSocket subscriber connected: %s (total: %d)",
            subscriber_id,
            len(self._subscribers),
        )

        # Send a welcome event so the client knows the connection is live
        await self._send_to_subscriber(sub, {
            "type": "connected",
            "subscriber_id": subscriber_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "Connected to NEXUS event stream",
        })

        return subscriber_id

    async def unsubscribe(self, websocket: WebSocket) -> None:
        """
        Remove a WebSocket subscriber. Safe to call even if not subscribed.
        """
        to_remove = None
        with self._lock:
            for sid, sub in self._subscribers.items():
                if sub.websocket is websocket:
                    to_remove = sid
                    break

        if to_remove:
            with self._lock:
                self._subscribers.pop(to_remove, None)
            logger.info(
                "WebSocket subscriber disconnected: %s (remaining: %d)",
                to_remove,
                len(self._subscribers),
            )

    # ── Broadcast ──────────────────────────────────────────────────

    async def broadcast(self, event_type: str, data: Any = None) -> None:
        """
        Broadcast an event to all connected subscribers.

        Args:
            event_type: One of VALID_EVENT_TYPES (or any custom string).
            data: Arbitrary JSON-serializable payload.

        The event is delivered as a JSON message:
            {
                "type": "agent_thinking",
                "data": { ... },
                "timestamp": "2025-03-04T12:34:56.789Z",
                "event_id": "evt_abc123"
            }
        """
        event = {
            "type": event_type,
            "data": data if data is not None else {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_id": f"evt_{uuid.uuid4().hex[:8]}",
        }

        self._event_count += 1

        # Snapshot subscribers under lock, then send outside lock
        with self._lock:
            subscribers = list(self._subscribers.values())

        if not subscribers:
            return

        # Send to each subscriber's queue (non-blocking)
        for sub in subscribers:
            try:
                sub.queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest event and try again to avoid blocking
                try:
                    sub.queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    sub.queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning(
                        "Dropping event for subscriber %s (queue full)",
                        sub.subscriber_id,
                    )

    def broadcast_sync(self, event_type: str, data: Any = None) -> None:
        """
        Synchronous wrapper for broadcast() — safe to call from sync code.

        Creates a new event loop if there isn't one running (e.g. in a thread).
        If called from within a running loop, schedules the broadcast as a task.
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast(event_type, data))
        except RuntimeError:
            # No running loop — use a dedicated background loop
            try:
                # Create a new loop in a background thread if needed
                if not hasattr(self, '_bg_loop'):
                    import threading
                    self._bg_loop = asyncio.new_event_loop()
                    threading.Thread(target=self._bg_loop.run_forever, daemon=True).start()
                asyncio.run_coroutine_threadsafe(self.broadcast(event_type, data), self._bg_loop)
            except Exception as exc:
                logger.debug("broadcast_sync failed: %s", exc)

    # ── Subscriber event pump ──────────────────────────────────────

    async def pump_subscriber(self, websocket: WebSocket) -> None:
        """
        Forward events from the subscriber's queue to the WebSocket.

        This should be run as an async task for each connected subscriber.
        It will exit when the subscriber disconnects or an error occurs.
        """
        # Find the subscriber for this websocket
        sub = None
        with self._lock:
            for s in self._subscribers.values():
                if s.websocket is websocket:
                    sub = s
                    break

        if sub is None:
            logger.warning("pump_subscriber called for unknown websocket")
            return

        try:
            while True:
                event = await sub.queue.get()
                try:
                    await websocket.send_json(event)
                except Exception as exc:
                    logger.debug(
                        "Failed to send event to subscriber %s: %s",
                        sub.subscriber_id, exc,
                    )
                    break
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.debug("Event pump error for %s: %s", sub.subscriber_id, exc)
        finally:
            await self.unsubscribe(websocket)

    # ── Internal helpers ───────────────────────────────────────────

    async def _send_to_subscriber(self, sub: _Subscriber, event: dict) -> None:
        """Send a single event directly to a subscriber's WebSocket."""
        try:
            await sub.websocket.send_json(event)
        except Exception as exc:
            logger.debug(
                "Failed to send to subscriber %s: %s",
                sub.subscriber_id, exc,
            )

    # ── Status / introspection ─────────────────────────────────────

    @property
    def subscriber_count(self) -> int:
        """Number of currently connected subscribers."""
        with self._lock:
            return len(self._subscribers)

    @property
    def total_events_broadcast(self) -> int:
        """Total number of events broadcast since startup."""
        return self._event_count

    def get_status(self) -> dict[str, Any]:
        """Get broadcaster status for monitoring."""
        with self._lock:
            return {
                "connected_subscribers": len(self._subscribers),
                "total_events_broadcast": self._event_count,
                "subscriber_ids": list(self._subscribers.keys()),
            }


# ═══════════════════════════════════════════════════════════════════
# Singleton accessor
# ═══════════════════════════════════════════════════════════════════

_broadcaster: Optional[EventBroadcaster] = None
_broadcaster_lock = threading.Lock()


def get_broadcaster() -> EventBroadcaster:
    """
    Get the global EventBroadcaster singleton.

    Thread-safe: uses double-checked locking to ensure
    the singleton is created exactly once under concurrent access.
    """
    global _broadcaster
    if _broadcaster is None:
        with _broadcaster_lock:
            if _broadcaster is None:
                _broadcaster = EventBroadcaster()
    return _broadcaster
