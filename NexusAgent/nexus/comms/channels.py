"""
NEXUS Channel Adapters — Multi-platform communication adapters.

Supports sending and receiving messages through multiple channels:
  - Telegram Bot
  - Discord (future)
  - Slack (future)
  - WebSocket (built into gateway)
  - CLI (built into cli module)
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ChannelMessage:
    """A message from any channel."""
    channel: str
    sender_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    reply_to: Optional[str] = None


class ChannelAdapter:
    """Base class for channel adapters."""
    channel_name: str = "base"

    async def send(self, recipient: str, message: str, **kwargs) -> bool:
        return False

    async def receive(self) -> list[ChannelMessage]:
        return []

    def is_available(self) -> bool:
        return False


class TelegramAdapter(ChannelAdapter):
    """
    Telegram Bot channel adapter.

    Uses python-telegram-bot for full Telegram Bot API support
    including inline keyboards, media, and webhooks.

    Usage:
        adapter = TelegramAdapter()
        await adapter.send(chat_id, "Hello from NEXUS!")
    """

    channel_name = "telegram"

    def __init__(self):
        self.settings = get_settings()
        self._bot = None

    def is_available(self) -> bool:
        return bool(self.settings.telegram_bot_token)

    async def _get_bot(self):
        """Lazily initialize the Telegram bot."""
        if self._bot is None and self.settings.telegram_bot_token:
            try:
                from telegram import Bot
                self._bot = Bot(token=self.settings.telegram_bot_token)
            except ImportError:
                logger.warning("python-telegram-bot not installed")
        return self._bot

    async def send(self, recipient: str, message: str, **kwargs) -> bool:
        """
        Send a message via Telegram.

        Args:
            recipient: Chat ID to send to.
            message: Message text.
            **kwargs: Additional Telegram parameters (parse_mode, etc.).

        Returns:
            True if message was sent successfully.
        """
        bot = await self._get_bot()
        if not bot:
            logger.error("Telegram bot not available")
            return False

        try:
            await bot.send_message(
                chat_id=recipient,
                text=message,
                parse_mode=kwargs.get("parse_mode", "Markdown"),
            )
            logger.info("Sent Telegram message to %s", recipient)
            return True
        except Exception as e:
            logger.error("Telegram send failed: %s", e)
            return False

    async def receive(self) -> list[ChannelMessage]:
        """Get recent messages (requires webhook or polling setup)."""
        # This would be implemented with polling or webhooks
        # For MVP, return empty list
        return []


class ChannelManager:
    """
    Central manager for all communication channels.

    Routes messages to/from the appropriate channel adapter.
    """

    def __init__(self):
        self._adapters: dict[str, ChannelAdapter] = {}
        self._register_default_adapters()

    def _register_default_adapters(self):
        self._adapters["telegram"] = TelegramAdapter()

    def get_adapter(self, channel: str) -> Optional[ChannelAdapter]:
        return self._adapters.get(channel)

    def get_available_channels(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "available": adapter.is_available(),
                "channel_name": adapter.channel_name,
            }
            for name, adapter in self._adapters.items()
        ]

    async def send(self, channel: str, recipient: str, message: str, **kwargs) -> bool:
        adapter = self._adapters.get(channel)
        if not adapter:
            logger.error("Unknown channel: %s", channel)
            return False
        if not adapter.is_available():
            logger.error("Channel %s is not available (check configuration)", channel)
            return False
        return await adapter.send(recipient, message, **kwargs)

    def register_adapter(self, name: str, adapter: ChannelAdapter):
        self._adapters[name] = adapter
