"""Workflow Actions — Executable steps in a workflow."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """Types of workflow actions."""
    TOOL_CALL = "tool_call"
    LLM_CALL = "llm_call"
    AGENT_SPAWN = "agent_spawn"
    NOTIFY = "notify"
    DELAY = "delay"
    SET_VARIABLE = "set_variable"
    HTTP_REQUEST = "http_request"
    RUN_WORKFLOW = "run_workflow"
    CONDITIONAL = "conditional"
    PARALLEL = "parallel"


@dataclass
class ActionResult:
    """Result of executing an action."""
    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


class Action(ABC):
    """Base class for workflow actions."""

    def __init__(self, action_id: str, action_type: ActionType, params: dict[str, Any] | None = None) -> None:
        self.action_id = action_id
        self.action_type = action_type
        self.params = params or {}

    @abstractmethod
    async def execute(self, context: dict[str, Any]) -> ActionResult: ...

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "params": self.params,
        }


class ToolCallAction(Action):
    """Calls an MCP tool or local tool."""

    def __init__(self, action_id: str, tool_name: str, tool_params: dict[str, Any] | None = None) -> None:
        super().__init__(action_id, ActionType.TOOL_CALL, {"tool_name": tool_name, "tool_params": tool_params or {}})
        self.tool_name = tool_name
        self.tool_params = tool_params or {}

    async def execute(self, context: dict[str, Any]) -> ActionResult:
        start = time.monotonic()
        try:
            from nexus.tools import ToolRegistry
            registry = ToolRegistry()
            merged_params = {**self.tool_params, **context}
            result = await registry.execute(self.tool_name, merged_params)
            duration = (time.monotonic() - start) * 1000
            return ActionResult(success=True, output=result, duration_ms=duration)
        except Exception as exc:
            duration = (time.monotonic() - start) * 1000
            return ActionResult(success=False, error=str(exc), duration_ms=duration)


class LLMCallAction(Action):
    """Calls the LLM with a prompt."""

    def __init__(self, action_id: str, prompt_template: str, model: str | None = None) -> None:
        super().__init__(action_id, ActionType.LLM_CALL, {"prompt_template": prompt_template, "model": model})
        self.prompt_template = prompt_template
        self.model = model

    async def execute(self, context: dict[str, Any]) -> ActionResult:
        start = time.monotonic()
        try:
            prompt = self.prompt_template.format(**context)
            from nexus.llm.router import LLMRouter, TaskComplexity
            router = LLMRouter()
            response = await router.complete(
                messages=[{"role": "user", "content": prompt}],
                task_complexity=TaskComplexity.SIMPLE,
            )
            duration = (time.monotonic() - start) * 1000
            return ActionResult(success=True, output=response.content, duration_ms=duration)
        except Exception as exc:
            duration = (time.monotonic() - start) * 1000
            return ActionResult(success=False, error=str(exc), duration_ms=duration)


class AgentSpawnAction(Action):
    """Spawns a sub-agent."""

    def __init__(self, action_id: str, agent_type: str, task: str) -> None:
        super().__init__(action_id, ActionType.AGENT_SPAWN, {"agent_type": agent_type, "task": task})
        self.agent_type = agent_type
        self.task = task

    async def execute(self, context: dict[str, Any]) -> ActionResult:
        start = time.monotonic()
        try:
            from nexus.core.registry import AgentRegistry
            from nexus.agents import AGENT_TYPE_MAP
            registry = AgentRegistry()
            task = self.task.format(**context)
            agent_cls = AGENT_TYPE_MAP.get(self.agent_type)
            if not agent_cls:
                return ActionResult(success=False, error=f"Unknown agent type: {self.agent_type}")
            instance = await registry.create_instance(agent_type=self.agent_type)
            result = await instance.run(task)
            duration = (time.monotonic() - start) * 1000
            return ActionResult(success=True, output=result, duration_ms=duration)
        except Exception as exc:
            duration = (time.monotonic() - start) * 1000
            return ActionResult(success=False, error=str(exc), duration_ms=duration)


class NotifyAction(Action):
    """Sends a notification."""

    def __init__(self, action_id: str, message: str, channel: str = "default") -> None:
        super().__init__(action_id, ActionType.NOTIFY, {"message": message, "channel": channel})
        self.message = message
        self.channel = channel

    async def execute(self, context: dict[str, Any]) -> ActionResult:
        message = self.message.format(**context)
        logger.info("Notification [%s]: %s", self.channel, message)
        return ActionResult(success=True, output={"message": message, "channel": self.channel})


class DelayAction(Action):
    """Waits for a specified duration."""

    def __init__(self, action_id: str, seconds: float) -> None:
        super().__init__(action_id, ActionType.DELAY, {"seconds": seconds})
        self.seconds = seconds

    async def execute(self, context: dict[str, Any]) -> ActionResult:
        await asyncio.sleep(self.seconds)
        return ActionResult(success=True, output=f"Waited {self.seconds}s")


class SetVariableAction(Action):
    """Sets a variable in the workflow context."""

    def __init__(self, action_id: str, key: str, value: Any) -> None:
        super().__init__(action_id, ActionType.SET_VARIABLE, {"key": key, "value": value})
        self.key = key
        self.value = value

    async def execute(self, context: dict[str, Any]) -> ActionResult:
        context[self.key] = self.value
        return ActionResult(success=True, output={self.key: self.value})


class HTTPRequestAction(Action):
    """Makes an HTTP request."""

    def __init__(self, action_id: str, url: str, method: str = "GET", headers: dict | None = None, body: dict | None = None) -> None:
        super().__init__(action_id, ActionType.HTTP_REQUEST, {"url": url, "method": method, "headers": headers, "body": body})
        self.url = url
        self.method = method
        self.headers = headers or {}
        self.body = body

    async def execute(self, context: dict[str, Any]) -> ActionResult:
        start = time.monotonic()
        try:
            import httpx
            url = self.url.format(**context)
            async with httpx.AsyncClient(timeout=30) as client:
                if self.method.upper() == "GET":
                    resp = await client.get(url, headers=self.headers)
                elif self.method.upper() == "POST":
                    resp = await client.post(url, headers=self.headers, json=self.body)
                else:
                    resp = await client.request(self.method, url, headers=self.headers, json=self.body)
            duration = (time.monotonic() - start) * 1000
            return ActionResult(
                success=resp.status_code < 400,
                output={"status": resp.status_code, "body": resp.text[:2000]},
                duration_ms=duration,
            )
        except Exception as exc:
            duration = (time.monotonic() - start) * 1000
            return ActionResult(success=False, error=str(exc), duration_ms=duration)


class ParallelAction(Action):
    """Executes multiple actions in parallel."""

    def __init__(self, action_id: str, actions: list[Action]) -> None:
        super().__init__(action_id, ActionType.PARALLEL)
        self.actions = actions

    async def execute(self, context: dict[str, Any]) -> ActionResult:
        start = time.monotonic()
        results = await asyncio.gather(
            *[a.execute(context) for a in self.actions],
            return_exceptions=True,
        )
        duration = (time.monotonic() - start) * 1000
        outputs = []
        for r in results:
            if isinstance(r, Exception):
                outputs.append(ActionResult(success=False, error=str(r)))
            else:
                outputs.append(r)
        all_ok = all(r.success for r in outputs if isinstance(r, ActionResult))
        return ActionResult(
            success=all_ok,
            output=[r.to_dict() for r in outputs if isinstance(r, ActionResult)],
            duration_ms=duration,
        )


class ActionFactory:
    """Creates action instances from configuration dicts."""

    @staticmethod
    def create(config: dict[str, Any]) -> Action:
        atype = config.get("type", "tool_call")
        aid = config.get("id", f"action_{int(time.time())}")
        params = config.get("params", {})

        if atype == "tool_call":
            return ToolCallAction(aid, config.get("tool_name", ""), params)
        elif atype == "llm_call":
            return LLMCallAction(aid, config.get("prompt_template", ""), config.get("model"))
        elif atype == "agent_spawn":
            return AgentSpawnAction(aid, config.get("agent_type", ""), config.get("task", ""))
        elif atype == "notify":
            return NotifyAction(aid, config.get("message", ""), config.get("channel", "default"))
        elif atype == "delay":
            return DelayAction(aid, config.get("seconds", 1))
        elif atype == "set_variable":
            return SetVariableAction(aid, config.get("key", ""), config.get("value"))
        elif atype == "http_request":
            return HTTPRequestAction(aid, config.get("url", ""), config.get("method", "GET"), config.get("headers"), config.get("body"))
        elif atype == "parallel":
            sub_actions = [ActionFactory.create(c) for c in config.get("actions", [])]
            return ParallelAction(aid, sub_actions)
        else:
            logger.warning("Unknown action type: %s, defaulting to tool_call", atype)
            return ToolCallAction(aid, atype, params)
