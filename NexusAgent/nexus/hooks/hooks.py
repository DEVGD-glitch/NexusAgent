"""
NEXUS Hooks — Core type definitions for the hooks system.

Defines HookPoint (lifecycle events), HookAction (what a hook can do),
HookContext (the event data), HookResult (the handler response),
and HookHandler (the async callable signature).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


class HookPoint(str, Enum):
    """All lifecycle points where hooks can be registered.

    Each constant represents a specific moment in the agent's execution
    lifecycle. Hooks registered at these points can observe, modify,
    or block the ongoing operation.
    """

    # ── Prompt lifecycle ────────────────────────────────────────────
    BEFORE_PROMPT = "before_prompt"
    AFTER_PROMPT = "after_prompt"

    # ── Tool lifecycle ──────────────────────────────────────────────
    BEFORE_TOOL = "before_tool"
    AFTER_TOOL = "after_tool"

    # ── LLM call lifecycle ──────────────────────────────────────────
    BEFORE_LLM_CALL = "before_llm_call"
    AFTER_LLM_CALL = "after_llm_call"

    # ── Git / commit lifecycle ──────────────────────────────────────
    BEFORE_COMMIT = "before_commit"
    AFTER_COMMIT = "after_commit"

    # ── File operation lifecycle ────────────────────────────────────
    BEFORE_FILE_DELETE = "before_file_delete"
    AFTER_FILE_DELETE = "after_file_delete"

    # ── Error and idle states ──────────────────────────────────────
    ON_ERROR = "on_error"
    ON_IDLE = "on_idle"

    # ── Task lifecycle ──────────────────────────────────────────────
    ON_TASK_START = "on_task_start"
    ON_TASK_COMPLETE = "on_task_complete"

    # ── Agent spawning lifecycle ────────────────────────────────────
    BEFORE_AGENT_SPAWN = "before_agent_spawn"
    AFTER_AGENT_SPAWN = "after_agent_spawn"

    # ── Plugin lifecycle ────────────────────────────────────────────
    ON_PLUGIN_LOAD = "on_plugin_load"
    ON_PLUGIN_UNLOAD = "on_plugin_unload"


class HookAction(str, Enum):
    """What action a hook handler can request.

    ALLOW — Continue normally (the default).
    BLOCK — Stop the operation (only effective when blocking=True).
    MODIFY — The handler has modified the data for downstream handlers.
    LOG — The handler only wants to log; no effect on execution.
    """

    ALLOW = "allow"
    BLOCK = "block"
    MODIFY = "modify"
    LOG = "log"


@dataclass
class HookContext:
    """Context passed to every hook handler.

    Attributes:
        hook_point: Which lifecycle point triggered this hook.
        plugin_id: Identifier of the plugin that registered this hook.
        data: Arbitrary payload data for the hook event.
        timestamp: Unix timestamp of when the event occurred.
    """

    hook_point: HookPoint
    plugin_id: str = "system"
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


@dataclass
class HookResult:
    """Result returned by a hook handler.

    Attributes:
        action: What action the handler requests (ALLOW, BLOCK, MODIFY, LOG).
        modified_data: If action=MODIFY, the updated data to pass downstream.
        message: Human-readable message describing the result.
        blocking: Hint that this result should stop execution if honored.
    """

    action: HookAction = HookAction.ALLOW
    modified_data: dict[str, Any] | None = None
    message: str = ""
    blocking: bool = False


# Async handler signature: takes a HookContext, returns a HookResult
HookHandler = Callable[[HookContext], Awaitable[HookResult]]
