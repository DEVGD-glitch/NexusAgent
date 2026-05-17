"""
NEXUS Hooks System — Plugin-based lifecycle hooks for agent actions.

Provides a hook engine, dispatcher, and built-in hooks for audit,
permissions, and logging. External plugins can register handlers
to observe or modify agent behavior at key lifecycle points.

Usage:
    from nexus.hooks import HookEngine, HookPoint

    engine = HookEngine()
    await engine.initialize()
    results = await engine.dispatch(HookPoint.BEFORE_TOOL, {"tool": "read_file"})

    # Check if any handler blocked
    blocked = any(r.action == HookAction.BLOCK for r in results)

Module-level convenience wrappers:
    register_hook(hook_point, handler, plugin_id, priority)
    await dispatch_hook(hook_point, context, data, blocking)
"""

from __future__ import annotations

import logging
import time
from typing import Any

from nexus.hooks.hooks import HookAction, HookContext, HookPoint, HookResult
from nexus.hooks.hooks import HookHandler
from nexus.hooks.dispatcher import HookDispatcher, get_dispatcher
from nexus.hooks.engine import HookEngine

logger = logging.getLogger(__name__)


# ── Module-level convenience functions ──────────────────────────────


def register_hook(
    hook_point: HookPoint,
    handler: HookHandler,
    plugin_id: str = "system",
    priority: int = 100,
) -> None:
    """Register a hook handler via the global dispatcher.

    This is a module-level convenience wrapper around
    ``get_dispatcher().register(...)``.

    Args:
        hook_point: The lifecycle point to hook into.
        handler: The async callable to invoke with HookContext.
        plugin_id: Identifier for the registering plugin (default "system").
        priority: Lower values run first (default 100).

    Example:
        from nexus.hooks import register_hook, HookPoint, HookResult, HookAction

        async def my_handler(ctx):
            print(f"Tool called: {ctx.data.get('tool')}")
            return HookResult(action=HookAction.ALLOW)

        register_hook(HookPoint.BEFORE_TOOL, my_handler, plugin_id="my_plugin")
    """
    get_dispatcher().register(hook_point, handler, plugin_id, priority)


async def dispatch_hook(
    hook_point: HookPoint,
    context: HookContext | None = None,
    data: dict[str, Any] | None = None,
    blocking: bool = False,
) -> list[HookResult]:
    """Dispatch a hook event via the global dispatcher.

    This is a module-level convenience wrapper around
    ``get_dispatcher().dispatch(...)``.

    Args:
        hook_point: The lifecycle point being triggered.
        context: A pre-built HookContext. If not provided, one is
            constructed from ``data`` with the current timestamp.
        data: Payload data (used only if ``context`` is not provided).
        blocking: If True, a BLOCK result stops the handler chain.

    Returns:
        List of HookResults from all executed handlers.

    Example:
        from nexus.hooks import dispatch_hook, HookPoint

        results = await dispatch_hook(
            HookPoint.BEFORE_TOOL,
            data={"tool": "execute_code"},
        )
    """
    if context is None:
        context = HookContext(
            hook_point=hook_point,
            data=data or {},
            timestamp=time.time(),
        )
    return await get_dispatcher().dispatch(hook_point, context, blocking=blocking)


__all__ = [
    # Core classes
    "HookEngine",
    "HookPoint",
    "HookResult",
    "HookAction",
    "HookContext",
    "HookHandler",
    # Dispatcher
    "HookDispatcher",
    "get_dispatcher",
    # Convenience functions
    "register_hook",
    "dispatch_hook",
]
