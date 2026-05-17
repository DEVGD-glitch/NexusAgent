"""
Permission Hook — Enforces security policies at key lifecycle points.

Registers handlers on BEFORE_TOOL, BEFORE_FILE_DELETE, and
BEFORE_AGENT_SPAWN to evaluate whether the requested operation
should be allowed or blocked.

The permission hook uses the nexus.permissions module when available,
and falls back to built-in rules for common security-sensitive patterns
(e.g., blocking deletion of configuration and environment files).
"""

from __future__ import annotations

import logging
from typing import Any

from nexus.hooks.hooks import HookAction, HookContext, HookResult

logger = logging.getLogger(__name__)

# ── Protected paths that cannot be deleted via hook lifecycle ─────
# These patterns are checked against file paths in before_file_delete.
PROTECTED_PATH_PATTERNS: list[str] = [
    ".env",
    ".env.local",
    ".env.production",
    "nexus_data",
    "config.json",
    "config.yaml",
    "config.yml",
    "credentials",
    "secrets",
    ".git",
    "node_modules",
]


def create_permission_hook_handlers() -> dict[str, Any]:
    """Create permission check hook handler functions.

    Returns:
        Dict with three keys:
            - 'before_tool':        async handler for BEFORE_TOOL events
            - 'before_file_delete': async handler for BEFORE_FILE_DELETE events
            - 'before_agent_spawn': async handler for BEFORE_AGENT_SPAWN events

    Usage:
        handlers = create_permission_hook_handlers()
        dispatcher.register(HookPoint.BEFORE_TOOL, handlers["before_tool"])
    """

    async def on_before_tool(ctx: HookContext) -> HookResult:
        """Check permission before a tool executes.

        Evaluates whether the requesting actor has permission to use
        the specified tool. Currently allows all tools by default;
        real permission checks can be integrated with nexus.permissions.

        Expected context data:
            - tool / name: The tool identifier.
            - user_id / actor: The requesting user or agent.
        """
        tool_name = ctx.data.get("tool", ctx.data.get("name", "unknown"))
        user_id = ctx.data.get("user_id", ctx.data.get("actor", "system"))

        # Future: integrate with nexus.permissions module
        # if not await permission_check(user_id, tool_name):
        #     return HookResult(action=HookAction.BLOCK, message="...", blocking=True)

        logger.debug(
            "Permission: tool=%s actor=%s → ALLOW",
            tool_name,
            user_id,
        )

        return HookResult(
            action=HookAction.ALLOW,
            message=f"Permission granted for tool '{tool_name}'",
        )

    async def on_before_file_delete(ctx: HookContext) -> HookResult:
        """Check permission before a file is deleted.

        Blocks deletion of protected system files and directories.
        Protects against accidental or malicious destruction of
        configuration, credentials, and repository data.

        Expected context data:
            - file_path / path: The path of the file to delete.
            - user_id / actor: The requesting user or agent.
        """
        file_path = ctx.data.get("file_path", ctx.data.get("path", ""))
        user_id = ctx.data.get("user_id", ctx.data.get("actor", "system"))

        # Check against protected path patterns
        for pattern in PROTECTED_PATH_PATTERNS:
            if pattern.lower() in file_path.lower():
                logger.warning(
                    "Permission BLOCK: delete %s by %s (matched pattern: %s)",
                    file_path,
                    user_id,
                    pattern,
                )
                return HookResult(
                    action=HookAction.BLOCK,
                    message=(
                        f"Deletion of protected path '{file_path}' is not allowed. "
                        f"Matched protection pattern: '{pattern}'."
                    ),
                    blocking=True,
                )

        logger.debug(
            "Permission: delete %s by %s → ALLOW",
            file_path,
            user_id,
        )

        return HookResult(
            action=HookAction.ALLOW,
            message=f"Permission granted for file delete '{file_path}'",
        )

    async def on_before_agent_spawn(ctx: HookContext) -> HookResult:
        """Check permission before spawning a child agent.

        Evaluates whether the current context allows spawning a new
        agent with the requested task. Currently allows all spawns
        by default.

        Expected context data:
            - agent_type / type: The type of agent to spawn.
            - task: The task description for the child agent.
        """
        agent_type = ctx.data.get("agent_type", ctx.data.get("type", "unknown"))
        task = ctx.data.get("task", "")

        # Future: limit concurrent agents, check resource availability
        logger.debug(
            "Permission: spawn %s (task=%.80s) → ALLOW",
            agent_type,
            task,
        )

        return HookResult(
            action=HookAction.ALLOW,
            message=f"Permission granted to spawn agent '{agent_type}'",
        )

    return {
        "before_tool": on_before_tool,
        "before_file_delete": on_before_file_delete,
        "before_agent_spawn": on_before_agent_spawn,
    }
