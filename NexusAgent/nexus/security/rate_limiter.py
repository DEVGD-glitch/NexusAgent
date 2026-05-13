"""
NEXUS Rate Limiter — Token bucket rate limiting for API and tool calls.

Implements per-user and global rate limiting using a sliding window
algorithm. Prevents abuse and ensures fair resource allocation.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from nexus.core.config import get_settings
from nexus.core.exceptions import RateLimitExceededError

logger = logging.getLogger(__name__)


@dataclass
class RateLimitWindow:
    """A sliding window for rate tracking."""
    timestamps: list[float] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit."""
    name: str
    max_requests: int
    window_seconds: int
    burst: int = 0  # Allow burst over the limit temporarily


class RateLimiter:
    """
    Sliding window rate limiter for NEXUS.

    Supports:
      - Per-user rate limiting
      - Global rate limiting
      - Per-tool rate limiting
      - Configurable burst allowance
      - Automatic cleanup of expired windows

    Usage:
        limiter = RateLimiter()
        limiter.check("user_123", "api_call")  # Raises if rate exceeded
        limiter.check("user_123", "api_call")  # Returns True if allowed
    """

    def __init__(self):
        settings = get_settings()
        self._windows: dict[str, RateLimitWindow] = defaultdict(RateLimitWindow)
        self._configs: dict[str, RateLimitConfig] = {}

        # Default rate limits
        self._configs["api_call"] = RateLimitConfig(
            name="api_call",
            max_requests=settings.rate_limit_rpm,
            window_seconds=60,
            burst=settings.rate_limit_burst,
        )
        self._configs["tool_call"] = RateLimitConfig(
            name="tool_call",
            max_requests=120,
            window_seconds=60,
            burst=20,
        )
        self._configs["code_execution"] = RateLimitConfig(
            name="code_execution",
            max_requests=30,
            window_seconds=60,
            burst=5,
        )
        self._configs["llm_call"] = RateLimitConfig(
            name="llm_call",
            max_requests=60,
            window_seconds=60,
            burst=10,
        )

    def _get_key(self, identifier: str, action: str) -> str:
        """Generate a unique key for the rate limit window."""
        return f"{identifier}:{action}"

    def _cleanup_old_entries(self, window: RateLimitWindow, window_seconds: int):
        """Remove timestamps outside the sliding window."""
        cutoff = time.monotonic() - window_seconds
        with window.lock:
            window.timestamps = [ts for ts in window.timestamps if ts > cutoff]

    def check(
        self,
        identifier: str,
        action: str = "api_call",
        tokens: int = 1,
    ) -> bool:
        """
        Check if a request is allowed under the rate limit.

        Args:
            identifier: User or session identifier.
            action: Action type (api_call, tool_call, etc.).
            tokens: Number of tokens to consume (default: 1).

        Returns:
            True if the request is allowed.

        Raises:
            RateLimitExceededError: If the rate limit is exceeded.
        """
        config = self._configs.get(action)
        if not config:
            # No rate limit configured for this action
            return True

        key = self._get_key(identifier, action)
        window = self._windows[key]

        self._cleanup_old_entries(window, config.window_seconds)

        with window.lock:
            current_count = len(window.timestamps)
            effective_limit = config.max_requests + config.burst

            if current_count + tokens > effective_limit:
                logger.warning(
                    "Rate limit exceeded: %s/%s (%d/%d in %ds window)",
                    identifier, action, current_count, effective_limit,
                    config.window_seconds,
                )
                raise RateLimitExceededError(
                    limit=config.max_requests,
                    window=f"{config.window_seconds}s",
                )

            # Record the request
            now = time.monotonic()
            for _ in range(tokens):
                window.timestamps.append(now)

        return True

    def is_allowed(
        self,
        identifier: str,
        action: str = "api_call",
    ) -> bool:
        """
        Check if a request would be allowed without consuming tokens.

        Returns:
            True if the request would be allowed, False otherwise.
        """
        config = self._configs.get(action)
        if not config:
            return True

        key = self._get_key(identifier, action)
        window = self._windows[key]

        self._cleanup_old_entries(window, config.window_seconds)

        with window.lock:
            current_count = len(window.timestamps)
            effective_limit = config.max_requests + config.burst
            return current_count < effective_limit

    def get_remaining(
        self,
        identifier: str,
        action: str = "api_call",
    ) -> dict[str, Any]:
        """Get remaining requests for a user/action combination."""
        config = self._configs.get(action)
        if not config:
            return {"remaining": float("inf"), "limit": 0, "window_seconds": 0}

        key = self._get_key(identifier, action)
        window = self._windows[key]

        self._cleanup_old_entries(window, config.window_seconds)

        with window.lock:
            current_count = len(window.timestamps)
            return {
                "remaining": max(0, config.max_requests - current_count),
                "limit": config.max_requests,
                "burst": config.burst,
                "current_count": current_count,
                "window_seconds": config.window_seconds,
            }

    def add_limit(self, action: str, max_requests: int, window_seconds: int, burst: int = 0):
        """Add or update a rate limit configuration."""
        self._configs[action] = RateLimitConfig(
            name=action,
            max_requests=max_requests,
            window_seconds=window_seconds,
            burst=burst,
        )

    def reset(self, identifier: Optional[str] = None, action: Optional[str] = None):
        """Reset rate limit windows."""
        if identifier and action:
            key = self._get_key(identifier, action)
            if key in self._windows:
                del self._windows[key]
        elif identifier:
            keys_to_delete = [k for k in self._windows if k.startswith(f"{identifier}:")]
            for key in keys_to_delete:
                del self._windows[key]
        else:
            self._windows.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics."""
        return {
            "configured_limits": {k: {"max": v.max_requests, "window_s": v.window_seconds, "burst": v.burst}
                                  for k, v in self._configs.items()},
            "active_windows": len(self._windows),
        }
