"""
NEXUS Hook Dispatcher — Manages registration and dispatch of hook handlers.

Provides a thread-safe singleton HookDispatcher that routes events to
registered handlers in priority order, supporting BLOCK short-circuit
for blocking dispatches and MODIFY for data transformation.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from nexus.hooks.hooks import HookAction, HookContext, HookHandler, HookPoint, HookResult

logger = logging.getLogger(__name__)


@dataclass
class _HandlerEntry:
    """Internal handler registration entry with priority ordering."""

    priority: int
    handler: HookHandler
    plugin_id: str = "system"


class HookDispatcher:
    """Thread-safe dispatcher for hook handlers.

    Handlers are executed in priority order (ascending). When blocking=True,
    a BLOCK action stops the handler chain immediately. MODIFY actions
    propagate modified data to subsequent handlers in the chain.

    This is a singleton — use get_dispatcher() to obtain the instance.

    Thread safety:
        All mutation of the handler registry is protected by a threading.Lock.
        Dispatch reads handler lists under the lock but executes handlers
        outside it to avoid holding the lock across await points.
    """

    def __init__(self) -> None:
        self._handlers: dict[HookPoint, list[_HandlerEntry]] = {}
        self._lock = threading.Lock()
        self._dispatch_count: int = 0

    # ── Registration ────────────────────────────────────────────────

    def register(
        self,
        hook_point: HookPoint,
        handler: HookHandler,
        plugin_id: str = "system",
        priority: int = 100,
    ) -> None:
        """Register a hook handler for a given lifecycle point.

        Args:
            hook_point: The lifecycle point to hook into.
            handler: The async callable to invoke with HookContext.
            plugin_id: Identifier for the registering plugin or system.
            priority: Lower values run first (default 100).

        Multiple handlers from the same plugin can be registered at the
        same hook point. The list is kept sorted by priority for fast dispatch.
        """
        entry = _HandlerEntry(priority=priority, handler=handler, plugin_id=plugin_id)

        with self._lock:
            if hook_point not in self._handlers:
                self._handlers[hook_point] = []
            self._handlers[hook_point].append(entry)
            # Maintain priority order for O(n) dispatch
            self._handlers[hook_point].sort(key=lambda h: h.priority)

        logger.debug(
            "Hook registered: %s → %s (priority=%d, plugin=%s)",
            hook_point.value,
            getattr(handler, "__name__", repr(handler)),
            priority,
            plugin_id,
        )

    def unregister(self, hook_point: HookPoint, plugin_id: str) -> int:
        """Remove all handlers for a plugin at a given hook point.

        Args:
            hook_point: The lifecycle point to unregister from.
            plugin_id: The plugin identifier to remove.

        Returns:
            Number of handlers removed (0 if none found).
        """
        with self._lock:
            if hook_point not in self._handlers:
                return 0
            before = len(self._handlers[hook_point])
            self._handlers[hook_point] = [
                h for h in self._handlers[hook_point] if h.plugin_id != plugin_id
            ]
            removed = before - len(self._handlers[hook_point])

        if removed:
            logger.debug(
                "Hook unregistered: %s → plugin=%s (%d removed)",
                hook_point.value,
                plugin_id,
                removed,
            )
        return removed

    # ── Dispatch ────────────────────────────────────────────────────

    async def dispatch(
        self,
        hook_point: HookPoint,
        context: HookContext,
        blocking: bool = False,
    ) -> list[HookResult]:
        """Dispatch an event to all registered handlers for the given hook point.

        The dispatch flow:
        1. Snapshot the handler list under the lock.
        2. Execute handlers sequentially in priority order.
        3. If a handler returns BLOCK and blocking=True, stop the chain.
        4. If a handler returns MODIFY, propagate modified_data downstream.

        Args:
            hook_point: The lifecycle point being triggered.
            context: The HookContext with event data. The context.data may
                be modified by MODIFY actions as data flows through the chain.
            blocking: If True, a BLOCK result from any handler stops the
                chain immediately and no further handlers are invoked.

        Returns:
            List of HookResults from all executed handlers, in order.
            If no handlers are registered, returns an empty list.
        """
        handlers = self._get_handlers_safe(hook_point)
        if not handlers:
            return []

        self._dispatch_count += 1

        results: list[HookResult] = []
        current_data: dict[str, Any] = (
            dict(context.data) if context.data is not None else {}
        )
        ts = context.timestamp or time.time()

        for entry in handlers:
            # Build a fresh context with the current (potentially modified) data
            hook_ctx = HookContext(
                hook_point=hook_point,
                plugin_id=entry.plugin_id,
                data=current_data,
                timestamp=ts,
            )

            try:
                result = await entry.handler(hook_ctx)
            except Exception as exc:
                logger.exception(
                    "Hook handler '%s' (plugin=%s) raised an error: %s",
                    getattr(entry.handler, "__name__", "?"),
                    entry.plugin_id,
                    exc,
                )
                result = HookResult(
                    action=HookAction.ALLOW,
                    message=f"Handler error: {exc}",
                )

            results.append(result)

            # BLOCK + blocking=True → short-circuit the chain
            if result.action == HookAction.BLOCK and blocking:
                logger.info(
                    "Hook chain blocked by '%s' (plugin=%s): %s",
                    getattr(entry.handler, "__name__", "?"),
                    entry.plugin_id,
                    result.message,
                )
                break

            # MODIFY → propagate updated data to the next handler
            if result.action == HookAction.MODIFY and result.modified_data is not None:
                current_data = result.modified_data

        return results

    # ── Introspection ───────────────────────────────────────────────

    def get_handlers(self, hook_point: HookPoint) -> list[tuple[int, str, str]]:
        """Get registered handlers for a hook point.

        Returns:
            List of (priority, plugin_id, handler_name) tuples,
            ordered by priority ascending.
        """
        with self._lock:
            entries = list(self._handlers.get(hook_point, []))
        return [
            (
                e.priority,
                e.plugin_id,
                getattr(e.handler, "__name__", "?"),
            )
            for e in entries
        ]

    def clear(self) -> None:
        """Remove all registered handlers from every hook point.

        This is called during engine shutdown to ensure a clean state.
        """
        with self._lock:
            self._handlers.clear()
        logger.info("All hook handlers cleared")

    def _get_handlers_safe(self, hook_point: HookPoint) -> list[_HandlerEntry]:
        """Thread-safe snapshot of handlers for a hook point.

        Returns a shallow copy of the list so the caller can iterate
        without holding the lock.
        """
        with self._lock:
            return list(self._handlers.get(hook_point, []))

    @property
    def total_dispatches(self) -> int:
        """Total number of dispatch calls since startup."""
        return self._dispatch_count

    def get_status(self) -> dict[str, Any]:
        """Get dispatcher status for monitoring and health checks.

        Returns:
            Dict with registered_hook_points (count), hook_points (breakdown
            by hook point with handler counts), and total_dispatches.
        """
        with self._lock:
            hook_points = {
                hp.value: len(handlers)
                for hp, handlers in self._handlers.items()
            }
        return {
            "registered_hook_points": len(self._handlers),
            "hook_points": hook_points,
            "total_dispatches": self._dispatch_count,
        }


# ═══════════════════════════════════════════════════════════════════
# Singleton accessor
# ═══════════════════════════════════════════════════════════════════

_dispatcher: HookDispatcher | None = None


def get_dispatcher() -> HookDispatcher:
    """Get the global HookDispatcher singleton.

    Thread-safe: the singleton is created on first call and reused.
    Use this in application code to access the shared dispatcher instance.
    """
    global _dispatcher  # noqa: PLW0603
    if _dispatcher is None:
        _dispatcher = HookDispatcher()
    return _dispatcher
