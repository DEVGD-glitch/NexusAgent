"""
L1 Working Memory — Context compression and management.

The working memory manages the active context window for LLM inference.
Inspired by GenericAgent's context density principle, it maintains a
compressed representation that stays under the token budget (default 30K tokens)
where competitors burn 200K-1M tokens.

Key features:
  - Token budget enforcement via tiktoken
  - Automatic compression when threshold is exceeded
  - Priority-based eviction (least important messages removed first)
  - Support for message roles (system, user, assistant, tool)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)

try:
    import tiktoken
    _ENCODER = tiktoken.encoding_for_model("gpt-4o")
except Exception:
    _ENCODER = None


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class WorkingMessage:
    """A single message in the working memory."""
    role: MessageRole
    content: str
    timestamp: float = field(default_factory=time.time)
    priority: float = 1.0  # Higher = more important, less likely to be evicted
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def token_count(self) -> int:
        """Estimate token count for this message."""
        if _ENCODER is not None:
            return len(_ENCODER.encode(self.content))
        return len(self.content) // 4  # Fallback: ~4 chars per token


@dataclass
class WorkingMemory:
    """
    L1 Working Memory — manages the active context window.

    Maintains a list of messages that are compressed automatically
    when they exceed the token budget. The compression strategy
    prioritizes keeping high-priority and recent messages.

    Usage:
        wm = WorkingMemory(max_tokens=30000)
        wm.add(MessageRole.USER, "What is the capital of France?")
        wm.add(MessageRole.ASSISTANT, "The capital of France is Paris.")
        messages = wm.get_messages()  # Returns list of dicts for LLM
    """

    max_tokens: Optional[int] = None
    compression_threshold: float = 0.8
    messages: list[WorkingMessage] = field(default_factory=list)
    system_prompt: Optional[str] = None

    def __post_init__(self):
        if self.max_tokens is None:
            settings = get_settings()
            self.max_tokens = settings.memory_max_working_tokens
            self.compression_threshold = settings.memory_compression_threshold

    @property
    def total_tokens(self) -> int:
        """Current total token count of all messages."""
        return sum(msg.token_count for msg in self.messages)

    @property
    def utilization(self) -> float:
        """Current utilization as a fraction of max_tokens."""
        if self.max_tokens == 0:
            return 0.0
        return self.total_tokens / self.max_tokens

    def add(
        self,
        role: MessageRole,
        content: str,
        priority: float = 1.0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Add a message to working memory.

        Automatically triggers compression if the token budget is exceeded.

        Args:
            role: Message role (system, user, assistant, tool).
            content: Message text content.
            priority: Importance score (higher = less likely to be evicted).
            metadata: Optional metadata dict.
        """
        msg = WorkingMessage(
            role=role,
            content=content,
            priority=priority,
            metadata=metadata or {},
        )
        self.messages.append(msg)

        if self.total_tokens > self.max_tokens:
            self._compress()

    def get_messages(self, include_system: bool = True) -> list[dict[str, str]]:
        """
        Return messages as a list of dicts suitable for LLM API calls.

        Format: [{"role": "user", "content": "..."}, ...]

        Args:
            include_system: Whether to include the system prompt as first message.
        """
        result = []
        if include_system and self.system_prompt:
            result.append({"role": "system", "content": self.system_prompt})
        for msg in self.messages:
            result.append({"role": msg.role.value, "content": msg.content})
        return result

    def clear(self) -> None:
        """Clear all messages from working memory."""
        self.messages.clear()

    def _compress(self) -> None:
        """
        Compress working memory by evicting low-priority messages.

        Strategy:
        1. Sort messages by priority (ascending) then by recency (oldest first)
        2. Remove messages until we're under the compression threshold
        3. Never remove system messages or messages with priority >= 2.0
        4. Add a single brief summary instead of one summary per evicted message
        """
        target_tokens = int(self.max_tokens * self.compression_threshold)
        current = self.total_tokens

        if current <= target_tokens:
            return

        # Sort by priority (ascending), then by age (oldest first)
        indexed = list(enumerate(self.messages))
        evictable = [
            (i, msg) for i, msg in indexed
            if msg.role != MessageRole.SYSTEM and msg.priority < 2.0
        ]
        evictable.sort(key=lambda x: (x[1].priority, x[1].timestamp))

        evicted_indices = []
        evicted_count = 0

        for idx, msg in evictable:
            if current <= target_tokens:
                break
            current -= msg.token_count
            evicted_indices.append(idx)
            evicted_count += 1

        if evicted_indices:
            for idx in sorted(evicted_indices, reverse=True):
                self.messages.pop(idx)

            # Add a single brief summary message (not one per evicted msg!)
            summary = f"[Context compressed: {evicted_count} older messages removed to save space]"
            summary_msg = WorkingMessage(
                role=MessageRole.SYSTEM,
                content=summary,
                priority=1.5,
                metadata={"compressed": True, "original_count": evicted_count},
            )
            self.messages.insert(0, summary_msg)

            # If still over budget after one pass, remove the summary and repeat
            if self.total_tokens > self.max_tokens:
                self.messages = [m for m in self.messages if not m.metadata.get("compressed")]
                # Aggressive: keep only the last N messages that fit, with safety limit
                max_evictions = max(1, len(self.messages) - 1)  # Never empty the list
                for _ in range(max_evictions):
                    if self.total_tokens <= self.max_tokens or len(self.messages) <= 2:
                        break
                    # Check if first message is oversized — if so, skip it
                    if self.messages and self.messages[0].token_count > self.max_tokens:
                        logger.warning("First message exceeds max_tokens (%d > %d) — skipping aggressive eviction",
                                       self.messages[0].token_count, self.max_tokens)
                        break
                    self.messages.pop(0)

            logger.info(
                "Compressed working memory: evicted %d messages, now %d tokens",
                evicted_count, self.total_tokens,
            )

    def set_system_prompt(self, prompt: str) -> None:
        """Set the system prompt (always first in context)."""
        self.system_prompt = prompt

    def get_stats(self) -> dict[str, Any]:
        """Return statistics about working memory state."""
        return {
            "message_count": len(self.messages),
            "total_tokens": self.total_tokens,
            "max_tokens": self.max_tokens,
            "utilization": round(self.utilization, 3),
            "needs_compression": self.utilization > self.compression_threshold,
            "roles": {role.value: sum(1 for m in self.messages if m.role == role) for role in MessageRole},
        }
