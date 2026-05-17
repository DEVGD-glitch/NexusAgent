"""
NEXUS Plugin Sandbox — Security enforcement layer for plugins.

Every action a plugin takes passes through the sandbox which:
  - Validates that the plugin has declared the required :class:`PluginPermission`
  - Prevents directory-traversal attacks via path validation
  - Enforces per-plugin rate limits with a token bucket algorithm
  - Logs every action to the audit trail
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

from nexus.plugins.exceptions import PluginPermissionDenied
from nexus.plugins.manifest import PluginManifest, PluginPermission

logger = logging.getLogger(__name__)


class TokenBucket:
    """Thread-safe token bucket rate limiter.

    Tokens are refilled continuously at a fixed *refill_rate* per second
    up to *capacity*. Each call to :meth:`consume` draws the requested
    number of tokens and returns ``True`` if they were available.

    Usage::

        bucket = TokenBucket(capacity=60, refill_rate=1.0)
        if bucket.consume():
            ...  # action allowed
    """

    def __init__(self, capacity: int = 60, refill_rate: float = 1.0) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._tokens: float = float(capacity)
        self._last_refill: float = time.monotonic()
        self._lock: threading.Lock = threading.Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time since last refill."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate)
            self._last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume *tokens* from the bucket.

        Returns:
            ``True`` if the tokens were consumed, ``False`` if the bucket
            did not have enough tokens (caller should deny the action).
        """
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    @property
    def available(self) -> float:
        """Number of tokens currently available (read-only snapshot)."""
        with self._lock:
            self._refill()
            return self._tokens


class PluginSandbox:
    """Security sandbox that enforces plugin permissions, path safety, and rate limits.

    Every plugin action should be gated through this sandbox *before*
    execution. The sandbox is shared across all plugins and referenced
    by the :class:`PluginEngine`.
    """

    def __init__(self) -> None:
        self._rate_limiters: dict[str, TokenBucket] = {}
        self._rl_lock: threading.Lock = threading.Lock()

    # ── Permission Checks ───────────────────────────────────────────

    def check_permission(
        self,
        manifest: PluginManifest,
        permission: PluginPermission,
        action: str = "",
    ) -> bool:
        """Verify that a plugin has declared the required permission.

        Args:
            manifest: The plugin's manifest (checking ``manifest.permissions``).
            permission: The :class:`PluginPermission` required.
            action: Human-readable description of the action being checked.

        Returns:
            ``True`` if the permission is granted.

        Raises:
            PluginPermissionDenied: If the plugin does not have the permission.
        """
        # ADMIN permission grants everything
        if PluginPermission.ADMIN in manifest.permissions:
            return True

        if permission not in manifest.permissions:
            raise PluginPermissionDenied(
                plugin_id=manifest.id,
                permission=permission.value,
                action=action,
            )
        return True

    # ── Path Validation ─────────────────────────────────────────────

    def validate_path(self, path: str, allowed_bases: list[str]) -> bool:
        """Validate that a path is contained within one of the *allowed_bases*.

        Prevents directory-traversal attacks by resolving both the target
        path and each allowed base to their real paths and verifying that
        the target is a descendant.

        Args:
            path: The filesystem path to validate.
            allowed_bases: List of directory paths that are allowed.

        Returns:
            ``True`` if *path* is inside one of the *allowed_bases*.
        """
        try:
            resolved = Path(path).resolve()
        except (OSError, RuntimeError) as exc:
            logger.warning("Path resolution failed for '%s': %s", path, exc)
            return False

        for base in allowed_bases:
            try:
                base_resolved = Path(base).resolve()
                resolved.relative_to(base_resolved)
                return True
            except ValueError:
                continue
            except (OSError, RuntimeError) as exc:
                logger.warning("Base path resolution failed for '%s': %s", base, exc)
                continue

        logger.warning(
            "Path validation failed for '%s' — not in allowed bases: %s",
            path, allowed_bases,
        )
        return False

    # ── Rate Limiting ───────────────────────────────────────────────

    def get_rate_limiter(
        self,
        plugin_id: str,
        capacity: int = 60,
        refill_rate: float = 1.0,
    ) -> TokenBucket:
        """Get or create a token bucket for a plugin.

        Args:
            plugin_id: Unique plugin identifier.
            capacity: Maximum token bucket capacity.
            refill_rate: Tokens added per second.

        Returns:
            A :class:`TokenBucket` instance for the plugin.
        """
        with self._rl_lock:
            if plugin_id not in self._rate_limiters:
                self._rate_limiters[plugin_id] = TokenBucket(
                    capacity=capacity,
                    refill_rate=refill_rate,
                )
            return self._rate_limiters[plugin_id]

    def check_rate_limit(self, plugin_id: str, tokens: int = 1) -> bool:
        """Check if a plugin is within its rate limit.

        Consumes *tokens* from the plugin's token bucket.

        Args:
            plugin_id: Unique plugin identifier.
            tokens: Number of tokens to consume (default: 1).

        Returns:
            ``True`` if the action is allowed, ``False`` if rate limited.
        """
        limiter = self.get_rate_limiter(plugin_id)
        allowed = limiter.consume(tokens)
        if not allowed:
            logger.warning("Rate limit exceeded for plugin: %s", plugin_id)
        return allowed

    # ── Audit Logging ───────────────────────────────────────────────

    def log_action(
        self,
        manifest: PluginManifest,
        action: str,
        target: str = "",
        result: str = "success",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record a plugin action in the audit log.

        Args:
            manifest: The plugin's manifest (used for identity).
            action: Action name (e.g. ``initialize``, ``tool_call``, ``hook_trigger``).
            target: Optional target identifier (e.g. file path, tool name).
            result: Outcome — ``success``, ``denied``, or ``error``.
            details: Optional structured context.
        """
        entry = {
            "plugin_id": manifest.id,
            "plugin_version": manifest.version,
            "action": action,
            "target": target,
            "result": result,
            "details": details or {},
        }

        if result == "denied":
            logger.warning(
                "PLUGIN SANDBOX [DENIED]  %(plugin_id)s %(action)s %(target)s",
                entry,
            )
        elif result == "error":
            logger.error(
                "PLUGIN SANDBOX [ERROR]   %(plugin_id)s %(action)s %(target)s",
                entry,
            )
        else:
            logger.info(
                "PLUGIN SANDBOX [SUCCESS] %(plugin_id)s %(action)s %(target)s",
                entry,
            )

    def set_rate_limits(
        self,
        plugin_id: str,
        capacity: int,
        refill_rate: float,
    ) -> None:
        """Set or update rate limits for a plugin, resetting its token bucket.

        Args:
            plugin_id: Unique plugin identifier.
            capacity: Maximum tokens.
            refill_rate: Tokens per second.
        """
        with self._rl_lock:
            self._rate_limiters[plugin_id] = TokenBucket(
                capacity=capacity,
                refill_rate=refill_rate,
            )
            logger.debug("Rate limits updated for plugin %s: cap=%d rate=%.1f/s", plugin_id, capacity, refill_rate)
