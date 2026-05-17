"""
Audit Hook — Records tool calls to the NEXUS audit trail.

Registers handlers on BEFORE_TOOL and AFTER_TOOL to capture
tool invocation details in the immutable audit log. This provides
a permanent record of every tool the agent invokes, including
parameters, execution time, and outcome.

The audit hook uses the nexus.security.audit.AuditLogger, which
writes to both the Python logging system and a JSONL file for
persistent storage and analysis.
"""

from __future__ import annotations

import logging
from typing import Any

from nexus.hooks.hooks import HookAction, HookContext, HookResult
from nexus.security.audit import AuditCategory, AuditLevel, AuditLogger

logger = logging.getLogger(__name__)


def create_audit_hook_handlers() -> dict[str, Any]:
    """Create audit hook handler functions.

    Returns:
        Dict with two keys:
            - 'before_tool': async handler for BEFORE_TOOL events
            - 'after_tool':  async handler for AFTER_TOOL events

    Usage:
        handlers = create_audit_hook_handlers()
        dispatcher.register(HookPoint.BEFORE_TOOL, handlers["before_tool"])
        dispatcher.register(HookPoint.AFTER_TOOL, handlers["after_tool"])
    """
    audit = AuditLogger()

    async def on_before_tool(ctx: HookContext) -> HookResult:
        """Log a tool call before it executes.

        Captures the tool name, parameters, and requesting plugin
        before the tool is invoked. Outcome is set to 'pending'
        since we don't know the result yet.
        """
        tool_name = ctx.data.get("tool", ctx.data.get("name", "unknown"))
        params = ctx.data.get("params", ctx.data.get("arguments", {}))
        session_id = ctx.data.get("session_id", "")

        audit.log(
            category=AuditCategory.TOOL_CALL,
            level=AuditLevel.INFO,
            action="call",
            actor=ctx.plugin_id,
            target=tool_name,
            details={
                "params": params,
                "phase": "before",
                "hook_point": ctx.hook_point.value,
            },
            outcome="pending",
            session_id=session_id,
        )

        logger.debug(
            "Audit: BEFORE_TOOL %s (plugin=%s)",
            tool_name,
            ctx.plugin_id,
        )

        return HookResult(
            action=HookAction.ALLOW,
            message=f"Audit logged BEFORE_TOOL for {tool_name}",
        )

    async def on_after_tool(ctx: HookContext) -> HookResult:
        """Log a tool call after it completes.

        Captures the outcome (success/failure), execution time, and
        any error message. Uses WARNING level for failed tool calls.
        """
        tool_name = ctx.data.get("tool", ctx.data.get("name", "unknown"))
        outcome = ctx.data.get("outcome", "success")
        execution_time = ctx.data.get("execution_time_ms", 0.0)
        error = ctx.data.get("error", "")
        session_id = ctx.data.get("session_id", "")

        log_outcome = "failure" if (outcome == "failure" or error) else "success"
        log_level = (
            AuditLevel.WARNING
            if log_outcome == "failure"
            else AuditLevel.INFO
        )

        audit.log(
            category=AuditCategory.TOOL_CALL,
            level=log_level,
            action="complete",
            actor=ctx.plugin_id,
            target=tool_name,
            details={
                "execution_time_ms": execution_time,
                "phase": "after",
                "error": error,
                "hook_point": ctx.hook_point.value,
            },
            outcome=log_outcome,
            session_id=session_id,
        )

        logger.debug(
            "Audit: AFTER_TOOL %s (outcome=%s, time=%.1fms)",
            tool_name,
            log_outcome,
            execution_time,
        )

        return HookResult(
            action=HookAction.ALLOW,
            message=f"Audit logged AFTER_TOOL for {tool_name} (outcome={log_outcome})",
        )

    return {
        "before_tool": on_before_tool,
        "after_tool": on_after_tool,
    }
