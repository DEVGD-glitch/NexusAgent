"""
NEXUS A2A Protocol — Agent-to-Agent communication and task delegation.

Implements the A2A (Agent-to-Agent) protocol for inter-agent
communication, task delegation, and service discovery.

Components:
  - A2AServer: HTTP server exposing agent capabilities
  - A2AClient: Client for discovering and calling remote agents
  - Task delegation: Assign tasks to other agents
  - Service discovery: Find agents by capability
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import httpx

from nexus.core.config import get_settings
from nexus.core.exceptions import NexusError

logger = logging.getLogger(__name__)


class TaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class MessageType(str, Enum):
    """A2A message types for agent communication."""
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    PROGRESS_UPDATE = "progress_update"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


@dataclass
class TaskDelegate:
    """
    Delegate a task to a remote agent with progress tracking.

    Created by the delegating agent. Can be polled for status
    or used with a callback for streaming progress reports.

    Usage:
        delegate = TaskDelegate(
            task_id="task_123",
            target_agent="http://remote:8080",
            callback=on_progress,
        )
        result = await delegate.wait_for_completion()
    """
    task_id: str
    target_agent: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    state: TaskState = TaskState.SUBMITTED
    callback: Optional[Any] = None  # Callable[[ProgressReport], None]
    result: Optional[str] = None
    error: Optional[str] = None

    async def wait_for_completion(
        self,
        poll_interval: float = 1.0,
        timeout: float = 300.0,
    ) -> str:
        """
        Poll the remote agent until the task completes or times out.

        Args:
            poll_interval: Seconds between status polls.
            timeout: Maximum seconds to wait.

        Returns:
            The task result string.
        """
        from nexus.core.a2a import A2AProtocol, ProgressReport
        import time

        protocol = A2AProtocol()
        start = time.monotonic()

        while self.state in (TaskState.SUBMITTED, TaskState.WORKING):
            if time.monotonic() - start > timeout:
                self.state = TaskState.FAILED
                self.error = "Timeout waiting for remote task"
                raise TimeoutError(f"Task {self.task_id} timed out after {timeout}s")

            status = await protocol.get_task_status(self.target_agent, self.task_id)
            if status:
                self.state = TaskState(status.get("state", "working"))
                progress = ProgressReport(
                    task_id=self.task_id,
                    progress=status.get("progress", 0.0),
                    message=status.get("message", ""),
                    intermediate_result=status.get("result"),
                )
                if self.callback:
                    self.callback(progress)

                if self.state == TaskState.COMPLETED:
                    self.result = status.get("result", "")
                    return self.result
                elif self.state == TaskState.FAILED:
                    self.error = status.get("error", "Unknown error")
                    return ""

            await asyncio.sleep(poll_interval)

        return self.result or ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "target_agent": self.target_agent,
            "state": self.state.value,
            "created_at": self.created_at,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class ProgressReport:
    """
    Streaming progress report from a remote agent.

    Emitted during task execution to track progress in real-time.
    Can include intermediate results for preview/streaming.
    """
    task_id: str
    progress: float = 0.0  # 0.0 - 1.0
    message: str = ""
    intermediate_result: Optional[dict[str, Any]] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    state: TaskState = TaskState.WORKING

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "progress": self.progress,
            "message": self.message,
            "intermediate_result": self.intermediate_result,
            "timestamp": self.timestamp,
            "state": self.state.value,
        }


@dataclass
class A2ATask:
    """An A2A protocol task."""
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    description: str = ""
    task: str = ""  # backward compat: alias for description
    assigned_to: str = ""
    created_by: str = "nexus"
    state: TaskState = TaskState.SUBMITTED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    result: Optional[str] = None
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "assigned_to": self.assigned_to,
            "created_by": self.created_by,
            "state": self.state.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class A2AMessage:
    """A message in the A2A protocol."""
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    message_type: Optional[MessageType] = None  # type of message (task_request, task_response, etc.)
    task_id: str = ""
    role: str = "agent"  # agent, user
    content: str = ""
    task: str = ""  # backward compat: task description
    sender: str = ""
    recipient: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "message_type": self.message_type.value if self.message_type else None,
            "task_id": self.task_id,
            "role": self.role,
            "content": self.content,
            "task": self.task,
            "sender": self.sender,
            "recipient": self.recipient,
            "timestamp": self.timestamp,
        }


class A2AProtocol:
    """
    A2A Protocol handler for NEXUS.

    Implements:
      - Agent Card discovery and registration
      - Task delegation to remote agents
      - Task status tracking
      - Message passing between agents
      - Service discovery by capability

    Usage:
        a2a = A2AProtocol()
        # Delegate a task to a remote agent
        task = await a2a.delegate_task(
            agent_url="http://remote-agent:8080",
            description="Analyze this dataset",
        )
        # Check status
        status = await a2a.get_task_status(agent_url, task.task_id)
    """

    def __init__(self):
        self.settings = get_settings()
        self._local_tasks: dict[str, A2ATask] = {}
        self._discovered_agents: dict[str, dict[str, Any]] = {}

    async def get_agent_card(self, agent_url: str) -> Optional[dict[str, Any]]:
        """
        Discover an agent's capabilities by fetching its Agent Card.

        Args:
            agent_url: Base URL of the remote agent.

        Returns:
            Agent Card dict or None if discovery fails.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{agent_url}/.well-known/agent.json")
                if response.status_code == 200:
                    card = response.json()
                    self._discovered_agents[agent_url] = card
                    logger.info("Discovered agent at %s: %s", agent_url, card.get("name", "unknown"))
                    return card
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning("Failed to discover agent at %s: %s", agent_url, e)
        return None

    async def delegate_task(
        self,
        agent_url: str,
        description: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> A2ATask:
        """
        Delegate a task to a remote agent via A2A protocol.

        Args:
            agent_url: Base URL of the remote agent.
            description: Task description.
            metadata: Optional task metadata.

        Returns:
            A2ATask with the task_id for tracking.
        """
        task = A2ATask(
            description=description,
            assigned_to=agent_url,
            metadata=metadata or {},
        )
        self._local_tasks[task.task_id] = task

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{agent_url}/a2a/tasks",
                    json={
                        "task_id": task.task_id,
                        "description": description,
                        "metadata": metadata or {},
                    },
                )

                if response.status_code in (200, 201):
                    data = response.json()
                    task.state = TaskState.WORKING
                    task.updated_at = datetime.now(timezone.utc).isoformat()
                    if "task_id" in data:
                        task.metadata["remote_task_id"] = data["task_id"]
                    logger.info("Delegated task %s to %s", task.task_id, agent_url)
                else:
                    task.state = TaskState.FAILED
                    task.error = f"Remote agent returned HTTP {response.status_code}"
                    logger.error("Task delegation failed: HTTP %d", response.status_code)

        except (httpx.ConnectError, httpx.TimeoutException) as e:
            task.state = TaskState.FAILED
            task.error = f"Connection error: {str(e)}"
            logger.error("Task delegation failed: %s", e)

        return task

    async def get_task_status(self, agent_url: str, task_id: str) -> Optional[dict[str, Any]]:
        """Get the status of a delegated task."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{agent_url}/a2a/tasks/{task_id}")
                if response.status_code == 200:
                    return response.json()
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        return None

    async def cancel_task(self, agent_url: str, task_id: str) -> bool:
        """Cancel a delegated task."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.delete(f"{agent_url}/a2a/tasks/{task_id}")
                return response.status_code in (200, 204)
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def send_message(
        self,
        agent_url: str,
        task_id: str,
        content: str,
        role: str = "agent",
    ) -> Optional[dict[str, Any]]:
        """Send a message to a remote agent about a task."""
        message = A2AMessage(
            task_id=task_id,
            role=role,
            content=content,
        )

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{agent_url}/a2a/tasks/{task_id}/messages",
                    json=message.to_dict(),
                )
                if response.status_code in (200, 201):
                    return response.json()
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        return None

    def discover_local_agents(self) -> list[dict[str, Any]]:
        """
        Discover local agents registered in the NEXUS Agent Registry.

        Returns Agent Cards for all local agents.
        """
        try:
            from nexus.core.registry import get_registry
            registry = get_registry()
            return registry.get_all_cards()
        except Exception:
            return []

    def get_local_task(self, task_id: str) -> Optional[A2ATask]:
        """Get a local task by ID."""
        return self._local_tasks.get(task_id)

    def list_local_tasks(self, state: Optional[TaskState] = None) -> list[A2ATask]:
        """List local tasks, optionally filtered by state."""
        tasks = list(self._local_tasks.values())
        if state:
            tasks = [t for t in tasks if t.state == state]
        return tasks

    def get_discovered_agents(self) -> dict[str, dict[str, Any]]:
        """Get all discovered remote agents."""
        return dict(self._discovered_agents)

    def get_stats(self) -> dict[str, Any]:
        """Get A2A protocol statistics."""
        state_counts = {}
        for task in self._local_tasks.values():
            state_counts[task.state.value] = state_counts.get(task.state.value, 0) + 1
        return {
            "local_tasks": len(self._local_tasks),
            "discovered_agents": len(self._discovered_agents),
            "task_states": state_counts,
        }
