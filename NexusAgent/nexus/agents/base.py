"""
NEXUS Base Agent — Abstract base class for all NEXUS agents.

Every specialized agent (Researcher, Developer, Analyst, Operator) inherits
from BaseAgent. It provides the common lifecycle (initialize → run → finalize),
access to shared services (LLM router, memory, MCP tools, security), and
standardized error handling and audit logging.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from nexus.core.config import get_settings
from nexus.core.exceptions import AgentError, AgentTimeoutError
from nexus.core.registry import AgentCapability, AgentStatus, AgentInstance
from nexus.core.viz_events import get_viz_emitter, VizEventType

logger = logging.getLogger(__name__)


class AgentPhase(str, Enum):
    """Phases of an agent's execution lifecycle."""
    INITIALIZING = "initializing"
    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentContext:
    """
    Shared context passed through every step of an agent's execution.

    Carries conversation history, accumulated knowledge, tool results,
    and metadata that the agent uses to make decisions.
    """
    task: str
    agent_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    conversation: list[dict[str, Any]] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    max_iterations: int = 25
    current_iteration: int = 0

    def add_message(self, role: str, content: str, **kwargs) -> None:
        """Add a message to the conversation history."""
        msg = {"role": role, "content": content}
        msg.update(kwargs)
        self.conversation.append(msg)

    def store_artifact(self, key: str, value: Any) -> None:
        """Store an artifact (file, result, data) for later retrieval."""
        self.artifacts[key] = value

    def get_artifact(self, key: str, default: Any = None) -> Any:
        """Retrieve a stored artifact."""
        return self.artifacts.get(key, default)


@dataclass
class AgentResult:
    """Structured result from an agent's execution."""
    agent_id: str
    agent_type: str
    status: AgentStatus
    answer: str = ""
    artifacts: dict[str, Any] = field(default_factory=dict)
    steps_taken: int = 0
    tools_used: list[str] = field(default_factory=list)
    reasoning_trace: list[dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    token_usage: dict[str, int] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == AgentStatus.COMPLETED


class BaseAgent(ABC):
    """
    Abstract base class for all NEXUS agents.

    Provides:
      - Standard lifecycle (initialize → run_loop → finalize)
      - Lazy-initialized access to LLM router, memory, security, MCP tools
      - Conversation management with automatic context window handling
      - Audit logging for every significant action
      - Error handling with graceful degradation
      - Token usage tracking

    Subclasses must implement:
      - ``system_prompt`` property: The agent's system prompt
      - ``capabilities`` property: List of agent capabilities
      - ``plan`` method: Create a plan for the task
      - ``execute_step`` method: Execute one step of the plan
      - ``reflect`` method: Evaluate progress and decide next action
    """

    def __init__(
        self,
        agent_type: str,
        description: str = "",
        skills: Optional[list[str]] = None,
    ):
        self.agent_type = agent_type
        self.description = description
        self.skills = skills or []
        self._phase: AgentPhase = AgentPhase.INITIALIZING
        self._context: Optional[AgentContext] = None
        self._llm_router = None
        self._memory = None
        self._security = None
        self._mcp_client = None
        self._audit_logger = None
        self._settings = None
        self._tools_used: list[str] = []
        self._token_usage: dict[str, int] = {"prompt": 0, "completion": 0, "total": 0}
        self._viz = None

    # ── Abstract interface ────────────────────────────────────────

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt for this agent type."""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> list[AgentCapability]:
        """Return the list of capabilities this agent has."""
        ...

    @abstractmethod
    async def plan(self, context: AgentContext) -> list[dict[str, Any]]:
        """
        Create a plan for the given task.

        Args:
            context: The agent's execution context.

        Returns:
            A list of planned steps, each a dict with 'action' and 'params'.
        """
        ...

    @abstractmethod
    async def execute_step(self, step: dict[str, Any], context: AgentContext) -> dict[str, Any]:
        """
        Execute a single step of the plan.

        Args:
            step: The step to execute.
            context: The agent's execution context.

        Returns:
            A dict with 'success', 'result', and optional 'next_steps'.
        """
        ...

    @abstractmethod
    async def reflect(self, context: AgentContext) -> dict[str, Any]:
        """
        Reflect on progress so far and decide whether to continue.

        Args:
            context: The agent's execution context.

        Returns:
            A dict with 'should_continue', 'assessment', and optional 'adjustments'.
        """
        ...

    # ── Lazy-initialized service accessors ────────────────────────

    @property
    def settings(self):
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    @property
    def llm_router(self):
        if self._llm_router is None:
            from nexus.llm.router import LLMRouter
            self._llm_router = LLMRouter()
        return self._llm_router

    @property
    def memory(self):
        if self._memory is None:
            from nexus.memory.chroma_service import NexusMemoryService
            self._memory = NexusMemoryService(persist_dir=self.settings.chroma_persist_dir)
        return self._memory

    @property
    def security(self):
        if self._security is None:
            from nexus.security.guardrails import GuardrailManager
            self._security = GuardrailManager()
        return self._security

    @property
    def mcp_client(self):
        """MCP client is the FastMCP server instance."""
        if self._mcp_client is None:
            from nexus.mcp_server import nexus_mcp
            self._mcp_client = nexus_mcp
        return self._mcp_client

    @property
    def audit_logger(self):
        if self._audit_logger is None:
            from nexus.security.audit import AuditLogger
            self._audit_logger = AuditLogger()
        return self._audit_logger

    @property
    def viz_emitter(self):
        """Lazy-initialized VizEventEmitter for brick-by-brick visualization."""
        if self._viz is None:
            self._viz = get_viz_emitter()
        return self._viz

    # ── Lifecycle ─────────────────────────────────────────────────

    async def run(self, task: str, **kwargs) -> AgentResult:
        """
        Execute the full agent lifecycle: initialize → plan → execute → reflect → finalize.

        This is the main entry point. It orchestrates the agent's work,
        handles errors, and returns a structured result.

        Args:
            task: The task description.
            **kwargs: Additional parameters passed to the context.

        Returns:
            An AgentResult with the outcome.
        """
        started_at = datetime.now(timezone.utc).isoformat()
        self._phase = AgentPhase.INITIALIZING

        # Create execution context
        self._context = AgentContext(
            task=task,
            max_iterations=kwargs.get("max_iterations", self.settings.orchestrator_max_iterations),
            **{k: v for k, v in kwargs.items() if k != "max_iterations"},
        )
        self._context.add_message("system", self.system_prompt)
        self._context.add_message("user", task)

        # Log start
        await self._log_action("agent_start", {"task": task[:200]})

        # Viz: emit build start
        build_id = self._context.agent_id
        try:
            await self.viz_emitter.emit_build_start(build_id, description=f"{self.agent_type}: {task[:100]}")
        except Exception:
            pass  # Viz events should never break agent execution

        try:
            # ── Phase 1: Planning ──
            self._phase = AgentPhase.PLANNING
            plan = await self.plan(self._context)
            self._context.store_artifact("plan", plan)
            await self._log_action("plan_created", {"steps": len(plan)})

            # ── Phase 2: Execution loop ──
            self._phase = AgentPhase.EXECUTING
            steps_completed = 0
            total_steps = len(plan)

            for step in plan:
                if self._context.current_iteration >= self._context.max_iterations:
                    logger.warning("Agent %s hit max iterations (%d)", self.agent_type, self._context.max_iterations)
                    break

                self._context.current_iteration += 1

                # Execute the step
                step_result = await self.execute_step(step, self._context)
                steps_completed += 1

                # Viz: emit build progress
                try:
                    step_desc = step.get("action", "") or step.get("params", {}).get("path", "") or f"Step {steps_completed}"
                    await self.viz_emitter.emit_build_progress(
                        build_id,
                        step=step_desc,
                        progress=steps_completed / max(total_steps, 1),
                    )
                except Exception:
                    pass

                # Track tools used
                if step_result.get("tool_used"):
                    self._tools_used.append(step_result["tool_used"])

                # Store step result
                self._context.store_artifact(f"step_{steps_completed}", step_result)

                # Reflect after each step
                self._phase = AgentPhase.REFLECTING
                reflection = await self.reflect(self._context)

                if not reflection.get("should_continue", True):
                    logger.info("Agent %s decided to stop after %d steps: %s",
                                self.agent_type, steps_completed, reflection.get("assessment", ""))
                    break

                # Apply adjustments if any
                if reflection.get("adjustments"):
                    self._context.metadata["adjustments"] = reflection["adjustments"]

                self._phase = AgentPhase.EXECUTING

            # ── Phase 3: Finalize ──
            self._phase = AgentPhase.FINALIZING
            answer = await self._synthesize_answer(self._context)

            completed_at = datetime.now(timezone.utc).isoformat()
            self._phase = AgentPhase.COMPLETED

            await self._log_action("agent_complete", {
                "steps": steps_completed,
                "tools_used": self._tools_used,
                "tokens": self._token_usage,
            })

            # Viz: emit build complete
            try:
                await self.viz_emitter.emit_build_complete(
                    build_id,
                    summary=f"Completed in {steps_completed} steps, {len(self._tools_used)} tools used",
                )
            except Exception:
                pass

            return AgentResult(
                agent_id=self._context.agent_id,
                agent_type=self.agent_type,
                status=AgentStatus.COMPLETED,
                answer=answer,
                artifacts=self._context.artifacts,
                steps_taken=steps_completed,
                tools_used=self._tools_used,
                reasoning_trace=self._context.conversation,
                started_at=started_at,
                completed_at=completed_at,
                token_usage=self._token_usage,
            )

        except Exception as e:
            self._phase = AgentPhase.FAILED
            logger.exception("Agent %s failed: %s", self.agent_type, e)
            await self._log_action("agent_failed", {"error": str(e)})

            # Viz: emit error
            try:
                await self.viz_emitter.emit_error(str(e), build_id=build_id)
            except Exception:
                pass

            return AgentResult(
                agent_id=self._context.agent_id if self._context else "unknown",
                agent_type=self.agent_type,
                status=AgentStatus.FAILED,
                error=str(e),
                tools_used=self._tools_used,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                token_usage=self._token_usage,
            )

    async def execute_with_retry(
        self,
        task: str,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        max_backoff: float = 30.0,
        **kwargs,
    ) -> AgentResult:
        """
        Execute a task with exponential backoff retry.

        Args:
            task: The task description.
            max_retries: Maximum number of retry attempts.
            backoff_base: Base delay for exponential backoff (in seconds).
            max_backoff: Maximum delay between retries.
            **kwargs: Additional parameters passed to run().

        Returns:
            AgentResult from the execution.
        """
        last_error: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            try:
                return await self.run(task, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    delay = min(backoff_base * (2 ** attempt), max_backoff)
                    jitter = delay * 0.1 * (uuid.uuid4().time_low % 10) / 10
                    actual_delay = delay + jitter
                    logger.warning(
                        "Agent %s attempt %d/%d failed: %s. Retrying in %.1fs...",
                        self.agent_type, attempt + 1, max_retries + 1, str(e), actual_delay,
                    )
                    await asyncio.sleep(actual_delay)

        return AgentResult(
            agent_id=self._context.agent_id if self._context else "unknown",
            agent_type=self.agent_type,
            status=AgentStatus.FAILED,
            error=f"Failed after {max_retries + 1} attempts: {last_error}",
            tools_used=self._tools_used,
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=datetime.now(timezone.utc).isoformat(),
            token_usage=self._token_usage,
        )

    async def execute_with_fallback(
        self,
        task: str,
        fallback_agent_type: Optional[str] = None,
        **kwargs,
    ) -> AgentResult:
        """
        Execute task with automatic fallback to another agent type on failure.

        Args:
            task: The task description.
            fallback_agent_type: Agent type to use if this agent fails.
                                 If None, uses LLM-based fallback.
            **kwargs: Additional parameters.

        Returns:
            AgentResult from primary or fallback agent.
        """
        try:
            return await self.execute_with_retry(task, max_retries=2, **kwargs)
        except Exception as e:
            logger.warning("Agent %s failed, trying fallback: %s", self.agent_type, e)

            if fallback_agent_type:
                # Dynamically load and use the fallback agent
                from nexus.core.registry import get_registry
                registry = get_registry()
                fallback_instance = registry.spawn(fallback_agent_type, task=task)
                # Try to run the fallback agent using the LLM router
                try:
                    from nexus.llm.router import LLMRouter, TaskComplexity
                    fallback_router = LLMRouter()
                    # Get fallback agent definition for system prompt
                    fallback_def = registry._agent_types.get(fallback_agent_type, {})
                    fallback_prompt = fallback_def.get("description", f"You are a {fallback_agent_type} agent.")
                    response = await fallback_router.complete(
                        messages=[
                            {"role": "system", "content": fallback_prompt},
                            {"role": "user", "content": task},
                        ],
                        task_complexity=TaskComplexity.MEDIUM,
                    )
                    return AgentResult(
                        agent_id=self._context.agent_id if self._context else "unknown",
                        agent_type=fallback_agent_type,
                        status=AgentStatus.COMPLETED,
                        answer=response.content,
                        artifacts={},
                        steps_taken=0,
                        tools_used=["llm_fallback"],
                        reasoning_trace=[],
                        started_at=datetime.now(timezone.utc).isoformat(),
                        completed_at=datetime.now(timezone.utc).isoformat(),
                        token_usage={"prompt": 0, "completion": 0, "total": 0},
                    )
                except Exception as fallback_error:
                    return AgentResult(
                        agent_id=self._context.agent_id if self._context else "unknown",
                        agent_type=self.agent_type,
                        status=AgentStatus.FAILED,
                        error=f"Primary failed: {e}. Fallback also failed: {fallback_error}",
                        tools_used=self._tools_used,
                        started_at=datetime.now(timezone.utc).isoformat(),
                        completed_at=datetime.now(timezone.utc).isoformat(),
                        token_usage=self._token_usage,
                    )
            else:
                # Simple LLM fallback — just ask the router directly
                from nexus.llm.router import LLMRouter, TaskComplexity
                router = LLMRouter()
                try:
                    response = await router.complete(
                        messages=[
                            {"role": "system", "content": self.system_prompt},
                            {"role": "user", "content": task},
                        ],
                        task_complexity=TaskComplexity.MEDIUM,
                    )
                    return AgentResult(
                        agent_id=self._context.agent_id if self._context else "unknown",
                        agent_type=self.agent_type,
                        status=AgentStatus.COMPLETED,
                        answer=response.content,
                        artifacts={},
                        steps_taken=0,
                        tools_used=["llm_fallback"],
                        reasoning_trace=[],
                        started_at=datetime.now(timezone.utc).isoformat(),
                        completed_at=datetime.now(timezone.utc).isoformat(),
                        token_usage={"prompt": 0, "completion": 0, "total": 0},
                    )
                except Exception as llm_error:
                    return AgentResult(
                        agent_id=self._context.agent_id if self._context else "unknown",
                        agent_type=self.agent_type,
                        status=AgentStatus.FAILED,
                        error=f"All fallbacks failed. Primary: {e}, LLM: {llm_error}",
                        tools_used=self._tools_used,
                        started_at=datetime.now(timezone.utc).isoformat(),
                        completed_at=datetime.now(timezone.utc).isoformat(),
                        token_usage=self._token_usage,
                    )

    async def _call_llm(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.3,
        tools: Optional[list[dict[str, Any]]] = None,
        max_tool_turns: int = 10,
        provider: Optional[str] = "glm",  # Default to GLM-4-Flash (free)
        **kwargs,
    ) -> str:
        """
        Call the LLM router and track token usage.

        Args:
            messages: Conversation messages.
            temperature: Sampling temperature.
            tools: Optional list of tool definitions for function calling.
            max_tool_turns: Maximum number of tool call iterations.

        Returns:
            The LLM's response text.
        """
        from nexus.llm.router import TaskComplexity

        current_messages = list(messages)

        for turn in range(max_tool_turns):
            # Estimate complexity based on messages
            total_chars = sum(len(m.get("content", "")) for m in current_messages)
            task_complexity = TaskComplexity.MEDIUM if total_chars > 2000 else TaskComplexity.SIMPLE

            response = await self.llm_router.complete(
                messages=current_messages,
                task_complexity=task_complexity,
                temperature=temperature,
                tools=tools,
                provider=provider,
                **kwargs,
            )

            # Track tokens
            if response.usage:
                self._token_usage["prompt"] += response.usage.get("prompt_tokens", 0) or 0
                self._token_usage["completion"] += response.usage.get("completion_tokens", 0) or 0
                self._token_usage["total"] = self._token_usage["prompt"] + self._token_usage["completion"]

            # If no tool calls, return the content
            if not response.tool_calls:
                # Add assistant response to messages
                current_messages.append({"role": "assistant", "content": response.content})
                return response.content

            # Handle tool calls
            logger.info("Processing %d tool calls from LLM", len(response.tool_calls))

            # Add assistant message with tool calls to conversation
            assistant_msg = {"role": "assistant", "content": response.content or ""}
            if response.tool_calls:
                assistant_msg["tool_calls"] = response.tool_calls
            current_messages.append(assistant_msg)

            # Process each tool call
            for tc in response.tool_calls:
                tool_name = tc.get("function", {}).get("name", "")
                tool_args_str = tc.get("function", {}).get("arguments", "{}")

                # Parse arguments
                try:
                    import json as _json
                    tool_args = _json.loads(tool_args_str) if tool_args_str else {}
                except (_json.JSONDecodeError, ValueError, TypeError):
                    tool_args = {"raw_args": tool_args_str}

                logger.info("Calling tool: %s with args: %s", tool_name, str(tool_args)[:200])

                # Execute the tool
                try:
                    tool_result = await self._use_tool(tool_name, tool_args)
                    # Convert result to string for message
                    if tool_result is None:
                        result_str = "Tool executed successfully"
                    elif isinstance(tool_result, str):
                        result_str = tool_result
                    else:
                        import json
                        result_str = json.dumps(tool_result, default=str)
                except Exception as e:
                    logger.error("Tool '%s' failed: %s", tool_name, e)
                    result_str = f"Error: {str(e)}"

                # Add tool result to messages
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": result_str,
                })

            # Continue loop to get next LLM response

        # Max tool turns exceeded
        raise AgentError(f"Max tool turns ({max_tool_turns}) exceeded")

    _FALLBACK_TOOLS = frozenset({
        "web_search", "code_execute", "file_read", "file_write",
        "memory_store", "memory_recall",
    })

    async def _use_tool(self, tool_name: str, params: dict[str, Any]) -> Any:
        self._tools_used.append(tool_name)
        await self._log_action("tool_call", {"tool": tool_name, "params": str(params)[:200]})

        # Viz: emit visualization events for key tool actions
        build_id = self._context.agent_id if self._context else "default"
        try:
            if tool_name in ("write_file", "file_write"):
                path = params.get("path", "unknown")
                content = params.get("content", "")
                # Detect language from file extension
                ext = path.rsplit(".", 1)[-1] if "." in path else ""
                lang_map = {
                    "py": "python", "js": "javascript", "ts": "typescript",
                    "tsx": "typescript", "jsx": "javascript", "html": "html",
                    "css": "css", "json": "json", "md": "markdown",
                    "sh": "bash", "yaml": "yaml", "yml": "yaml",
                    "rs": "rust", "go": "go", "java": "java",
                }
                language = lang_map.get(ext, "")
                await self.viz_emitter.emit_file_create(path, content, language=language, build_id=build_id)
            elif tool_name in ("execute_code", "code_execute", "execute_sandboxed"):
                code = params.get("code", "")
                language = params.get("language", "python")
                from nexus.core.viz_events import VizEvent
                await self.viz_emitter.emit(VizEvent(
                    type=VizEventType.CODE_EXECUTE,
                    title=f"Executing {language} code",
                    detail=code[:200],
                    content=code,
                    language=language,
                    status="running",
                    metadata={"build_id": build_id},
                ))
            elif tool_name in ("install_package",):
                pkg = params.get("package", "unknown")
                from nexus.core.viz_events import VizEvent
                await self.viz_emitter.emit(VizEvent(
                    type=VizEventType.DEPENDENCY_INSTALL,
                    title=f"Installing {pkg}",
                    detail=f"pip install {pkg}",
                    status="running",
                    metadata={"build_id": build_id},
                ))
        except Exception:
            pass  # Viz events should never break tool execution

        if tool_name in self._FALLBACK_TOOLS:
            return await self._fallback_tool_execution(tool_name, params)

        try:
            result = await self._invoke_mcp_tool(tool_name, params)
            return result
        except Exception as e:
            logger.warning("MCP tool '%s' not found or failed: %s", tool_name, e)
            return {"error": f"Tool '{tool_name}' not available", "suggestion": "Try a different approach"}

    async def _invoke_mcp_tool(self, tool_name: str, params: dict[str, Any]) -> Any:
        """Dynamically invoke an MCP tool function by name."""
        tool_map = {
            "search_memory": self._mcp_search_memory,
            "store_memory": self._mcp_store_memory,
            "delete_memory": self._mcp_delete_memory,
            "list_namespaces": self._mcp_list_namespaces,
            "memory_stats": self._mcp_memory_stats,
            "knowledge_query": self._mcp_knowledge_query,
            "knowledge_add_entity": self._mcp_knowledge_add_entity,
            "knowledge_add_relation": self._mcp_knowledge_add_relation,
            "knowledge_search": self._mcp_knowledge_search,
            "knowledge_paths": self._mcp_knowledge_paths,
            "llm_complete": self._mcp_llm_complete,
            "llm_list_models": self._mcp_llm_list_models,
            "llm_provider_status": self._mcp_llm_provider_status,
            "llm_stream": self._mcp_llm_stream,
            "spawn_agent": self._mcp_spawn_agent,
            "list_agents": self._mcp_list_agents,
            "agent_status": self._mcp_agent_status,
            "agent_delegate": self._mcp_agent_delegate,
            "a2a_discover": self._mcp_a2a_discover,
            "execute_code": self._mcp_execute_code,
            "execute_sandboxed": self._mcp_execute_sandboxed,
            "install_package": self._mcp_install_package,
            "read_file": self._mcp_read_file,
            "write_file": self._mcp_write_file,
            "list_files": self._mcp_list_files,
            "delete_file": self._mcp_delete_file,
            "move_file": self._mcp_move_file,
            "copy_file": self._mcp_copy_file,
            "search_files": self._mcp_search_files,
            "web_scrape": self._mcp_web_scrape,
            "web_screenshot": self._mcp_web_screenshot,
            "reason_react": self._mcp_reason_react,
            "reason_tot": self._mcp_reason_tot,
            "reason_lats": self._mcp_reason_lats,
            "run_pipeline": self._mcp_run_pipeline,
            "rag_query": self._mcp_rag_query,

        }
        handler = tool_map.get(tool_name)
        if not handler:
            raise AttributeError(f"No handler for tool '{tool_name}'")
        return await handler(params)

    # ── MCP Tool Handlers ───────────────────────────────────────────

    async def _mcp_search_memory(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import search_memory
        return await search_memory(params["query"], params.get("namespace", "knowledge"), params.get("top_k", 5))

    async def _mcp_store_memory(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import store_memory
        return await store_memory(params["text"], params.get("namespace", "knowledge"), params.get("metadata"))

    async def _mcp_delete_memory(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import delete_memory
        doc_ids = params.get("doc_ids", [params["doc_id"]] if "doc_id" in params else [])
        return await delete_memory(doc_ids, params.get("namespace", "knowledge"))

    async def _mcp_list_namespaces(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import list_namespaces
        return await list_namespaces()

    async def _mcp_memory_stats(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import memory_stats
        return await memory_stats()

    async def _mcp_knowledge_query(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import knowledge_query
        return await knowledge_query(params["entity_name"], params.get("depth", 1))

    async def _mcp_knowledge_add_entity(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import knowledge_add_entity
        return await knowledge_add_entity(params.get("entity_type", "concept"), params["name"], params.get("properties"))

    async def _mcp_knowledge_add_relation(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import knowledge_add_relation
        return await knowledge_add_relation(params["source_name"], params["target_name"], params["relation_type"], params.get("properties"))

    async def _mcp_knowledge_search(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import knowledge_search
        return await knowledge_search(params["query"], params.get("entity_type"), params.get("limit", 20))

    async def _mcp_knowledge_paths(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import knowledge_paths
        return await knowledge_paths(params["source_name"], params["target_name"], params.get("max_length", 5))

    async def _mcp_llm_complete(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import llm_complete
        return await llm_complete(params.get("prompt", params.get("messages_json")), params.get("model"), params.get("temperature", 0.7), params.get("max_tokens", 4096))

    async def _mcp_llm_list_models(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import llm_list_models
        return await llm_list_models()

    async def _mcp_llm_provider_status(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import llm_provider_status
        return await llm_provider_status()

    async def _mcp_llm_stream(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import llm_stream
        return await llm_stream(params.get("prompt", params.get("messages_json")), params.get("model"), params.get("temperature", 0.7))

    async def _mcp_spawn_agent(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import spawn_agent
        return await spawn_agent(params.get("agent_type", "general"), params["task"], params.get("config"))

    async def _mcp_list_agents(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import list_agents
        return await list_agents()

    async def _mcp_agent_status(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import agent_status
        return await agent_status(params["instance_id"])

    async def _mcp_agent_delegate(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import agent_delegate
        return await agent_delegate(params.get("source_agent", ""), params.get("target_agent", ""), params["task"], params.get("context"))

    async def _mcp_a2a_discover(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import a2a_discover
        return await a2a_discover(params["agent_url"])

    async def _mcp_execute_code(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import execute_code
        return await execute_code(params["code"], params.get("language", "python"), params.get("timeout", 30))

    async def _mcp_execute_sandboxed(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import execute_sandboxed
        return await execute_sandboxed(params.get("command", params.get("code")), params.get("timeout", 30), params.get("allowed_dirs"))

    async def _mcp_install_package(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import install_package
        return await install_package(params["package"], params.get("version"))

    async def _mcp_read_file(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import read_file
        return await read_file(params["path"], params.get("encoding", "utf-8"))

    async def _mcp_write_file(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import write_file
        return await write_file(params["path"], params["content"], params.get("encoding", "utf-8"))

    async def _mcp_list_files(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import list_files
        return await list_files(params.get("directory", "."), params.get("pattern", "*"))

    async def _mcp_delete_file(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import delete_file
        return await delete_file(params["path"])

    async def _mcp_move_file(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import move_file
        return await move_file(params["source"], params["destination"])

    async def _mcp_copy_file(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import copy_file
        return await copy_file(params["source"], params["destination"])

    async def _mcp_search_files(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import search_files
        return await search_files(params.get("query", params.get("content_query", "")), params.get("path", params.get("directory", ".")), params.get("file_pattern", params.get("pattern", "*")))

    async def _mcp_web_scrape(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import web_scrape
        return await web_scrape(params["url"], params.get("max_length", 10000))

    async def _mcp_web_screenshot(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import web_screenshot
        return await web_screenshot(params["url"])

    async def _mcp_reason_react(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import reason_react
        return await reason_react(params["task"], params.get("max_iterations", 10))

    async def _mcp_reason_tot(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import reason_tot
        return await reason_tot(params["task"], params.get("max_depth", 3), params.get("branch_factor", 3))

    async def _mcp_reason_lats(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import reason_lats
        return await reason_lats(params["task"], params.get("max_simulations", 10), params.get("max_depth", 4))

    async def _mcp_run_pipeline(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import run_pipeline
        tasks = params.get("tasks", params.get("stages_json", []))
        sequential = params.get("sequential", True)
        return await run_pipeline(tasks, sequential)

    async def _mcp_rag_query(self, params: dict[str, Any]) -> Any:
        from nexus.mcp_server import rag_query
        return await rag_query(params["query"], params.get("namespace", "knowledge"))

    async def _mcp_telemetry_submit(self, params: dict[str, Any]) -> Any:
        return {"error": "not implemented"}

    async def _mcp_browser_navigate(self, params: dict[str, Any]) -> Any:
        return {"error": "not implemented"}

    async def _mcp_browser_snapshot(self, params: dict[str, Any]) -> Any:
        return {"error": "not implemented"}

    async def _fallback_tool_execution(self, tool_name: str, params: dict[str, Any]) -> Any:
        """
        Fallback tool execution when MCP server is unavailable.

        Uses the LLM to simulate tool behavior for known tool patterns.
        """
        # Map known tools to direct implementations
        tool_map = {
            "web_search": self._tool_web_search,
            "code_execute": self._tool_code_execute,
            "file_read": self._tool_file_read,
            "file_write": self._tool_file_write,
            "memory_store": self._tool_memory_store,
            "memory_recall": self._tool_memory_recall,
        }

        handler = tool_map.get(tool_name)
        if handler:
            return await handler(params)

        return {"error": f"Tool '{tool_name}' not available", "suggestion": "Try a different approach"}

    async def _tool_web_search(self, params: dict[str, Any]) -> dict[str, Any]:
        """Direct web search implementation."""
        try:
            from nexus.knowledge.web_search import MultiSourceWebSearch
            engine = MultiSourceWebSearch()
            results = await engine.search(params.get("query", ""), num_results=params.get("num", 5))
            return {"results": results}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_code_execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Direct code execution."""
        try:
            from nexus.dev.code_executor import CodeExecutor
            executor = CodeExecutor()
            result = await executor.execute(
                code=params.get("code", ""),
                language=params.get("language", "python"),
                timeout=params.get("timeout", 30),
            )
            return result
        except Exception as e:
            return {"error": str(e)}

    async def _tool_file_read(self, params: dict[str, Any]) -> dict[str, Any]:
        """Read a file from disk."""
        import aiofiles
        path = params.get("path", "")
        try:
            async with aiofiles.open(path, "r") as f:
                content = await f.read()
            return {"content": content, "path": path}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_file_write(self, params: dict[str, Any]) -> dict[str, Any]:
        """Write content to a file on disk."""
        import aiofiles
        path = params.get("path", "")
        content = params.get("content", "")
        try:
            async with aiofiles.open(path, "w") as f:
                await f.write(content)
            return {"success": True, "path": path, "bytes_written": len(content)}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_memory_store(self, params: dict[str, Any]) -> dict[str, Any]:
        """Store information in memory."""
        try:
            svc = self.memory
            doc_id = await svc.store(
                text=params.get("content", ""),
                metadata=params.get("metadata", {}),
                namespace="working",
                doc_id=params.get("id", uuid.uuid4().hex[:8]),
            )
            return {"success": True, "doc_id": doc_id}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_memory_recall(self, params: dict[str, Any]) -> dict[str, Any]:
        """Recall information from memory."""
        try:
            svc = self.memory
            raw = await svc.search(
                query=params.get("query", ""),
                top_k=params.get("n", 5),
                namespace="working",
            )
            # Parse ChromaDB results
            ids = raw.get("ids", [[]])[0]
            docs = raw.get("documents", [[]])[0]
            metas = raw.get("metadatas", [[]])[0]
            dists = raw.get("distances", [[]])[0]
            results = []
            for i, doc_id in enumerate(ids):
                dist = dists[i] if i < len(dists) else 0.5
                results.append({
                    "id": doc_id,
                    "text": docs[i] if i < len(docs) else "",
                    "metadata": metas[i] if i < len(metas) else {},
                    "relevance": max(0.0, 1.0 - dist / 2.0),
                })
            return {"results": results}
        except Exception as e:
            return {"error": str(e)}

    async def _synthesize_answer(self, context: AgentContext) -> str:
        """
        Synthesize a final answer from the execution context.

        Uses the LLM to create a coherent summary of all work done.
        """
        synthesis_prompt = (
            "Based on the following conversation and work completed, "
            "provide a clear, comprehensive final answer to the original task.\n\n"
            f"Original task: {context.task}\n\n"
            f"Steps completed: {context.current_iteration}\n"
            f"Tools used: {', '.join(self._tools_used) or 'none'}\n\n"
            "Conversation summary:\n"
        )

        # Add condensed conversation
        for msg in context.conversation[-6:]:  # Last 6 messages for context
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:300]
            synthesis_prompt += f"\n[{role}]: {content}"

        try:
            messages = [
                {"role": "system", "content": "You synthesize final answers from agent execution traces. Be concise but complete."},
                {"role": "user", "content": synthesis_prompt},
            ]
            answer = await self._call_llm(messages, temperature=0.2)
            return answer
        except Exception as e:
            logger.error("Answer synthesis failed: %s", e)
            # Fallback: use the last assistant message
            for msg in reversed(context.conversation):
                if msg.get("role") == "assistant":
                    return msg.get("content", "Task completed but answer synthesis failed.")
            return "Task completed."

    async def _log_action(self, action: str, details: dict[str, Any]) -> None:
        """Log an action to the audit logger."""
        try:
            self.audit_logger.log(
                actor=self._context.agent_id if self._context else "unknown",
                action=action,
                details=details,
            )
        except Exception:
            pass  # Audit logging should never break the agent

    @property
    def phase(self) -> AgentPhase:
        return self._phase

    def get_info(self) -> dict[str, Any]:
        """Get information about this agent."""
        return {
            "agent_type": self.agent_type,
            "description": self.description,
            "capabilities": [c.value for c in self.capabilities],
            "skills": self.skills,
            "phase": self._phase.value,
        }
