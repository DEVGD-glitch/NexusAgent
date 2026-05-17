"""Workflow Triggers — Events that start workflow execution."""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class TriggerType(str, Enum):
    """Types of workflow triggers."""
    TIMER = "timer"
    FILE_CHANGE = "file_change"
    WEBHOOK = "webhook"
    EVENT = "event"
    MANUAL = "manual"
    STARTUP = "startup"
    SHUTDOWN = "shutdown"
    AGENT_EVENT = "agent_event"
    MCP_EVENT = "mcp_event"
    ERROR = "error"


@dataclass(frozen=True)
class TriggerContext:
    """Context passed when a trigger fires."""
    trigger_type: TriggerType
    trigger_id: str
    timestamp: float
    data: dict[str, Any] = field(default_factory=dict)
    source: str = ""


TriggerCallback = Callable[[TriggerContext], Awaitable[None]]


class Trigger(ABC):
    """Base class for workflow triggers."""

    def __init__(self, trigger_id: str, trigger_type: TriggerType) -> None:
        self.trigger_id = trigger_id
        self.trigger_type = trigger_type
        self._callbacks: list[TriggerCallback] = []
        self._active = False

    def on_fire(self, callback: TriggerCallback) -> None:
        self._callbacks.append(callback)

    async def fire(self, data: dict[str, Any] | None = None) -> None:
        ctx = TriggerContext(
            trigger_type=self.trigger_type,
            trigger_id=self.trigger_id,
            timestamp=time.time(),
            data=data or {},
        )
        logger.info("Trigger fired: %s (%s)", self.trigger_id, self.trigger_type.value)
        for cb in self._callbacks:
            try:
                await cb(ctx)
            except Exception as exc:
                logger.error("Trigger callback error for %s: %s", self.trigger_id, exc)

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "trigger_type": self.trigger_type.value,
            "active": self._active,
        }


class TimerTrigger(Trigger):
    """Fires on a periodic interval."""

    def __init__(self, trigger_id: str, interval_seconds: float) -> None:
        super().__init__(trigger_id, TriggerType.TIMER)
        self.interval = interval_seconds
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._active = True
        self._task = asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        while self._active:
            await asyncio.sleep(self.interval)
            if self._active:
                await self.fire()

    async def stop(self) -> None:
        self._active = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


class FileChangeTrigger(Trigger):
    """Fires when a file is modified."""

    def __init__(self, trigger_id: str, path: str, pattern: str = "*") -> None:
        super().__init__(trigger_id, TriggerType.FILE_CHANGE)
        self.path = Path(path)
        self.pattern = pattern
        self._task: asyncio.Task | None = None
        self._last_modified: dict[str, float] = {}

    async def start(self) -> None:
        self._active = True
        self._scan()
        self._task = asyncio.create_task(self._loop())

    def _scan(self) -> None:
        if self.path.is_dir():
            for f in self.path.glob(self.pattern):
                if f.is_file():
                    self._last_modified[str(f)] = f.stat().st_mtime

    async def _loop(self) -> None:
        while self._active:
            await asyncio.sleep(1.0)
            if not self._active:
                break
            if self.path.is_dir():
                for f in self.path.glob(self.pattern):
                    if f.is_file():
                        key = str(f)
                        mtime = f.stat().st_mtime
                        if key in self._last_modified and mtime > self._last_modified[key]:
                            await self.fire({"path": key, "mtime": mtime})
                        self._last_modified[key] = mtime

    async def stop(self) -> None:
        self._active = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


class WebhookTrigger(Trigger):
    """Fires when an HTTP POST hits the webhook endpoint."""

    def __init__(self, trigger_id: str, path: str = "/webhook") -> None:
        super().__init__(trigger_id, TriggerType.WEBHOOK)
        self.webhook_path = path

    async def start(self) -> None:
        self._active = True
        logger.info("Webhook trigger %s ready at %s", self.trigger_id, self.webhook_path)

    async def stop(self) -> None:
        self._active = False

    async def handle_request(self, body: dict[str, Any]) -> None:
        if self._active:
            await self.fire(body)


class EventTrigger(Trigger):
    """Fires on named events from the event bus."""

    def __init__(self, trigger_id: str, event_name: str) -> None:
        super().__init__(trigger_id, TriggerType.EVENT)
        self.event_name = event_name

    async def start(self) -> None:
        self._active = True
        logger.info("Event trigger %s listening for '%s'", self.trigger_id, self.event_name)

    async def stop(self) -> None:
        self._active = False

    async def on_event(self, event_data: dict[str, Any]) -> None:
        if self._active:
            await self.fire(event_data)


class ManualTrigger(Trigger):
    """Fires only when explicitly invoked."""

    def __init__(self, trigger_id: str) -> None:
        super().__init__(trigger_id, TriggerType.MANUAL)

    async def start(self) -> None:
        self._active = True

    async def stop(self) -> None:
        self._active = False


class TriggerFactory:
    """Creates trigger instances from configuration dicts."""

    _creators: dict[str, type[Trigger]] = {
        "timer": TimerTrigger,
        "file_change": FileChangeTrigger,
        "webhook": WebhookTrigger,
        "event": EventTrigger,
        "manual": ManualTrigger,
    }

    @classmethod
    def create(cls, config: dict[str, Any]) -> Trigger:
        ttype = config.get("type", "manual")
        tid = config.get("id", f"trigger_{int(time.time())}")

        if ttype == "timer":
            return TimerTrigger(tid, config.get("interval_seconds", 60))
        elif ttype == "file_change":
            return FileChangeTrigger(tid, config.get("path", "."), config.get("pattern", "*"))
        elif ttype == "webhook":
            return WebhookTrigger(tid, config.get("path", "/webhook"))
        elif ttype == "event":
            return EventTrigger(tid, config.get("event_name", "default"))
        else:
            return ManualTrigger(tid)
