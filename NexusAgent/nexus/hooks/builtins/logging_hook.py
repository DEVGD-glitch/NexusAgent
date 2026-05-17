"""
Logging Hook — Logs all hook events for debugging and observability.

Registers on ALL HookPoints with low priority (200) to provide
a universal event log without interfering with other handlers.

This is the lowest-priority built-in hook, so it runs after all
other handlers have had their say. It never blocks or modifies
data — it only observes and logs.

Output is at DEBUG level and includes the hook point, plugin ID,
and a truncated JSON summary of the event data. This is invaluable
for development, debugging, and post-mortem analysis.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from nexus.hooks.hooks import HookAction, HookContext, HookResult

logger = logging.getLogger(__name__)

# Maximum length of data summary in log output (characters)
_DATA_SUMMARY_MAX_LEN: int = 250


def create_logging_hook_handlers() -> Any:
    """Create a universal logging hook handler.

    Returns:
        An async handler function that logs every hook event at
        DEBUG level with a truncated JSON summary of the event data.

    Usage:
        handler = create_logging_hook_handlers()
        for hp in HookPoint:
            dispatcher.register(hp, handler, plugin_id="builtin_logging", priority=200)
    """

    async def on_any_event(ctx: HookContext) -> HookResult:
        """Log every hook event to the debug logger.

        This handler is registered on every HookPoint and writes
        a standardized log line with the event type, source plugin,
        and a compact data summary.

        It always returns ALLOW and never modifies data.
        """
        summary = _summarize_data(ctx.data, max_len=_DATA_SUMMARY_MAX_LEN)

        logger.debug(
            "[HOOK] %s | plugin=%s | data=%s",
            ctx.hook_point.value,
            ctx.plugin_id,
            summary,
        )
        return HookResult(
            action=HookAction.ALLOW,
            message="Event logged by universal logging hook",
        )

    return on_any_event


def _summarize_data(data: dict[str, Any], max_len: int = 250) -> str:
    """Summarize a data dict for logging, truncating if too large.

    Serializes the dict to JSON and truncates to max_len characters.
    If serialization fails (e.g., non-serializable values), falls back
    to a type-based description.

    Args:
        data: The dict to summarize.
        max_len: Maximum string length before truncation.

    Returns:
        A string representation safe for logging.
    """
    if not data:
        return "{}"

    try:
        dumped = json.dumps(data, ensure_ascii=False, default=str, sort_keys=True)
        if len(dumped) <= max_len:
            return dumped
        return dumped[:max_len] + "..."
    except (TypeError, ValueError, OverflowError):
        return f"<unserializable data: {type(data).__name__}>"
