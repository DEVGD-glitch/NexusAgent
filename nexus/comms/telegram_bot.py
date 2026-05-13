"""
NEXUS Telegram Bot — Telegram bot interface for mobile access.

Supports:
  - Message handling (commands, text, callbacks)
  - Rich message formatting (Markdown, HTML)
  - Command registration (/start, /help, /status, /chat, /memory)
  - Conversation management with session persistence
  - Integration with the gateway for agent access
  - httpx-based Telegram Bot API calls
  - Support for long-running tasks with status updates
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

import httpx

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """Types of Telegram messages."""
    TEXT = "text"
    COMMAND = "command"
    CALLBACK = "callback"
    PHOTO = "photo"
    DOCUMENT = "document"


class ParseMode(str, Enum):
    """Telegram message parse modes."""
    MARKDOWN = "Markdown"
    MARKDOWN_V2 = "MarkdownV2"
    HTML = "HTML"


@dataclass
class TelegramMessage:
    """Incoming Telegram message."""
    message_id: int
    chat_id: int
    text: str = ""
    message_type: MessageType = MessageType.TEXT
    from_user: dict[str, Any] = field(default_factory=dict)
    date: int = 0
    command: str = ""
    command_args: str = ""
    callback_data: str = ""

    @classmethod
    def from_update(cls, update: dict[str, Any]) -> Optional[TelegramMessage]:
        """Create a TelegramMessage from a Telegram API update."""
        # Handle regular message
        msg = update.get("message") or update.get("edited_message")
        if msg:
            text = msg.get("text", "")
            message_type = MessageType.TEXT
            command = ""
            command_args = ""

            # Check if it's a command
            entities = msg.get("entities", [])
            for entity in entities:
                if entity.get("type") == "bot_command":
                    message_type = MessageType.COMMAND
                    offset = entity.get("offset", 0)
                    length = entity.get("length", 0)
                    command = text[offset:offset + length].lstrip("/")
                    command_args = text[offset + length:].strip()
                    break

            return cls(
                message_id=msg.get("message_id", 0),
                chat_id=msg.get("chat", {}).get("id", 0),
                text=text,
                message_type=message_type,
                from_user=msg.get("from", {}),
                date=msg.get("date", 0),
                command=command,
                command_args=command_args,
            )

        # Handle callback query
        callback = update.get("callback_query")
        if callback:
            msg = callback.get("message", {})
            return cls(
                message_id=msg.get("message_id", 0),
                chat_id=msg.get("chat", {}).get("id", 0),
                text=callback.get("data", ""),
                message_type=MessageType.CALLBACK,
                from_user=callback.get("from", {}),
                date=msg.get("date", 0),
                callback_data=callback.get("data", ""),
            )

        return None


@dataclass
class ConversationSession:
    """Manages a conversation session with a Telegram user."""
    chat_id: int
    user_id: int
    username: str = ""
    created_at: float = 0.0
    last_active: float = 0.0
    message_count: int = 0
    context: list[dict[str, str]] = field(default_factory=list)
    is_processing: bool = False

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()
        self.last_active = time.time()

    def add_message(self, role: str, content: str):
        """Add a message to the conversation context."""
        self.context.append({"role": role, "content": content})
        self.message_count += 1
        self.last_active = time.time()

        # Keep context manageable (last 20 messages)
        if len(self.context) > 20:
            self.context = self.context[-20:]

    def to_dict(self) -> dict[str, Any]:
        return {
            "chat_id": self.chat_id,
            "user_id": self.user_id,
            "username": self.username,
            "message_count": self.message_count,
            "is_processing": self.is_processing,
        }


class TelegramBot:
    """
    Telegram bot interface for NEXUS mobile access.

    Provides a polling-based Telegram bot that processes commands
    and messages, maintains conversation sessions, and integrates
    with the NEXUS gateway for agent access.

    Usage:
        bot = TelegramBot()
        await bot.start()

    Commands:
        /start  - Start the bot
        /help   - Show available commands
        /status - Show NEXUS status
        /chat   - Start/continue a conversation
        /memory - Search NEXUS memory
    """

    TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"

    def __init__(
        self,
        gateway_url: Optional[str] = None,
        allowed_users: Optional[list[int]] = None,
    ):
        """
        Initialize the Telegram bot.

        Args:
            gateway_url: URL of the NEXUS gateway API.
            allowed_users: Optional list of Telegram user IDs allowed to use the bot.
                           If None, all users are allowed.
        """
        self.settings = get_settings()
        self._token = self.settings.telegram_bot_token
        self._gateway_url = gateway_url or f"http://localhost:{self.settings.nexus_port}"
        self._allowed_users = allowed_users
        self._sessions: dict[int, ConversationSession] = {}
        self._running = False
        self._poll_task: Optional[asyncio.Task] = None
        self._last_update_id = 0
        self._command_handlers: dict[str, Callable] = {}
        self._message_handlers: list[Callable] = []
        self._router = None

        # Register default commands
        self._register_default_commands()

    def _get_router(self):
        """Lazily initialize the LLM router."""
        if self._router is None:
            from nexus.llm.router import LLMRouter
            self._router = LLMRouter()
        return self._router

    def is_available(self) -> bool:
        """Check if the Telegram bot is properly configured."""
        return bool(self._token)

    # ── Bot Lifecycle ────────────────────────────────────────────────

    async def start(self, poll_interval: float = 1.0):
        """
        Start the Telegram bot polling loop.

        Args:
            poll_interval: Seconds between polling requests.
        """
        if not self._token:
            logger.error("Telegram bot token not configured. Set TELEGRAM_BOT_TOKEN in .env")
            return

        if self._running:
            logger.warning("Telegram bot already running")
            return

        self._running = True

        # Verify bot token
        me = await self._api_call("getMe")
        if not me:
            logger.error("Failed to verify Telegram bot token")
            self._running = False
            return

        bot_name = me.get("username", "unknown")
        logger.info("Telegram bot started: @%s", bot_name)

        # Set bot commands
        await self._set_commands()

        # Start polling
        self._poll_task = asyncio.create_task(self._poll_loop(poll_interval))

    async def stop(self):
        """Stop the Telegram bot."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None
        logger.info("Telegram bot stopped")

    async def _poll_loop(self, interval: float):
        """Main polling loop for receiving updates."""
        while self._running:
            try:
                updates = await self._get_updates()

                for update in updates:
                    try:
                        await self._process_update(update)
                    except Exception as e:
                        logger.error("Error processing update: %s", e)

                # Small delay even if no updates
                if not updates:
                    await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Polling error: %s", e)
                await asyncio.sleep(5)

    # ── API Calls ────────────────────────────────────────────────────

    async def _api_call(
        self,
        method: str,
        params: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Make a Telegram Bot API call.

        Args:
            method: API method name.
            params: Method parameters.

        Returns:
            Result dict from the API, or None on failure.
        """
        if not self._token:
            return None

        url = self.TELEGRAM_API_BASE.format(token=self._token, method=method)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if params:
                    # Handle file-like params separately
                    response = await client.post(url, json=params)
                else:
                    response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        return data.get("result")
                    else:
                        logger.warning(
                            "Telegram API error: %s", data.get("description", "unknown")
                        )
                else:
                    logger.warning(
                        "Telegram API HTTP %d: %s",
                        response.status_code,
                        response.text[:200],
                    )
        except Exception as e:
            logger.error("Telegram API call failed (%s): %s", method, e)

        return None

    async def _get_updates(self) -> list[dict[str, Any]]:
        """Get new updates from Telegram using long polling."""
        params: dict[str, Any] = {
            "timeout": 10,
            "offset": self._last_update_id + 1,
            "allowed_updates": ["message", "callback_query"],
        }

        result = await self._api_call("getUpdates", params)
        if result:
            updates = result if isinstance(result, list) else []
            if updates:
                self._last_update_id = max(u.get("update_id", 0) for u in updates)
            return updates
        return []

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: ParseMode = ParseMode.MARKDOWN,
        reply_markup: Optional[dict[str, Any]] = None,
        reply_to: Optional[int] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Send a message to a Telegram chat.

        Args:
            chat_id: Target chat ID.
            text: Message text.
            parse_mode: Message formatting mode.
            reply_markup: Optional inline keyboard or reply markup.
            reply_to: Optional message ID to reply to.

        Returns:
            API result dict or None.
        """
        # Truncate long messages
        max_length = 4096
        if len(text) > max_length:
            text = text[:max_length - 3] + "..."

        params: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode.value,
        }

        if reply_markup:
            params["reply_markup"] = json.dumps(reply_markup)

        if reply_to:
            params["reply_to_message_id"] = reply_to

        return await self._api_call("sendMessage", params)

    async def _set_commands(self):
        """Set the bot's command list in Telegram."""
        commands = [
            {"command": "start", "description": "Start NEXUS bot"},
            {"command": "help", "description": "Show available commands"},
            {"command": "status", "description": "Show NEXUS status"},
            {"command": "chat", "description": "Chat with NEXUS"},
            {"command": "memory", "description": "Search NEXUS memory"},
        ]
        await self._api_call("setMyCommands", {"commands": commands})

    # ── Update Processing ────────────────────────────────────────────

    async def _process_update(self, update: dict[str, Any]):
        """Process a single Telegram update."""
        message = TelegramMessage.from_update(update)
        if not message:
            return

        # Check user authorization
        if self._allowed_users and message.from_user.get("id") not in self._allowed_users:
            await self.send_message(
                message.chat_id,
                "⛔ You are not authorized to use this bot.",
            )
            return

        # Route to appropriate handler
        if message.message_type == MessageType.COMMAND:
            await self._handle_command(message)
        elif message.message_type == MessageType.CALLBACK:
            await self._handle_callback(message)
        else:
            await self._handle_message(message)

    async def _handle_command(self, message: TelegramMessage):
        """Handle a command message."""
        command = message.command.lower()
        handler = self._command_handlers.get(command)

        if handler:
            try:
                await handler(message)
            except Exception as e:
                logger.error("Command handler error for /%s: %s", command, e)
                await self.send_message(
                    message.chat_id,
                    f"❌ Error processing command: {str(e)[:200]}",
                )
        else:
            await self.send_message(
                message.chat_id,
                f"Unknown command: /{command}\nUse /help to see available commands.",
            )

    async def _handle_message(self, message: TelegramMessage):
        """Handle a regular text message."""
        for handler in self._message_handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error("Message handler error: %s", e)

        # Default: treat as a chat message
        if not self._message_handlers:
            await self._cmd_chat(message)

    async def _handle_callback(self, message: TelegramMessage):
        """Handle a callback query (inline button press)."""
        data = message.callback_data

        # Acknowledge the callback
        await self._api_call("answerCallbackQuery", {
            "callback_query_id": str(message.message_id),
        })

        # Process based on callback data
        if data.startswith("memory:"):
            query = data[7:]
            await self._search_and_send(message.chat_id, query)

    # ── Command Handlers ─────────────────────────────────────────────

    def _register_default_commands(self):
        """Register the default bot commands."""
        self._command_handlers = {
            "start": self._cmd_start,
            "help": self._cmd_help,
            "status": self._cmd_status,
            "chat": self._cmd_chat,
            "memory": self._cmd_memory,
        }

    async def _cmd_start(self, message: TelegramMessage):
        """Handle /start command."""
        user_name = message.from_user.get("first_name", "there")
        welcome = (
            f"👋 Hello, {user_name}! I'm **NEXUS**, your AI assistant.\n\n"
            "I can help you with:\n"
            "• 💬 Chat with me about anything\n"
            "• 🔍 Search my knowledge base\n"
            "• 📊 Check system status\n\n"
            "Use /help to see all commands."
        )
        await self.send_message(message.chat_id, welcome)

    async def _cmd_help(self, message: TelegramMessage):
        """Handle /help command."""
        help_text = (
            "🤖 **NEXUS Bot Commands**\n\n"
            "/start — Start the bot\n"
            "/help — Show this help message\n"
            "/status — Show NEXUS system status\n"
            "/chat _message_ — Chat with NEXUS\n"
            "/memory _query_ — Search NEXUS memory\n\n"
            "💡 You can also just type a message to chat!"
        )
        await self.send_message(message.chat_id, help_text)

    async def _cmd_status(self, message: TelegramMessage):
        """Handle /status command."""
        status_lines = ["📊 **NEXUS Status**\n"]

        # Check gateway
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._gateway_url}/health")
                if response.status_code == 200:
                    data = response.json()
                    status_lines.append(f"✅ Gateway: online ({data.get('environment', 'unknown')})")
                    status_lines.append(f"⏱ Uptime: {data.get('uptime_seconds', 0):.0f}s")
                else:
                    status_lines.append("❌ Gateway: offline")
        except Exception:
            status_lines.append("❌ Gateway: unreachable")

        # Check LLM providers
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._gateway_url}/providers")
                if response.status_code == 200:
                    providers = response.json()
                    available = [
                        name for name, info in providers.items()
                        if info.get("available")
                    ]
                    status_lines.append(f"🧠 Providers: {', '.join(available) or 'none'}")
        except Exception:
            status_lines.append("🧠 Providers: unknown")

        # Session info
        status_lines.append(f"💬 Active sessions: {len(self._sessions)}")

        await self.send_message(message.chat_id, "\n".join(status_lines))

    async def _cmd_chat(self, message: TelegramMessage):
        """Handle /chat command or free-text message."""
        text = message.command_args or message.text

        if not text.strip():
            await self.send_message(
                message.chat_id,
                "💬 Send me a message and I'll respond!\n"
                "Example: `/chat What is machine learning?`",
            )
            return

        # Get or create session
        session = self._get_or_create_session(message)

        if session.is_processing:
            await self.send_message(
                message.chat_id,
                "⏳ I'm still processing your previous message. Please wait...",
            )
            return

        session.is_processing = True
        session.add_message("user", text)

        try:
            # Send "typing" indicator
            await self._api_call("sendChatAction", {
                "chat_id": message.chat_id,
                "action": "typing",
            })

            # Use LLM router for response
            router = self._get_router()
            from nexus.llm.router import TaskComplexity

            response = await router.complete(
                messages=session.context,
                task_complexity=TaskComplexity.MEDIUM,
                temperature=0.7,
                max_tokens=2048,
            )

            reply = response.content
            session.add_message("assistant", reply)

            # Escape Markdown special characters for Telegram
            safe_reply = self._escape_markdown(reply)
            await self.send_message(message.chat_id, safe_reply)

        except Exception as e:
            logger.error("Chat error: %s", e)
            await self.send_message(
                message.chat_id,
                f"❌ Sorry, I encountered an error. Please try again.",
            )
        finally:
            session.is_processing = False

    async def _cmd_memory(self, message: TelegramMessage):
        """Handle /memory command for searching NEXUS memory."""
        query = message.command_args

        if not query.strip():
            await self.send_message(
                message.chat_id,
                "🔍 Search NEXUS memory:\n"
                "Example: `/memory Python best practices`",
            )
            return

        await self._search_and_send(message.chat_id, query)

    async def _search_and_send(self, chat_id: int, query: str):
        """Search NEXUS memory and send results."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self._gateway_url}/memory/stats",
                )

            # Try to search via the memory service directly
            from nexus.memory.chroma_service import NexusMemoryService

            service = NexusMemoryService()
            results = await service.search(
                query=query,
                namespace="knowledge",
                top_k=3,
            )

            docs = results.get("documents", [[]])[0]
            distances = results.get("distances", [[]])[0]

            if not docs:
                await self.send_message(
                    chat_id,
                    f"🔍 No results found for: *{query}*",
                )
                return

            response_lines = [f"🔍 Results for: *{query}*\n"]
            for i, (doc, dist) in enumerate(zip(docs, distances), 1):
                relevance = f"{1 - dist:.0%}" if dist else "N/A"
                response_lines.append(f"{i}. [{relevance}] {doc[:300]}...")
                response_lines.append("")

            await self.send_message(chat_id, "\n".join(response_lines))

        except Exception as e:
            logger.error("Memory search error: %s", e)
            await self.send_message(
                chat_id,
                f"❌ Memory search failed: {str(e)[:200]}",
            )

    # ── Session Management ───────────────────────────────────────────

    def _get_or_create_session(self, message: TelegramMessage) -> ConversationSession:
        """Get or create a conversation session for the user."""
        chat_id = message.chat_id
        if chat_id not in self._sessions:
            self._sessions[chat_id] = ConversationSession(
                chat_id=chat_id,
                user_id=message.from_user.get("id", 0),
                username=message.from_user.get("username", ""),
            )
        return self._sessions[chat_id]

    def get_active_sessions(self) -> list[dict[str, Any]]:
        """Get all active conversation sessions."""
        return [session.to_dict() for session in self._sessions.values()]

    def clear_session(self, chat_id: int) -> bool:
        """Clear a conversation session."""
        if chat_id in self._sessions:
            del self._sessions[chat_id]
            return True
        return False

    # ── Utility ──────────────────────────────────────────────────────

    @staticmethod
    def _escape_markdown(text: str) -> str:
        """
        Escape Markdown special characters for Telegram MarkdownV1.

        Characters to escape: _ * [ `
        """
        # For MarkdownV1, we only need to escape problematic patterns
        # Replace problematic sequences that would break Telegram's parser
        text = re.sub(r"([_*\[`])", r"\\\1", text)
        return text

    async def send_long_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: ParseMode = ParseMode.MARKDOWN,
        chunk_size: int = 4000,
    ):
        """
        Send a long message by splitting it into chunks.

        Telegram has a 4096 character limit per message.

        Args:
            chat_id: Target chat ID.
            text: Message text (may be very long).
            parse_mode: Message formatting mode.
            chunk_size: Size of each chunk (must be < 4096).
        """
        if len(text) <= chunk_size:
            await self.send_message(chat_id, text, parse_mode)
            return

        # Split on paragraph boundaries
        paragraphs = text.split("\n\n")
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 > chunk_size:
                if current_chunk:
                    await self.send_message(chat_id, current_chunk.strip(), parse_mode)
                current_chunk = para
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para

        if current_chunk.strip():
            await self.send_message(chat_id, current_chunk.strip(), parse_mode)

    async def notify(self, chat_id: int, title: str, message: str):
        """
        Send a notification-style message.

        Args:
            chat_id: Target chat ID.
            title: Notification title.
            message: Notification body.
        """
        text = f"🔔 *{title}*\n\n{message}"
        await self.send_message(chat_id, text)
