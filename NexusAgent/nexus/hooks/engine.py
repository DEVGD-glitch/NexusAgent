"""
NEXUS Hook Engine — High-level orchestration for the hooks system.

Manages the full lifecycle: initialization, built-in hook registration,
dispatch delegation, and clean shutdown. Provides the primary public API
for hook usage throughout the NEXUS agent.

Usage:
    from nexus.hooks import HookEngine, HookPoint

    engine = HookEngine()
    await engine.initialize()

    # Dispatch an event
    results = await engine.dispatch(
        HookPoint.BEFORE_TOOL,
        {"tool": "read_file", "path": "/tmp/data.txt"},
    )

    # Check if any handler blocked the operation
    blocked = any(r.action == HookAction.BLOCK for r in results)

    await engine.shutdown()
"""

from __future__ import annotations

import logging
import time
from typing import Any

from nexus.hooks.dispatcher import HookDispatcher, get_dispatcher
from nexus.hooks.hooks import HookContext, HookHandler, HookPoint, HookResult

logger = logging.getLogger(__name__)


class HookEngine:
    """High-level hook engine that manages the hook lifecycle.

    Wraps the HookDispatcher with built-in hook registration and
    provides a cleaner API for the rest of the agent to consume.

    The engine is safe to initialize multiple times — subsequent
    calls to initialize() are no-ops. Call shutdown() to release
    all registered handlers.

    Thread safety:
        The underlying dispatcher is thread-safe for registration.
        Dispatch is async-safe and runs handlers sequentially.
    """

    def __init__(self, dispatcher: HookDispatcher | None = None) -> None:
        self._dispatcher = dispatcher or get_dispatcher()
        self._initialized: bool = False
        self._builtins_registered: bool = False

    # ── Lifecycle ───────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Initialize the hook engine and register all built-in hooks.

        Idempotent — safe to call multiple times. Subsequent calls are
        no-ops once the engine is already initialized.

        Built-in hooks registered:
            - audit_hook: Records tool calls to the audit trail.
            - permission_hook: Enforces security policies.
            - logging_hook: Logs all events at DEBUG level.
        """
        if self._initialized:
            logger.debug("HookEngine already initialized")
            return

        self._initialized = True
        await self._register_builtins()
        logger.info(
            "HookEngine initialized — %d hook points active",
            len(self._dispatcher.get_status().get("hook_points", {})),
        )

    async def shutdown(self) -> None:
        """Shut down the hook engine and clear all registered handlers.

        After shutdown, the engine can be re-initialized by calling
        initialize() again. This is safe to call even if the engine
        was never initialized.
        """
        if not self._initialized:
            logger.debug("HookEngine shutdown called but not initialized")
            return
        self._dispatcher.clear()
        self._initialized = False
        self._builtins_registered = False
        logger.info("HookEngine shut down — all handlers cleared")

    # ── Dispatch ────────────────────────────────────────────────────

    async def dispatch(
        self,
        hook_point: HookPoint,
        data: dict[str, Any] | None = None,
        plugin_id: str = "system",
        blocking: bool = False,
    ) -> list[HookResult]:
        """Dispatch a hook event to all registered handlers.

        This is the primary dispatch method. It constructs a HookContext
        with the current timestamp and delegates to the underlying dispatcher.

        Args:
            hook_point: The lifecycle point being triggered.
            data: Arbitrary payload data for the event. Handlers can
                read from and (via MODIFY action) write to this dict.
            plugin_id: Identifier for the plugin or system component
                that triggered this event.
            blocking: If True, any handler that returns BLOCK will
                stop the handler chain immediately.

        Returns:
            List of HookResults from all executed handlers, in priority order.
            Returns an empty list if no handlers are registered for this point.
        """
        context = HookContext(
            hook_point=hook_point,
            plugin_id=plugin_id,
            data=data or {},
            timestamp=time.time(),
        )

        return await self._dispatcher.dispatch(hook_point, context, blocking=blocking)

    async def dispatch_with_context(
        self,
        context: HookContext,
        blocking: bool = False,
    ) -> list[HookResult]:
        """Dispatch using an already-constructed HookContext.

        Useful when the caller needs fine-grained control over context
        fields such as timestamp, plugin_id, or data structure.

        Args:
            context: A fully populated HookContext.
            blocking: If True, BLOCK stops the handler chain.

        Returns:
            List of HookResults from all executed handlers.
        """
        return await self._dispatcher.dispatch(
            context.hook_point,
            context,
            blocking=blocking,
        )

    # ── Registration ────────────────────────────────────────────────

    def register_handler(
        self,
        hook_point: HookPoint,
        handler: HookHandler,
        plugin_id: str = "system",
        priority: int = 100,
    ) -> None:
        """Register a hook handler.

        This is a convenience wrapper around the dispatcher's register
        method that plugins can use to hook into lifecycle events.

        Args:
            hook_point: The lifecycle point to hook into.
            handler: The async callable to invoke. Must accept a HookContext
                and return a HookResult (or awaitable thereof).
            plugin_id: Identifier for the registering plugin.
            priority: Lower values run first (default 100). Built-in hooks
                use 30 (permission), 50 (audit), and 200 (logging).
        """
        self._dispatcher.register(hook_point, handler, plugin_id, priority)

    def unregister_plugin(
        self,
        hook_point: HookPoint,
        plugin_id: str,
    ) -> int:
        """Remove all handlers for a plugin at a given hook point.

        Args:
            hook_point: The lifecycle point to unregister from.
            plugin_id: The plugin identifier to remove.

        Returns:
            Number of handlers removed (0 if none found).
        """
        return self._dispatcher.unregister(hook_point, plugin_id)

    # ── Built-in hook registration ──────────────────────────────────

    async def _register_builtins(self) -> None:
        """Register all built-in hook implementations with the dispatcher.

        Built-in hooks are registered with specific priorities to ensure
        correct ordering:
            30 — permission_hook (run first — gate the action)
            50 — audit_hook (run after permissions — record the action)
            200 — logging_hook (run last — universal logging)

        If any built-in fails to load, an error is logged but the engine
        continues initialization with the remaining hooks.
        """
        if self._builtins_registered:
            return
        self._builtins_registered = True

        # ── Import built-in hook factories ──────────────────────────
        try:
            from nexus.hooks.builtins.audit_hook import (
                create_audit_hook_handlers,
            )
            from nexus.hooks.builtins.permission_hook import (
                create_permission_hook_handlers,
            )
            from nexus.hooks.builtins.logging_hook import (
                create_logging_hook_handlers,
            )
        except ImportError as exc:
            logger.warning(
                "Could not import built-in hooks (some may be missing): %s",
                exc,
            )
            return

        # ── Audit hook: record tool calls ───────────────────────────
        try:
            audit_handlers = create_audit_hook_handlers()
            if "before_tool" in audit_handlers:
                self._dispatcher.register(
                    HookPoint.BEFORE_TOOL,
                    audit_handlers["before_tool"],
                    plugin_id="builtin_audit",
                    priority=50,
                )
            if "after_tool" in audit_handlers:
                self._dispatcher.register(
                    HookPoint.AFTER_TOOL,
                    audit_handlers["after_tool"],
                    plugin_id="builtin_audit",
                    priority=50,
                )
            logger.debug("Built-in audit hook registered")
        except Exception as exc:
            logger.error("Failed to register audit hook: %s", exc)

        # ── Permission hook: enforce security policies ──────────────
        try:
            perm_handlers = create_permission_hook_handlers()
            permission_bindings = {
                "before_tool": HookPoint.BEFORE_TOOL,
                "before_file_delete": HookPoint.BEFORE_FILE_DELETE,
                "before_agent_spawn": HookPoint.BEFORE_AGENT_SPAWN,
            }
            for key, hp in permission_bindings.items():
                if key in perm_handlers:
                    self._dispatcher.register(
                        hp,
                        perm_handlers[key],
                        plugin_id="builtin_permission",
                        priority=30,
                    )
            logger.debug("Built-in permission hook registered")
        except Exception as exc:
            logger.error("Failed to register permission hook: %s", exc)

        # ── Logging hook: universal event logger (low priority) ─────
        try:
            logging_handler = create_logging_hook_handlers()
            for hp in HookPoint:
                self._dispatcher.register(
                    hp,
                    logging_handler,
                    plugin_id="builtin_logging",
                    priority=200,
                )
            logger.debug(
                "Built-in logging hook registered on %d hook points",
                len(HookPoint),
            )
        except Exception as exc:
            logger.error("Failed to register logging hook: %s", exc)

        logger.info("All built-in hooks registered successfully")

    # ── Status ──────────────────────────────────────────────────────

    @property
    def is_initialized(self) -> bool:
        """Whether the engine has been initialized."""
        return self._initialized

    def get_status(self) -> dict[str, Any]:
        """Get engine status for monitoring and health checks.

        Returns:
            Dict with initialization state and dispatcher status.
        """
        dispatcher_status = self._dispatcher.get_status()
        return {
            "initialized": self._initialized,
            "builtins_registered": self._builtins_registered,
            **dispatcher_status,
        }
