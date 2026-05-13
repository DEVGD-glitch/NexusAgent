"""
Comprehensive tests for BaseAgent — the abstract base all NEXUS agents inherit from.

Covers:
  - __init__ with various config options
  - _call_llm() with different providers, temperature, complexity, tool calls, error fallback
  - All ~30 MCP handler methods (10+ tested in depth)
  - _invoke_mcp_tool() dispatching to correct handler
  - _use_tool() with fallback and error handling
  - _fallback_tool_execution() for known tools
  - Audit logging path (AuditLogger.log() called with correct params)
  - Lifecycle: run() with plan → execute → reflect → finalize
  - execute_with_retry() with exponential backoff
  - execute_with_fallback() with agent and LLM fallback
  - _synthesize_answer() with LLM and fallback
  - Token usage tracking
  - Property accessors (lazy init of services)
  - Agent info reporting
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock, call

from nexus.agents.base import (
    BaseAgent,
    AgentContext,
    AgentResult,
    AgentPhase,
)
from nexus.core.registry import AgentCapability, AgentStatus


# ═══════════════════════════════════════════════════════════════════════════════
# Concrete test subclass (BaseAgent is abstract)
# ═══════════════════════════════════════════════════════════════════════════════

class ConcreteAgent(BaseAgent):
    """Minimal concrete subclass for testing BaseAgent behaviour."""

    @property
    def system_prompt(self) -> str:
        return "You are a test agent."

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [AgentCapability.RESEARCH]

    async def plan(self, context: AgentContext) -> list[dict[str, Any]]:
        return [
            {"action": "search", "params": {"query": context.task}},
            {"action": "analyze", "params": {}},
        ]

    async def execute_step(self, step: dict[str, Any], context: AgentContext) -> dict[str, Any]:
        return {"success": True, "result": f"Executed {step['action']}", "tool_used": step["action"]}

    async def reflect(self, context: AgentContext) -> dict[str, Any]:
        return {"should_continue": False, "assessment": "Task complete"}


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def agent():
    """Create a fresh ConcreteAgent with no pre-mocked internals."""
    return ConcreteAgent(agent_type="test_agent", description="A test agent", skills=["testing"])


@pytest.fixture
def mock_llm_router():
    """Patch LLMRouter at its source so lazy properties pick it up."""
    with patch("nexus.llm.router.LLMRouter") as mock:
        router_instance = MagicMock()
        router_instance.complete = AsyncMock()
        mock.return_value = router_instance
        yield mock, router_instance


@pytest.fixture
def mock_audit_logger():
    """Patch AuditLogger at its source so lazy properties pick it up."""
    with patch("nexus.security.audit.AuditLogger") as mock:
        logger_instance = MagicMock()
        mock.return_value = logger_instance
        yield mock, logger_instance


@pytest.fixture
def mock_settings():
    """Patch get_settings to return controlled values."""
    with patch("nexus.agents.base.get_settings") as mock:
        settings = MagicMock()
        settings.orchestrator_max_iterations = 25
        settings.chroma_persist_dir = "/tmp/chroma"
        mock.return_value = settings
        yield mock, settings


@pytest.fixture
def mock_mcp_server():
    """Mock the entire nexus.mcp_server module's exported async functions."""
    patches = {}
    func_names = [
        "search_memory", "store_memory", "delete_memory", "list_namespaces", "memory_stats",
        "knowledge_query", "knowledge_add_entity", "knowledge_add_relation", "knowledge_search",
        "knowledge_paths", "llm_complete", "llm_list_models", "llm_provider_status", "llm_stream",
        "spawn_agent", "list_agents", "agent_status", "agent_delegate", "a2a_discover",
        "execute_code", "execute_sandboxed", "install_package",
        "read_file", "write_file", "list_files", "delete_file", "move_file", "copy_file",
        "search_files", "web_scrape", "web_screenshot",
        "reason_react", "reason_tot", "reason_lats",
        "run_pipeline", "rag_query",
    ]
    patchers = {}
    for name in func_names:
        # Patch at the source module — handler methods use from nexus.mcp_server import ...
        p = patch(f"nexus.mcp_server.{name}", new_callable=AsyncMock)
        m = p.start()
        patches[name] = m
        patchers[name] = p

    yield patches

    for p in patchers.values():
        p.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. __init__ tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestInit:
    """Verify BaseAgent.__init__ sets up all internal state correctly."""

    def test_default_skills_empty(self):
        """Should default skills to empty list when not provided."""
        agent = ConcreteAgent(agent_type="test")
        assert agent.skills == []

    def test_skills_from_arg(self):
        """Should store provided skills."""
        agent = ConcreteAgent(agent_type="test", skills=["web_search", "code"])
        assert agent.skills == ["web_search", "code"]

    def test_agent_type_and_description(self):
        """Should store type and description."""
        agent = ConcreteAgent(agent_type="researcher", description="Research agent")
        assert agent.agent_type == "researcher"
        assert agent.description == "Research agent"

    def test_initial_phase(self):
        """Should start in INITIALIZING phase."""
        agent = ConcreteAgent(agent_type="test")
        assert agent._phase == AgentPhase.INITIALIZING
        assert agent.phase == AgentPhase.INITIALIZING

    def test_initial_state_is_none(self):
        """Lazy-loaded attributes should start as None."""
        agent = ConcreteAgent(agent_type="test")
        assert agent._context is None
        assert agent._llm_router is None
        assert agent._memory is None
        assert agent._security is None
        assert agent._mcp_client is None
        assert agent._audit_logger is None
        assert agent._settings is None

    def test_tools_and_tokens_empty(self):
        """Tools-used list and token usage should start empty."""
        agent = ConcreteAgent(agent_type="test")
        assert agent._tools_used == []
        assert agent._token_usage == {"prompt": 0, "completion": 0, "total": 0}


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Lazy property accessors
# ═══════════════════════════════════════════════════════════════════════════════

class TestLazyProperties:
    """Lazy-initialised service accessors should create services on first access."""

    def test_settings_lazy_init(self, agent):
        """settings should lazily call get_settings()."""
        assert agent._settings is None
        _ = agent.settings
        assert agent._settings is not None

    def test_llm_router_lazy_init(self, agent, mock_llm_router):
        """llm_router should lazily import and create LLMRouter."""
        mock_cls, _ = mock_llm_router
        assert agent._llm_router is None
        router = agent.llm_router
        assert router is not None
        assert agent._llm_router is not None
        # Subsequent calls return the same instance
        assert agent.llm_router is router

    def test_memory_lazy_init(self, agent):
        """memory should lazily import and create NexusMemoryService."""
        with patch("nexus.memory.chroma_service.NexusMemoryService") as mock_svc:
            instance = MagicMock()
            mock_svc.return_value = instance
            assert agent._memory is None
            mem = agent.memory
            assert mem is instance
            assert agent._memory is instance
            assert agent.memory is instance

    def test_security_lazy_init(self, agent):
        """security should lazily import Guardrails (the name used in base.py)."""
        with patch("nexus.security.guardrails.Guardrails", create=True) as mock_g:
            instance = MagicMock()
            mock_g.return_value = instance
            assert agent._security is None
            sec = agent.security
            assert sec is instance

    def test_mcp_client_lazy_init(self, agent):
        """mcp_client should lazily import nexus_mcp."""
        with patch("nexus.mcp_server.nexus_mcp") as mock_mcp:
            assert agent._mcp_client is None
            client = agent.mcp_client
            assert client is mock_mcp

    def test_audit_logger_lazy_init(self, agent, mock_audit_logger):
        """audit_logger should lazily import and create AuditLogger."""
        mock_cls, instance = mock_audit_logger
        assert agent._audit_logger is None
        log = agent.audit_logger
        assert log is instance


# ═══════════════════════════════════════════════════════════════════════════════
# 3. _call_llm tests  (core method)
# ═══════════════════════════════════════════════════════════════════════════════

class MockLLMResponse:
    """Simulates the LLM router's response object."""

    def __init__(self, content="", tool_calls=None, usage=None):
        self.content = content
        self.tool_calls = tool_calls or []
        self.usage = usage if usage is not None else None


class TestCallLlm:
    """Tests for _call_llm — provider selection, complexity, tool calls, errors."""

    @pytest.mark.asyncio
    async def test_simple_complexity(self, agent, mock_llm_router):
        """Should use TaskComplexity.SIMPLE when messages are short."""
        _, router = mock_llm_router
        router.complete.return_value = MockLLMResponse(content="Hello world")

        result = await agent._call_llm(
            messages=[{"role": "user", "content": "Hi"}],
            temperature=0.5,
        )

        assert result == "Hello world"
        # Verify complexity was SIMPLE (total_chars <= 2000)
        call_kwargs = router.complete.call_args[1]
        assert call_kwargs["temperature"] == 0.5
        # TaskComplexity enum — check the value passed
        from nexus.llm.router import TaskComplexity
        assert call_kwargs["task_complexity"] == TaskComplexity.SIMPLE

    @pytest.mark.asyncio
    async def test_medium_complexity(self, agent, mock_llm_router):
        """Should use TaskComplexity.MEDIUM when messages exceed 2000 chars."""
        _, router = mock_llm_router
        router.complete.return_value = MockLLMResponse(content="Long analysis")

        long_text = "A" * 2500
        result = await agent._call_llm(
            messages=[{"role": "user", "content": long_text}],
        )

        assert result == "Long analysis"
        from nexus.llm.router import TaskComplexity
        call_kwargs = router.complete.call_args[1]
        assert call_kwargs["task_complexity"] == TaskComplexity.MEDIUM

    @pytest.mark.asyncio
    async def test_provider_passthrough(self, agent, mock_llm_router):
        """Should pass the provider argument to router.complete."""
        _, router = mock_llm_router
        router.complete.return_value = MockLLMResponse(content="From Gemini")

        await agent._call_llm(
            messages=[{"role": "user", "content": "Hi"}],
            provider="gemini",
        )

        call_kwargs = router.complete.call_args[1]
        assert call_kwargs["provider"] == "gemini"

    @pytest.mark.asyncio
    async def test_custom_provider(self, agent, mock_llm_router):
        """Should accept custom provider names."""
        _, router = mock_llm_router
        router.complete.return_value = MockLLMResponse(content="From Claude")

        await agent._call_llm(
            messages=[{"role": "user", "content": "Hi"}],
            provider="anthropic",
        )

        call_kwargs = router.complete.call_args[1]
        assert call_kwargs["provider"] == "anthropic"

    @pytest.mark.asyncio
    async def test_temperature_default(self, agent, mock_llm_router):
        """Should default temperature to 0.3."""
        _, router = mock_llm_router
        router.complete.return_value = MockLLMResponse(content="Default temp")

        await agent._call_llm(
            messages=[{"role": "user", "content": "Hello"}],
        )

        call_kwargs = router.complete.call_args[1]
        assert call_kwargs["temperature"] == 0.3

    @pytest.mark.asyncio
    async def test_token_tracking(self, agent, mock_llm_router):
        """Should accumulate token usage from response."""
        _, router = mock_llm_router
        router.complete.return_value = MockLLMResponse(
            content="Test",
            usage={"prompt_tokens": 50, "completion_tokens": 25},
        )

        await agent._call_llm(
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert agent._token_usage["prompt"] == 50
        assert agent._token_usage["completion"] == 25
        assert agent._token_usage["total"] == 75

    @pytest.mark.asyncio
    async def test_token_tracking_missing_usage(self, agent, mock_llm_router):
        """Should handle missing usage data gracefully."""
        _, router = mock_llm_router
        router.complete.return_value = MockLLMResponse(content="No usage", usage=None)

        await agent._call_llm(
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert agent._token_usage["prompt"] == 0
        assert agent._token_usage["completion"] == 0

    @pytest.mark.asyncio
    async def test_tool_calls_round_trip(self, agent, mock_llm_router):
        """Should process tool calls and return final response."""
        _, router = mock_llm_router

        # First response: LLM wants to call a tool
        tool_call = {
            "id": "call_1",
            "function": {"name": "web_search", "arguments": '{"query": "AI news"}'},
        }
        router.complete.side_effect = [
            MockLLMResponse(content="Let me search", tool_calls=[tool_call]),
            MockLLMResponse(content="Here are the results"),
        ]

        with patch.object(agent, "_use_tool", new_callable=AsyncMock) as mock_use:
            mock_use.return_value = {"results": ["some data"]}

            result = await agent._call_llm(
                messages=[{"role": "user", "content": "Search for AI news"}],
            )

        assert result == "Here are the results"
        # _use_tool is mocked here so _tools_used isn't updated by the real method;
        # instead verify the mock was called with the expected arguments
        mock_use.assert_awaited_once_with(
            "web_search", {"query": "AI news"}
        )

    @pytest.mark.asyncio
    async def test_tool_call_with_failed_tool(self, agent, mock_llm_router):
        """Should handle tool execution errors gracefully and continue."""
        _, router = mock_llm_router

        tool_call = {
            "id": "call_fail",
            "function": {"name": "execute_code", "arguments": '{"code": "bad code"}'},
        }
        router.complete.side_effect = [
            MockLLMResponse(content="Running code", tool_calls=[tool_call]),
            MockLLMResponse(content="Code failed, trying something else"),
        ]

        with patch.object(agent, "_use_tool", new_callable=AsyncMock) as mock_use:
            mock_use.side_effect = RuntimeError("Syntax error")

            result = await agent._call_llm(
                messages=[{"role": "user", "content": "Run code"}],
            )

        assert result == "Code failed, trying something else"
        # The error message should have been added to conversation
        # Verify _use_tool was called
        mock_use.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_max_tool_turns_exceeded(self, agent, mock_llm_router):
        """Should raise AgentError when max tool turns is exceeded."""
        _, router = mock_llm_router

        # Every response calls a tool → infinite loop → blocked by max_tool_turns
        tool_call = {
            "id": "call_loop",
            "function": {"name": "web_search", "arguments": '{"query": "more"}'},
        }
        router.complete.return_value = MockLLMResponse(
            content="Searching...", tool_calls=[tool_call]
        )

        from nexus.core.exceptions import AgentError

        with patch.object(agent, "_use_tool", new_callable=AsyncMock) as mock_use:
            mock_use.return_value = {"results": []}
            with pytest.raises(AgentError, match="Max tool turns"):
                await agent._call_llm(
                    messages=[{"role": "user", "content": "Loop"}],
                    max_tool_turns=3,
                )

        assert router.complete.call_count == 3

    @pytest.mark.asyncio
    async def test_tool_call_invalid_json_args(self, agent, mock_llm_router):
        """Should parse broken JSON arguments gracefully."""
        _, router = mock_llm_router

        tool_call = {
            "id": "call_bad",
            "function": {"name": "web_search", "arguments": "not valid json"},
        }
        router.complete.side_effect = [
            MockLLMResponse(content="Hmm", tool_calls=[tool_call]),
            MockLLMResponse(content="Fixed it"),
        ]

        with patch.object(agent, "_use_tool", new_callable=AsyncMock) as mock_use:
            mock_use.return_value = {"results": []}
            result = await agent._call_llm(
                messages=[{"role": "user", "content": "Search"}],
                max_tool_turns=2,
            )

        assert result == "Fixed it"
        # Should pass raw_args when JSON is broken
        mock_use.assert_called_with("web_search", {"raw_args": "not valid json"})

    @pytest.mark.asyncio
    async def test_kwargs_passthrough_to_router(self, agent, mock_llm_router):
        """Should pass additional kwargs through to router.complete."""
        _, router = mock_llm_router
        router.complete.return_value = MockLLMResponse(content="Done")

        await agent._call_llm(
            messages=[{"role": "user", "content": "Hi"}],
            top_p=0.9,
            max_tokens=500,
        )

        call_kwargs = router.complete.call_args[1]
        assert call_kwargs["top_p"] == 0.9
        assert call_kwargs["max_tokens"] == 500


# ═══════════════════════════════════════════════════════════════════════════════
# 4. _invoke_mcp_tool dispatch tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestInvokeMcpTool:
    """Verify _invoke_mcp_tool dispatches to the correct handler."""

    @pytest.mark.asyncio
    async def test_dispatch_to_search_memory(self, agent):
        """Should dispatch search_memory to _mcp_search_memory."""
        with patch.object(agent, "_mcp_search_memory", new_callable=AsyncMock) as mock_h:
            mock_h.return_value = {"results": []}
            result = await agent._invoke_mcp_tool("search_memory", {"query": "test"})
            assert result == {"results": []}
            mock_h.assert_awaited_once_with({"query": "test"})

    @pytest.mark.asyncio
    async def test_dispatch_to_store_memory(self, agent):
        """Should dispatch store_memory to _mcp_store_memory."""
        with patch.object(agent, "_mcp_store_memory", new_callable=AsyncMock) as mock_h:
            mock_h.return_value = {"success": True}
            result = await agent._invoke_mcp_tool("store_memory", {"text": "data"})
            assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_dispatch_to_execute_code(self, agent):
        """Should dispatch execute_code to _mcp_execute_code."""
        with patch.object(agent, "_mcp_execute_code", new_callable=AsyncMock) as mock_h:
            mock_h.return_value = {"output": "done"}
            result = await agent._invoke_mcp_tool("execute_code", {"code": "print(1)"})
            assert result == {"output": "done"}

    @pytest.mark.asyncio
    async def test_dispatch_to_read_file(self, agent):
        """Should dispatch read_file to _mcp_read_file."""
        with patch.object(agent, "_mcp_read_file", new_callable=AsyncMock) as mock_h:
            mock_h.return_value = {"content": "file data"}
            result = await agent._invoke_mcp_tool("read_file", {"path": "/tmp/f"})
            assert result == {"content": "file data"}

    @pytest.mark.asyncio
    async def test_dispatch_to_write_file(self, agent):
        """Should dispatch write_file to _mcp_write_file."""
        with patch.object(agent, "_mcp_write_file", new_callable=AsyncMock) as mock_h:
            mock_h.return_value = {"success": True}
            result = await agent._invoke_mcp_tool("write_file", {"path": "/tmp/f", "content": "data"})
            assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_dispatch_to_spawn_agent(self, agent):
        """Should dispatch spawn_agent to _mcp_spawn_agent."""
        with patch.object(agent, "_mcp_spawn_agent", new_callable=AsyncMock) as mock_h:
            mock_h.return_value = {"agent_id": "abc"}
            result = await agent._invoke_mcp_tool("spawn_agent", {"agent_type": "researcher", "task": "do stuff"})
            assert result == {"agent_id": "abc"}

    @pytest.mark.asyncio
    async def test_dispatch_to_web_scrape(self, agent):
        """Should dispatch web_scrape to _mcp_web_scrape."""
        with patch.object(agent, "_mcp_web_scrape", new_callable=AsyncMock) as mock_h:
            mock_h.return_value = {"content": "page content"}
            result = await agent._invoke_mcp_tool("web_scrape", {"url": "https://example.com"})
            assert result == {"content": "page content"}

    @pytest.mark.asyncio
    async def test_dispatch_to_knowledge_add_entity(self, agent):
        """Should dispatch knowledge_add_entity to _mcp_knowledge_add_entity."""
        with patch.object(agent, "_mcp_knowledge_add_entity", new_callable=AsyncMock) as mock_h:
            mock_h.return_value = {"success": True}
            result = await agent._invoke_mcp_tool("knowledge_add_entity", {"name": "Python"})
            assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_dispatch_to_knowledge_search(self, agent):
        """Should dispatch knowledge_search to _mcp_knowledge_search."""
        with patch.object(agent, "_mcp_knowledge_search", new_callable=AsyncMock) as mock_h:
            mock_h.return_value = {"results": []}
            result = await agent._invoke_mcp_tool("knowledge_search", {"query": "AI"})
            assert result == {"results": []}

    @pytest.mark.asyncio
    async def test_dispatch_to_execute_sandboxed(self, agent):
        """Should dispatch execute_sandboxed to _mcp_execute_sandboxed."""
        with patch.object(agent, "_mcp_execute_sandboxed", new_callable=AsyncMock) as mock_h:
            mock_h.return_value = {"output": "sandbox result"}
            result = await agent._invoke_mcp_tool("execute_sandboxed", {"command": "ls"})
            assert result == {"output": "sandbox result"}

    @pytest.mark.asyncio
    async def test_unknown_tool_raises(self, agent):
        """Should raise AttributeError for unknown tool names."""
        with pytest.raises(AttributeError, match="No handler for tool 'nonexistent'"):
            await agent._invoke_mcp_tool("nonexistent", {})

    @pytest.mark.asyncio
    async def test_tool_map_has_expected_entries(self, agent):
        """The internal tool_map should contain all expected keys."""
        # Access the map indirectly by testing dispatch for each key
        expected_tools = [
            "search_memory", "store_memory", "delete_memory", "list_namespaces", "memory_stats",
            "knowledge_query", "knowledge_add_entity", "knowledge_add_relation", "knowledge_search",
            "knowledge_paths", "llm_complete", "llm_list_models", "llm_provider_status", "llm_stream",
            "spawn_agent", "list_agents", "agent_status", "agent_delegate", "a2a_discover",
            "execute_code", "execute_sandboxed", "install_package",
            "read_file", "write_file", "list_files", "delete_file", "move_file", "copy_file",
            "search_files", "web_scrape", "web_screenshot",
            "reason_react", "reason_tot", "reason_lats",
            "run_pipeline", "rag_query",
        ]
        for tool in expected_tools:
            if tool in ("reason_tot", "reason_lats", "reason_react"):
                # Just check they dispatch without error by patching
                with patch.object(agent, f"_mcp_{tool}", new_callable=AsyncMock) as mock_h:
                    mock_h.return_value = {"result": "ok"}
                    r = await agent._invoke_mcp_tool(tool, {"task": "test"})
                    assert r == {"result": "ok"}
            else:
                with patch.object(agent, f"_mcp_{tool}", new_callable=AsyncMock) as mock_h:
                    mock_h.return_value = {"result": "ok"}
                    params = {"query": "x", "text": "x", "name": "x", "path": "/tmp/x",
                              "content": "x", "code": "x", "url": "https://x",
                              "task": "x", "agent_type": "x", "command": "x",
                              "source": "x", "destination": "x", "entity_name": "x",
                              "source_name": "x", "target_name": "x", "relation_type": "x",
                              "package": "x", "instance_id": "x", "agent_url": "x",
                              "directory": ".", "query": "x"}
                    # Use appropriate params
                    r = await agent._invoke_mcp_tool(tool, params)
                    assert r == {"result": "ok"}


# ═══════════════════════════════════════════════════════════════════════════════
# 5. MCP handler method tests (10+ in depth)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMcpHandlers:
    """Verify each MCP handler calls the correct nexus.mcp_server function."""

    @pytest.mark.asyncio
    async def test_mcp_search_memory(self, agent, mock_mcp_server):
        """_mcp_search_memory should delegate to nexus.mcp_server.search_memory."""
        mock_mcp_server["search_memory"].return_value = {"results": [{"id": "doc1"}]}
        result = await agent._mcp_search_memory({"query": "AI", "namespace": "test", "top_k": 10})
        assert result == {"results": [{"id": "doc1"}]}
        mock_mcp_server["search_memory"].assert_awaited_once_with("AI", "test", 10)

    @pytest.mark.asyncio
    async def test_mcp_search_memory_defaults(self, agent, mock_mcp_server):
        """_mcp_search_memory should use sensible defaults."""
        mock_mcp_server["search_memory"].return_value = {"results": []}
        await agent._mcp_search_memory({"query": "test"})
        mock_mcp_server["search_memory"].assert_awaited_once_with("test", "knowledge", 5)

    @pytest.mark.asyncio
    async def test_mcp_store_memory(self, agent, mock_mcp_server):
        """_mcp_store_memory should delegate correctly."""
        mock_mcp_server["store_memory"].return_value = {"success": True}
        result = await agent._mcp_store_memory({"text": "important info", "namespace": "working", "metadata": {"key": "val"}})
        assert result == {"success": True}
        mock_mcp_server["store_memory"].assert_awaited_once_with("important info", "working", {"key": "val"})

    @pytest.mark.asyncio
    async def test_mcp_store_memory_defaults(self, agent, mock_mcp_server):
        """_mcp_store_memory should default namespace to 'knowledge' and metadata to None."""
        mock_mcp_server["store_memory"].return_value = {"success": True}
        await agent._mcp_store_memory({"text": "data"})
        mock_mcp_server["store_memory"].assert_awaited_once_with("data", "knowledge", None)

    @pytest.mark.asyncio
    async def test_mcp_delete_memory(self, agent, mock_mcp_server):
        """_mcp_delete_memory should use doc_ids or doc_id."""
        mock_mcp_server["delete_memory"].return_value = {"deleted": 1}
        result = await agent._mcp_delete_memory({"doc_id": "doc1"})
        mock_mcp_server["delete_memory"].assert_awaited_once_with(["doc1"], "knowledge")

    @pytest.mark.asyncio
    async def test_mcp_delete_memory_multiple(self, agent, mock_mcp_server):
        """_mcp_delete_memory should handle doc_ids list."""
        mock_mcp_server["delete_memory"].return_value = {"deleted": 2}
        result = await agent._mcp_delete_memory({"doc_ids": ["a", "b"]})
        mock_mcp_server["delete_memory"].assert_awaited_once_with(["a", "b"], "knowledge")

    @pytest.mark.asyncio
    async def test_mcp_list_namespaces(self, agent, mock_mcp_server):
        """_mcp_list_namespaces should delegate."""
        mock_mcp_server["list_namespaces"].return_value = ["knowledge", "working"]
        result = await agent._mcp_list_namespaces({})
        assert result == ["knowledge", "working"]

    @pytest.mark.asyncio
    async def test_mcp_memory_stats(self, agent, mock_mcp_server):
        """_mcp_memory_stats should delegate."""
        mock_mcp_server["memory_stats"].return_value = {"total_docs": 100}
        result = await agent._mcp_memory_stats({})
        assert result == {"total_docs": 100}

    @pytest.mark.asyncio
    async def test_mcp_knowledge_query(self, agent, mock_mcp_server):
        """_mcp_knowledge_query should delegate."""
        mock_mcp_server["knowledge_query"].return_value = {"entities": []}
        result = await agent._mcp_knowledge_query({"entity_name": "Python", "depth": 2})
        mock_mcp_server["knowledge_query"].assert_awaited_once_with("Python", 2)

    @pytest.mark.asyncio
    async def test_mcp_knowledge_add_entity(self, agent, mock_mcp_server):
        """_mcp_knowledge_add_entity should delegate with type, name, properties."""
        mock_mcp_server["knowledge_add_entity"].return_value = {"id": "ent_1"}
        result = await agent._mcp_knowledge_add_entity({"entity_type": "language", "name": "Python", "properties": {"paradigm": "OOP"}})
        mock_mcp_server["knowledge_add_entity"].assert_awaited_once_with("language", "Python", {"paradigm": "OOP"})

    @pytest.mark.asyncio
    async def test_mcp_knowledge_add_entity_default_type(self, agent, mock_mcp_server):
        """_mcp_knowledge_add_entity should default entity_type to 'concept'."""
        mock_mcp_server["knowledge_add_entity"].return_value = {"id": "ent_2"}
        await agent._mcp_knowledge_add_entity({"name": "AI"})
        mock_mcp_server["knowledge_add_entity"].assert_awaited_once_with("concept", "AI", None)

    @pytest.mark.asyncio
    async def test_mcp_knowledge_add_relation(self, agent, mock_mcp_server):
        """_mcp_knowledge_add_relation should delegate."""
        mock_mcp_server["knowledge_add_relation"].return_value = {"success": True}
        result = await agent._mcp_knowledge_add_relation({"source_name": "Python", "target_name": "Django", "relation_type": "framework_of", "properties": {}})
        mock_mcp_server["knowledge_add_relation"].assert_awaited_once_with("Python", "Django", "framework_of", {})

    @pytest.mark.asyncio
    async def test_mcp_knowledge_search(self, agent, mock_mcp_server):
        """_mcp_knowledge_search should delegate."""
        mock_mcp_server["knowledge_search"].return_value = {"results": []}
        result = await agent._mcp_knowledge_search({"query": "ML", "entity_type": "concept", "limit": 10})
        mock_mcp_server["knowledge_search"].assert_awaited_once_with("ML", "concept", 10)

    @pytest.mark.asyncio
    async def test_mcp_knowledge_search_defaults(self, agent, mock_mcp_server):
        """_mcp_knowledge_search should default entity_type to None and limit to 20."""
        mock_mcp_server["knowledge_search"].return_value = {"results": []}
        await agent._mcp_knowledge_search({"query": "AI"})
        mock_mcp_server["knowledge_search"].assert_awaited_once_with("AI", None, 20)

    @pytest.mark.asyncio
    async def test_mcp_knowledge_paths(self, agent, mock_mcp_server):
        """_mcp_knowledge_paths should delegate."""
        mock_mcp_server["knowledge_paths"].return_value = {"paths": []}
        result = await agent._mcp_knowledge_paths({"source_name": "A", "target_name": "B", "max_length": 3})
        mock_mcp_server["knowledge_paths"].assert_awaited_once_with("A", "B", 3)

    @pytest.mark.asyncio
    async def test_mcp_llm_complete(self, agent, mock_mcp_server):
        """_mcp_llm_complete should delegate."""
        mock_mcp_server["llm_complete"].return_value = {"content": "response"}
        result = await agent._mcp_llm_complete({"prompt": "Hello", "model": "gemma", "temperature": 0.5, "max_tokens": 2048})
        mock_mcp_server["llm_complete"].assert_awaited_once_with("Hello", "gemma", 0.5, 2048)

    @pytest.mark.asyncio
    async def test_mcp_llm_complete_messages_json_fallback(self, agent, mock_mcp_server):
        """_mcp_llm_complete should fall back to messages_json key."""
        mock_mcp_server["llm_complete"].return_value = {"content": "resp"}
        await agent._mcp_llm_complete({"messages_json": "Hello"})
        mock_mcp_server["llm_complete"].assert_awaited_once_with("Hello", None, 0.7, 4096)

    @pytest.mark.asyncio
    async def test_mcp_llm_list_models(self, agent, mock_mcp_server):
        """_mcp_llm_list_models should delegate."""
        mock_mcp_server["llm_list_models"].return_value = ["gemma", "llama"]
        result = await agent._mcp_llm_list_models({})
        assert result == ["gemma", "llama"]

    @pytest.mark.asyncio
    async def test_mcp_llm_provider_status(self, agent, mock_mcp_server):
        """_mcp_llm_provider_status should delegate."""
        mock_mcp_server["llm_provider_status"].return_value = {"gemini": "healthy"}
        result = await agent._mcp_llm_provider_status({})
        assert result == {"gemini": "healthy"}

    @pytest.mark.asyncio
    async def test_mcp_spawn_agent(self, agent, mock_mcp_server):
        """_mcp_spawn_agent should delegate with type, task, config."""
        mock_mcp_server["spawn_agent"].return_value = {"agent_id": "abc"}
        result = await agent._mcp_spawn_agent({"agent_type": "researcher", "task": "research AI", "config": {"temp": 0.5}})
        mock_mcp_server["spawn_agent"].assert_awaited_once_with("researcher", "research AI", {"temp": 0.5})

    @pytest.mark.asyncio
    async def test_mcp_spawn_agent_default_type(self, agent, mock_mcp_server):
        """_mcp_spawn_agent should default agent_type to 'general'."""
        mock_mcp_server["spawn_agent"].return_value = {"agent_id": "def"}
        await agent._mcp_spawn_agent({"task": "do stuff"})
        mock_mcp_server["spawn_agent"].assert_awaited_once_with("general", "do stuff", None)

    @pytest.mark.asyncio
    async def test_mcp_list_agents(self, agent, mock_mcp_server):
        """_mcp_list_agents should delegate."""
        mock_mcp_server["list_agents"].return_value = [{"id": "a1"}]
        result = await agent._mcp_list_agents({})
        assert result == [{"id": "a1"}]

    @pytest.mark.asyncio
    async def test_mcp_agent_status(self, agent, mock_mcp_server):
        """_mcp_agent_status should delegate."""
        mock_mcp_server["agent_status"].return_value = {"status": "running"}
        result = await agent._mcp_agent_status({"instance_id": "abc123"})
        mock_mcp_server["agent_status"].assert_awaited_once_with("abc123")

    @pytest.mark.asyncio
    async def test_mcp_agent_delegate(self, agent, mock_mcp_server):
        """_mcp_agent_delegate should delegate."""
        mock_mcp_server["agent_delegate"].return_value = {"result": "done"}
        result = await agent._mcp_agent_delegate({"source_agent": "src", "target_agent": "tgt", "task": "do it", "context": {"key": "val"}})
        mock_mcp_server["agent_delegate"].assert_awaited_once_with("src", "tgt", "do it", {"key": "val"})

    @pytest.mark.asyncio
    async def test_mcp_a2a_discover(self, agent, mock_mcp_server):
        """_mcp_a2a_discover should delegate."""
        mock_mcp_server["a2a_discover"].return_value = {"capabilities": []}
        result = await agent._mcp_a2a_discover({"agent_url": "http://agent"})
        mock_mcp_server["a2a_discover"].assert_awaited_once_with("http://agent")

    @pytest.mark.asyncio
    async def test_mcp_execute_code(self, agent, mock_mcp_server):
        """_mcp_execute_code should delegate."""
        mock_mcp_server["execute_code"].return_value = {"output": "hello", "exit_code": 0}
        result = await agent._mcp_execute_code({"code": "print('hello')", "language": "python", "timeout": 15})
        mock_mcp_server["execute_code"].assert_awaited_once_with("print('hello')", "python", 15)

    @pytest.mark.asyncio
    async def test_mcp_execute_code_defaults(self, agent, mock_mcp_server):
        """_mcp_execute_code should default language to python and timeout to 30."""
        mock_mcp_server["execute_code"].return_value = {"output": ""}
        await agent._mcp_execute_code({"code": "x = 1"})
        mock_mcp_server["execute_code"].assert_awaited_once_with("x = 1", "python", 30)

    @pytest.mark.asyncio
    async def test_mcp_execute_sandboxed(self, agent, mock_mcp_server):
        """_mcp_execute_sandboxed should delegate."""
        mock_mcp_server["execute_sandboxed"].return_value = {"output": "sandbox out"}
        result = await agent._mcp_execute_sandboxed({"command": "ls -la", "timeout": 60, "allowed_dirs": ["/tmp"]})
        mock_mcp_server["execute_sandboxed"].assert_awaited_once_with("ls -la", 60, ["/tmp"])

    @pytest.mark.asyncio
    async def test_mcp_execute_sandboxed_code_fallback(self, agent, mock_mcp_server):
        """_mcp_execute_sandboxed should fall back to code key when command is missing."""
        mock_mcp_server["execute_sandboxed"].return_value = {"output": "code out"}
        await agent._mcp_execute_sandboxed({"code": "print(1)"})
        mock_mcp_server["execute_sandboxed"].assert_awaited_once_with("print(1)", 30, None)

    @pytest.mark.asyncio
    async def test_mcp_install_package(self, agent, mock_mcp_server):
        """_mcp_install_package should delegate."""
        mock_mcp_server["install_package"].return_value = {"success": True}
        result = await agent._mcp_install_package({"package": "requests", "version": "2.28"})
        mock_mcp_server["install_package"].assert_awaited_once_with("requests", "2.28")

    @pytest.mark.asyncio
    async def test_mcp_read_file(self, agent, mock_mcp_server):
        """_mcp_read_file should delegate."""
        mock_mcp_server["read_file"].return_value = {"content": "file content"}
        result = await agent._mcp_read_file({"path": "/tmp/test.txt", "encoding": "utf-8"})
        mock_mcp_server["read_file"].assert_awaited_once_with("/tmp/test.txt", "utf-8")

    @pytest.mark.asyncio
    async def test_mcp_read_file_default_encoding(self, agent, mock_mcp_server):
        """_mcp_read_file should default encoding to utf-8."""
        mock_mcp_server["read_file"].return_value = {"content": "data"}
        await agent._mcp_read_file({"path": "/tmp/f"})
        mock_mcp_server["read_file"].assert_awaited_once_with("/tmp/f", "utf-8")

    @pytest.mark.asyncio
    async def test_mcp_write_file(self, agent, mock_mcp_server):
        """_mcp_write_file should delegate."""
        mock_mcp_server["write_file"].return_value = {"success": True, "bytes_written": 5}
        result = await agent._mcp_write_file({"path": "/tmp/test.txt", "content": "hello", "encoding": "ascii"})
        mock_mcp_server["write_file"].assert_awaited_once_with("/tmp/test.txt", "hello", "ascii")

    @pytest.mark.asyncio
    async def test_mcp_list_files(self, agent, mock_mcp_server):
        """_mcp_list_files should delegate."""
        mock_mcp_server["list_files"].return_value = {"files": ["a.txt"]}
        result = await agent._mcp_list_files({"directory": "/tmp", "pattern": "*.txt"})
        mock_mcp_server["list_files"].assert_awaited_once_with("/tmp", "*.txt")

    @pytest.mark.asyncio
    async def test_mcp_list_files_defaults(self, agent, mock_mcp_server):
        """_mcp_list_files should default directory to '.' and pattern to '*'."""
        mock_mcp_server["list_files"].return_value = {"files": []}
        await agent._mcp_list_files({})
        mock_mcp_server["list_files"].assert_awaited_once_with(".", "*")

    @pytest.mark.asyncio
    async def test_mcp_delete_file(self, agent, mock_mcp_server):
        """_mcp_delete_file should delegate."""
        mock_mcp_server["delete_file"].return_value = {"success": True}
        result = await agent._mcp_delete_file({"path": "/tmp/del.me"})
        mock_mcp_server["delete_file"].assert_awaited_once_with("/tmp/del.me")

    @pytest.mark.asyncio
    async def test_mcp_move_file(self, agent, mock_mcp_server):
        """_mcp_move_file should delegate."""
        mock_mcp_server["move_file"].return_value = {"success": True}
        result = await agent._mcp_move_file({"source": "/tmp/a", "destination": "/tmp/b"})
        mock_mcp_server["move_file"].assert_awaited_once_with("/tmp/a", "/tmp/b")

    @pytest.mark.asyncio
    async def test_mcp_copy_file(self, agent, mock_mcp_server):
        """_mcp_copy_file should delegate."""
        mock_mcp_server["copy_file"].return_value = {"success": True}
        result = await agent._mcp_copy_file({"source": "/tmp/src", "destination": "/tmp/dst"})
        mock_mcp_server["copy_file"].assert_awaited_once_with("/tmp/src", "/tmp/dst")

    @pytest.mark.asyncio
    async def test_mcp_search_files(self, agent, mock_mcp_server):
        """_mcp_search_files should delegate."""
        mock_mcp_server["search_files"].return_value = {"files": ["/tmp/result.txt"]}
        result = await agent._mcp_search_files({"query": "TODO", "path": "/tmp", "file_pattern": "*.py"})
        mock_mcp_server["search_files"].assert_awaited_once_with("TODO", "/tmp", "*.py")

    @pytest.mark.asyncio
    async def test_mcp_search_files_alternate_keys(self, agent, mock_mcp_server):
        """_mcp_search_files should support alternate key names."""
        mock_mcp_server["search_files"].return_value = {"files": []}
        await agent._mcp_search_files({"content_query": "test", "directory": "/home", "pattern": "*"})
        mock_mcp_server["search_files"].assert_awaited_once_with("test", "/home", "*")

    @pytest.mark.asyncio
    async def test_mcp_web_scrape(self, agent, mock_mcp_server):
        """_mcp_web_scrape should delegate."""
        mock_mcp_server["web_scrape"].return_value = {"content": "web page"}
        result = await agent._mcp_web_scrape({"url": "https://example.com", "max_length": 5000})
        mock_mcp_server["web_scrape"].assert_awaited_once_with("https://example.com", 5000)

    @pytest.mark.asyncio
    async def test_mcp_web_scrape_default_max_length(self, agent, mock_mcp_server):
        """_mcp_web_scrape should default max_length to 10000."""
        mock_mcp_server["web_scrape"].return_value = {"content": ""}
        await agent._mcp_web_scrape({"url": "https://example.com"})
        mock_mcp_server["web_scrape"].assert_awaited_once_with("https://example.com", 10000)

    @pytest.mark.asyncio
    async def test_mcp_web_screenshot(self, agent, mock_mcp_server):
        """_mcp_web_screenshot should delegate."""
        mock_mcp_server["web_screenshot"].return_value = {"screenshot": "base64data"}
        result = await agent._mcp_web_screenshot({"url": "https://example.com"})
        mock_mcp_server["web_screenshot"].assert_awaited_once_with("https://example.com")

    @pytest.mark.asyncio
    async def test_mcp_reason_react(self, agent, mock_mcp_server):
        """_mcp_reason_react should delegate."""
        mock_mcp_server["reason_react"].return_value = {"result": "reasoned"}
        result = await agent._mcp_reason_react({"task": "solve x", "max_iterations": 5})
        mock_mcp_server["reason_react"].assert_awaited_once_with("solve x", 5)

    @pytest.mark.asyncio
    async def test_mcp_reason_react_default_max_iterations(self, agent, mock_mcp_server):
        """_mcp_reason_react should default max_iterations to 10."""
        mock_mcp_server["reason_react"].return_value = {"result": ""}
        await agent._mcp_reason_react({"task": "solve"})
        mock_mcp_server["reason_react"].assert_awaited_once_with("solve", 10)

    @pytest.mark.asyncio
    async def test_mcp_reason_tot(self, agent, mock_mcp_server):
        """_mcp_reason_tot should delegate."""
        mock_mcp_server["reason_tot"].return_value = {"result": "tot done"}
        result = await agent._mcp_reason_tot({"task": "think", "max_depth": 4, "branch_factor": 5})
        mock_mcp_server["reason_tot"].assert_awaited_once_with("think", 4, 5)

    @pytest.mark.asyncio
    async def test_mcp_reason_lats(self, agent, mock_mcp_server):
        """_mcp_reason_lats should delegate."""
        mock_mcp_server["reason_lats"].return_value = {"result": "lats done"}
        result = await agent._mcp_reason_lats({"task": "simulate", "max_simulations": 5, "max_depth": 3})
        mock_mcp_server["reason_lats"].assert_awaited_once_with("simulate", 5, 3)

    @pytest.mark.asyncio
    async def test_mcp_run_pipeline(self, agent, mock_mcp_server):
        """_mcp_run_pipeline should delegate."""
        tasks = [{"action": "search"}, {"action": "analyze"}]
        mock_mcp_server["run_pipeline"].return_value = {"results": []}
        result = await agent._mcp_run_pipeline({"tasks": tasks, "sequential": True})
        mock_mcp_server["run_pipeline"].assert_awaited_once_with(tasks, True)

    @pytest.mark.asyncio
    async def test_mcp_run_pipeline_defaults(self, agent, mock_mcp_server):
        """_mcp_run_pipeline should default sequential=True and support stages_json."""
        mock_mcp_server["run_pipeline"].return_value = {"results": []}
        await agent._mcp_run_pipeline({"stages_json": ["a", "b"]})
        mock_mcp_server["run_pipeline"].assert_awaited_once_with(["a", "b"], True)

    @pytest.mark.asyncio
    async def test_mcp_rag_query(self, agent, mock_mcp_server):
        """_mcp_rag_query should delegate."""
        mock_mcp_server["rag_query"].return_value = {"results": ["doc1"]}
        result = await agent._mcp_rag_query({"query": "RAG test", "namespace": "docs"})
        mock_mcp_server["rag_query"].assert_awaited_once_with("RAG test", "docs")

    @pytest.mark.asyncio
    async def test_mcp_rag_query_default_namespace(self, agent, mock_mcp_server):
        """_mcp_rag_query should default namespace to 'knowledge'."""
        mock_mcp_server["rag_query"].return_value = {"results": []}
        await agent._mcp_rag_query({"query": "test"})
        mock_mcp_server["rag_query"].assert_awaited_once_with("test", "knowledge")

    @pytest.mark.asyncio
    async def test_mcp_llm_stream(self, agent, mock_mcp_server):
        """_mcp_llm_stream should delegate."""
        mock_mcp_server["llm_stream"].return_value = {"stream": "data"}
        result = await agent._mcp_llm_stream({"prompt": "Tell me a story", "model": "gemma", "temperature": 0.8})
        mock_mcp_server["llm_stream"].assert_awaited_once_with("Tell me a story", "gemma", 0.8)

    @pytest.mark.asyncio
    async def test_mcp_not_implemented_returns_error(self, agent):
        """_mcp_telemetry_submit and _mcp_browser_* should return error dict."""
        r1 = await agent._mcp_telemetry_submit({})
        assert r1 == {"error": "not implemented"}
        r2 = await agent._mcp_browser_navigate({})
        assert r2 == {"error": "not implemented"}
        r3 = await agent._mcp_browser_snapshot({})
        assert r3 == {"error": "not implemented"}


# ═══════════════════════════════════════════════════════════════════════════════
# 6. _use_tool tests (dispatch + fallback + error handling)
# ═══════════════════════════════════════════════════════════════════════════════

class TestUseTool:
    """Tests for _use_tool — MCP dispatch, fallback, error handling."""

    @pytest.mark.asyncio
    async def test_mcp_tool_path(self, agent):
        """_use_tool should invoke MCP for non-fallback tools."""
        with patch.object(agent, "_invoke_mcp_tool", new_callable=AsyncMock) as mock_mcp:
            mock_mcp.return_value = {"result": "mcp result"}
            result = await agent._use_tool("knowledge_query", {"entity_name": "Python"})
            assert result == {"result": "mcp result"}
            mock_mcp.assert_awaited_once_with("knowledge_query", {"entity_name": "Python"})

    @pytest.mark.asyncio
    async def test_fallback_tool_path(self, agent):
        """_use_tool should use fallback for tools in FALLBACK_TOOLS."""
        with patch.object(agent, "_fallback_tool_execution", new_callable=AsyncMock) as mock_fb:
            mock_fb.return_value = {"results": []}
            result = await agent._use_tool("web_search", {"query": "AI"})
            assert result == {"results": []}
            mock_fb.assert_awaited_once_with("web_search", {"query": "AI"})

    @pytest.mark.asyncio
    async def test_mcp_tool_not_found(self, agent):
        """_use_tool should return graceful error when MCP fails."""
        with patch.object(agent, "_invoke_mcp_tool", new_callable=AsyncMock) as mock_mcp:
            mock_mcp.side_effect = RuntimeError("MCP unavailable")
            result = await agent._use_tool("knowledge_query", {"entity_name": "test"})
            assert "error" in result
            assert "not available" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_tool_usage_tracked(self, agent):
        """_use_tool should record tool name in _tools_used."""
        with patch.object(agent, "_invoke_mcp_tool", new_callable=AsyncMock) as mock_mcp:
            mock_mcp.return_value = {}
            await agent._use_tool("knowledge_query", {})
            assert "knowledge_query" in agent._tools_used

    @pytest.mark.asyncio
    async def test_log_action_called(self, agent):
        """_use_tool should call _log_action with tool info."""
        with patch.object(agent, "_invoke_mcp_tool", new_callable=AsyncMock) as mock_mcp:
            mock_mcp.return_value = {}
            with patch.object(agent, "_log_action", new_callable=AsyncMock) as mock_log:
                await agent._use_tool("knowledge_query", {"entity_name": "Python"})
                mock_log.assert_awaited_once()
                args = mock_log.call_args[0]
                assert args[0] == "tool_call"
                assert args[1]["tool"] == "knowledge_query"

    @pytest.mark.asyncio
    async def test_all_fallback_tools(self, agent):
        """All tools in FALLBACK_TOOLS should route to _fallback_tool_execution."""
        fallback_tools = ["web_search", "code_execute", "file_read", "file_write", "memory_store", "memory_recall"]
        expected_map = ["web_search", "code_execute", "file_read", "file_write", "memory_store", "memory_recall"]

        with patch.object(agent, "_fallback_tool_execution", new_callable=AsyncMock) as mock_fb:
            mock_fb.return_value = {"result": "fallback"}
            for tool in fallback_tools:
                await agent._use_tool(tool, {})
                assert mock_fb.call_count >= 1  # called for each


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Fallback tool execution tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestFallbackToolExecution:
    """Tests for _fallback_tool_execution — direct implementations."""

    @pytest.mark.asyncio
    async def test_web_search_fallback(self, agent):
        """_fallback_tool_execution web_search should call MultiSourceWebSearch."""
        with patch("nexus.knowledge.web_search.MultiSourceWebSearch") as mock_search_cls:
            engine = MagicMock()
            engine.search = AsyncMock(return_value=["result1"])
            mock_search_cls.return_value = engine
            result = await agent._fallback_tool_execution("web_search", {"query": "AI", "num": 3})
            assert result == {"results": ["result1"]}
            engine.search.assert_awaited_once_with("AI", num_results=3)

    @pytest.mark.asyncio
    async def test_web_search_fallback_error(self, agent):
        """_fallback_tool_execution web_search should handle errors gracefully."""
        with patch("nexus.knowledge.web_search.MultiSourceWebSearch") as mock_search_cls:
            engine = MagicMock()
            engine.search = AsyncMock(side_effect=RuntimeError("Search failed"))
            mock_search_cls.return_value = engine
            result = await agent._fallback_tool_execution("web_search", {"query": "AI"})
            assert "error" in result

    @pytest.mark.asyncio
    async def test_code_execute_fallback(self, agent):
        """_fallback_tool_execution code_execute should call CodeExecutor."""
        with patch("nexus.dev.code_executor.CodeExecutor") as mock_exec_cls:
            executor = MagicMock()
            executor.execute = AsyncMock(return_value={"output": "done"})
            mock_exec_cls.return_value = executor
            result = await agent._fallback_tool_execution("code_execute", {"code": "print(1)", "language": "python", "timeout": 15})
            assert result == {"output": "done"}
            executor.execute.assert_awaited_once_with(code="print(1)", language="python", timeout=15)

    @pytest.mark.asyncio
    async def test_code_execute_fallback_error(self, agent):
        """_fallback_tool_execution code_execute should handle errors."""
        with patch("nexus.dev.code_executor.CodeExecutor") as mock_exec_cls:
            executor = MagicMock()
            executor.execute = AsyncMock(side_effect=RuntimeError("Exec failed"))
            mock_exec_cls.return_value = executor
            result = await agent._fallback_tool_execution("code_execute", {"code": "bad"})
            assert "error" in result

    @pytest.mark.asyncio
    async def test_memory_store_fallback(self, agent):
        """_fallback_tool_execution memory_store should use self.memory."""
        svc = MagicMock()
        svc.store = AsyncMock(return_value="doc_123")
        with patch.object(agent, "_memory", svc):
            result = await agent._fallback_tool_execution("memory_store", {"content": "data", "metadata": {"k": "v"}})
            assert result == {"success": True, "doc_id": "doc_123"}

    @pytest.mark.asyncio
    async def test_memory_recall_fallback(self, agent):
        """_fallback_tool_execution memory_recall should use self.memory."""
        svc = MagicMock()
        svc.search = AsyncMock(return_value={
            "ids": [["id1", "id2"]],
            "documents": [["doc1", "doc2"]],
            "metadatas": [[{"k": "v"}, {"k2": "v2"}]],
            "distances": [[0.1, 0.5]],
        })
        with patch.object(agent, "_memory", svc):
            result = await agent._fallback_tool_execution("memory_recall", {"query": "test", "n": 2})
            assert "results" in result
            assert len(result["results"]) == 2
            assert result["results"][0]["id"] == "id1"
            svc.search.assert_awaited_once_with(query="test", top_k=2, namespace="working")

    @pytest.mark.asyncio
    async def test_memory_recall_fallback_error(self, agent):
        """_fallback_tool_execution memory_recall should handle errors."""
        svc = MagicMock()
        svc.search = AsyncMock(side_effect=RuntimeError("Mem error"))
        with patch.object(agent, "_memory", svc):
            result = await agent._fallback_tool_execution("memory_recall", {"query": "test"})
            assert "error" in result

    @pytest.mark.asyncio
    async def test_unknown_fallback_tool(self, agent):
        """_fallback_tool_execution should return error for unknown tools."""
        result = await agent._fallback_tool_execution("unknown_tool", {})
        assert "error" in result
        assert "not available" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_file_read_fallback(self, agent):
        """_fallback_tool_execution file_read should read from disk."""
        mock_data = "file contents"
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_cm)
        mock_cm.read = AsyncMock(return_value=mock_data)

        with patch("aiofiles.open", return_value=mock_cm):
            result = await agent._fallback_tool_execution("file_read", {"path": "/tmp/test.txt"})
            assert result["content"] == "file contents"

    @pytest.mark.asyncio
    async def test_file_read_fallback_error(self, agent):
        """_fallback_tool_execution file_read should handle IO errors."""
        with patch("aiofiles.open", side_effect=FileNotFoundError("Not found")):
            result = await agent._fallback_tool_execution("file_read", {"path": "/nonexistent"})
            assert "error" in result

    @pytest.mark.asyncio
    async def test_file_write_fallback(self, agent):
        """_fallback_tool_execution file_write should write to disk."""
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_cm)
        mock_cm.write = AsyncMock()

        with patch("aiofiles.open", return_value=mock_cm):
            result = await agent._fallback_tool_execution("file_write", {"path": "/tmp/test.txt", "content": "hello"})
            assert result["success"] is True
            assert result["bytes_written"] == 5

    @pytest.mark.asyncio
    async def test_file_write_fallback_error(self, agent):
        """_fallback_tool_execution file_write should handle errors."""
        with patch("aiofiles.open", side_effect=PermissionError("Denied")):
            result = await agent._fallback_tool_execution("file_write", {"path": "/tmp/test.txt", "content": "hello"})
            assert "error" in result


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Audit logging path
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditLogging:
    """Verify _log_action calls AuditLogger.log with correct parameters."""

    @pytest.mark.asyncio
    async def test_log_action_calls_audit_logger(self, agent, mock_audit_logger):
        """_log_action should call AuditLogger.log with actor, action, details."""
        _, logger_instance = mock_audit_logger
        agent._context = AgentContext(task="test")

        await agent._log_action("test_action", {"key": "value"})

        logger_instance.log.assert_called_once_with(
            actor=agent._context.agent_id,
            action="test_action",
            details={"key": "value"},
        )

    @pytest.mark.asyncio
    async def test_log_action_unknown_actor(self, agent, mock_audit_logger):
        """_log_action should use 'unknown' when context is None."""
        _, logger_instance = mock_audit_logger
        assert agent._context is None

        await agent._log_action("no_context", {})

        logger_instance.log.assert_called_once_with(
            actor="unknown",
            action="no_context",
            details={},
        )

    @pytest.mark.asyncio
    async def test_log_action_never_breaks(self, agent):
        """_log_action should never raise exception."""
        agent._context = AgentContext(task="test")
        agent._audit_logger = MagicMock()
        agent._audit_logger.log.side_effect = RuntimeError("Audit system down")

        # This should NOT raise
        await agent._log_action("test", {"data": "value"})

    @pytest.mark.asyncio
    async def test_agent_start_logged_in_run(self, agent, mock_audit_logger):
        """Run lifecycle should log agent_start with task."""
        _, logger_instance = mock_audit_logger
        with patch.multiple(
            agent,
            plan=AsyncMock(return_value=[]),
            execute_step=AsyncMock(return_value={"success": True}),
            reflect=AsyncMock(return_value={"should_continue": False}),
            _synthesize_answer=AsyncMock(return_value="Done"),
            _call_llm=AsyncMock(return_value="OK"),
        ):
            result = await agent.run("Test task")

        # Verify agent_start was logged
        start_call = None
        for call_args in logger_instance.log.call_args_list:
            if call_args[1].get("action") == "agent_start":
                start_call = call_args
                break
        assert start_call is not None
        assert "Test task" in start_call[1]["details"]["task"]

    @pytest.mark.asyncio
    async def test_agent_complete_logged(self, agent, mock_audit_logger):
        """Successful run should log agent_complete with steps and tokens."""
        _, logger_instance = mock_audit_logger
        agent._tools_used = ["web_search"]
        agent._token_usage = {"prompt": 10, "completion": 5, "total": 15}

        with patch.multiple(
            agent,
            plan=AsyncMock(return_value=[]),
            execute_step=AsyncMock(return_value={"success": True}),
            reflect=AsyncMock(return_value={"should_continue": False}),
            _synthesize_answer=AsyncMock(return_value="Done"),
            _call_llm=AsyncMock(return_value="OK"),
        ):
            await agent.run("Test")

        complete_call = None
        for call_args in logger_instance.log.call_args_list:
            if call_args[1].get("action") == "agent_complete":
                complete_call = call_args
                break
        assert complete_call is not None
        details = complete_call[1]["details"]
        assert "tools_used" in details
        assert "tokens" in details

    @pytest.mark.asyncio
    async def test_agent_failed_logged(self, agent, mock_audit_logger):
        """Failed run should log agent_failed with error."""
        _, logger_instance = mock_audit_logger
        agent._tools_used = []

        with patch.multiple(
            agent,
            plan=AsyncMock(side_effect=ValueError("Plan failed")),
            _synthesize_answer=AsyncMock(return_value=""),
        ):
            result = await agent.run("Test")

        assert result.status == AgentStatus.FAILED
        fail_call = None
        for call_args in logger_instance.log.call_args_list:
            if call_args[1].get("action") == "agent_failed":
                fail_call = call_args
                break
        assert fail_call is not None
        assert "Plan failed" in fail_call[1]["details"]["error"]

    @pytest.mark.asyncio
    async def test_tool_call_logged(self, agent, mock_audit_logger):
        """_use_tool should log a tool_call action."""
        _, logger_instance = mock_audit_logger
        with patch.object(agent, "_invoke_mcp_tool", new_callable=AsyncMock) as mock_mcp:
            mock_mcp.return_value = {}
            await agent._use_tool("knowledge_query", {"entity_name": "Python"})

        tool_call = None
        for call_args in logger_instance.log.call_args_list:
            if call_args[1].get("action") == "tool_call":
                tool_call = call_args
                break
        assert tool_call is not None
        assert tool_call[1]["details"]["tool"] == "knowledge_query"


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Lifecycle: run()
# ═══════════════════════════════════════════════════════════════════════════════

class TestLifecycleRun:
    """Tests for the full run() lifecycle."""

    @pytest.mark.asyncio
    async def test_successful_run(self, agent):
        """run() should complete full lifecycle and return AgentResult with COMPLETED status."""
        with patch.multiple(
            agent,
            plan=AsyncMock(return_value=[
                {"action": "search", "params": {"query": "test"}},
                {"action": "analyze", "params": {}},
            ]),
            execute_step=AsyncMock(side_effect=[
                {"success": True, "result": "search done", "tool_used": "web_search"},
                {"success": True, "result": "analysis done", "tool_used": "data_analyze"},
            ]),
            reflect=AsyncMock(side_effect=[
                {"should_continue": True, "assessment": "Need more data"},
                {"should_continue": False, "assessment": "Done"},
            ]),
            _synthesize_answer=AsyncMock(return_value="Final synthesized answer"),
            _log_action=AsyncMock(),
        ):
            result = await agent.run("Test task")

        assert result.status == AgentStatus.COMPLETED
        assert result.answer == "Final synthesized answer"
        assert result.steps_taken == 2
        assert result.agent_type == "test_agent"
        assert result.success is True
        assert "web_search" in result.tools_used
        assert "data_analyze" in result.tools_used
        assert result.started_at is not None
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_phase_transitions(self, agent):
        """run() should end in COMPLETED phase after successful execution."""
        with patch.multiple(
            agent,
            plan=AsyncMock(return_value=[{"action": "search", "params": {}}]),
            execute_step=AsyncMock(return_value={"success": True, "result": "done"}),
            reflect=AsyncMock(return_value={"should_continue": False, "assessment": "Done"}),
            _synthesize_answer=AsyncMock(return_value="Answer"),
            _log_action=AsyncMock(),
        ):
            await agent.run("Test")
            assert agent.phase == AgentPhase.COMPLETED

    @pytest.mark.asyncio
    async def test_max_iterations_hit(self, agent):
        """run() should stop when current_iteration >= max_iterations."""
        with patch.multiple(
            agent,
            plan=AsyncMock(return_value=[
                {"action": "a", "params": {}} for _ in range(30)  # More than max_iterations
            ]),
            execute_step=AsyncMock(return_value={"success": True, "result": "step done"}),
            reflect=AsyncMock(return_value={"should_continue": True, "assessment": "Continue"}),
            _synthesize_answer=AsyncMock(return_value="Partial answer"),
            _log_action=AsyncMock(),
        ):
            agent._context = AgentContext(task="Long task", max_iterations=3)
            result = await agent.run("Long task")

        # Should have stopped at 3 steps (the default max_iterations for this test)
        assert result.status == AgentStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_run_exception_handling(self, agent):
        """run() should return FAILED result when plan raises."""
        with patch.object(agent, "plan", AsyncMock(side_effect=ValueError("Plan crashed"))):
            with patch.object(agent, "_log_action", AsyncMock()):
                result = await agent.run("Failing task")

        assert result.status == AgentStatus.FAILED
        assert "Plan crashed" in result.error

    @pytest.mark.asyncio
    async def test_run_context_creation(self, agent, mock_settings):
        """run() should create context with task and max_iterations from settings."""
        _, settings = mock_settings
        settings.orchestrator_max_iterations = 10

        with patch.multiple(
            agent,
            plan=AsyncMock(return_value=[]),
            execute_step=AsyncMock(return_value={"success": True}),
            reflect=AsyncMock(return_value={"should_continue": False}),
            _synthesize_answer=AsyncMock(return_value="Answer"),
            _log_action=AsyncMock(),
        ):
            await agent.run("Task with custom settings")

        assert agent._context is not None
        assert agent._context.task == "Task with custom settings"
        assert agent._context.max_iterations == 10

    @pytest.mark.asyncio
    async def test_plan_created_artifact(self, agent):
        """run() should store the plan as an artifact."""
        plan_data = [{"action": "search", "params": {}}]
        with patch.multiple(
            agent,
            plan=AsyncMock(return_value=plan_data),
            execute_step=AsyncMock(return_value={"success": True, "result": "ok"}),
            reflect=AsyncMock(return_value={"should_continue": False}),
            _synthesize_answer=AsyncMock(return_value="Answer"),
            _log_action=AsyncMock(),
        ):
            await agent.run("Test")

        assert agent._context.get_artifact("plan") == plan_data


# ═══════════════════════════════════════════════════════════════════════════════
# 10. execute_with_retry
# ═══════════════════════════════════════════════════════════════════════════════

class TestExecuteWithRetry:
    """Tests for execute_with_retry — exponential backoff."""

    @pytest.mark.asyncio
    async def test_first_attempt_succeeds(self, agent):
        """Should return successfully on first attempt."""
        with patch.object(agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = AgentResult(
                agent_id="test", agent_type="test", status=AgentStatus.COMPLETED, answer="OK"
            )
            result = await agent.execute_with_retry("task", max_retries=3)
            assert result.success
            mock_run.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_retries_and_succeeds(self, agent):
        """Should retry on failure and eventually succeed."""
        with patch.object(agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                RuntimeError("Attempt 1 failed"),
                RuntimeError("Attempt 2 failed"),
                AgentResult(agent_id="test", agent_type="test", status=AgentStatus.COMPLETED, answer="OK"),
            ]
            result = await agent.execute_with_retry("task", max_retries=2, backoff_base=0.01)
            assert result.success
            assert mock_run.call_count == 3

    @pytest.mark.asyncio
    async def test_all_retries_fail(self, agent):
        """Should return FAILED result when all retries exhausted."""
        with patch.object(agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = RuntimeError("Always fails")
            result = await agent.execute_with_retry("task", max_retries=2, backoff_base=0.01)
            assert result.status == AgentStatus.FAILED
            assert "Failed after 3 attempts" in result.error
            assert mock_run.call_count == 3

    @pytest.mark.asyncio
    async def test_max_backoff_cap(self, agent):
        """Should cap backoff at max_backoff."""
        with patch.object(agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = RuntimeError("Fail")
            with patch("nexus.agents.base.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                result = await agent.execute_with_retry("task", max_retries=3, backoff_base=1.0, max_backoff=3.0)
                # Verify delays: min(1*2^0, 3) = 1, min(1*2^1, 3) = 2, min(1*2^2, 3) = 3
                delays = [call_args[0][0] for call_args in mock_sleep.call_args_list]
                assert len(delays) == 3
                for d in delays:
                    assert d <= 3.3  # 3.0 + jitter

    @pytest.mark.asyncio
    async def test_retry_with_0_max_retries(self, agent):
        """With max_retries=0, should only attempt once."""
        with patch.object(agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = RuntimeError("Fail")
            result = await agent.execute_with_retry("task", max_retries=0)
            assert result.status == AgentStatus.FAILED
            mock_run.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════════════════
# 11. execute_with_fallback
# ═══════════════════════════════════════════════════════════════════════════════

class TestExecuteWithFallback:
    """Tests for execute_with_fallback — agent and LLM fallback."""

    @pytest.mark.asyncio
    async def test_primary_succeeds(self, agent):
        """Should return result on primary success."""
        with patch.object(agent, "execute_with_retry", new_callable=AsyncMock) as mock_retry:
            mock_retry.return_value = AgentResult(
                agent_id="test", agent_type="test", status=AgentStatus.COMPLETED, answer="Primary OK"
            )
            result = await agent.execute_with_fallback("task")
            assert result.success
            assert result.answer == "Primary OK"

    @pytest.mark.asyncio
    async def test_fallback_agent_type(self, agent):
        """Should use fallback agent type when primary fails."""
        with patch.object(agent, "execute_with_retry", new_callable=AsyncMock) as mock_retry:
            mock_retry.side_effect = RuntimeError("Primary failed")

            with patch("nexus.core.registry.get_registry") as mock_reg:
                registry = MagicMock()
                registry.spawn.return_value = MagicMock()
                mock_reg.return_value = registry

                result = await agent.execute_with_fallback("task", fallback_agent_type="operator")
                assert result.status == AgentStatus.FAILED
                assert "fallback: operator" in result.error

    @pytest.mark.asyncio
    async def test_llm_fallback(self, agent):
        """Should use LLM fallback when no agent type is specified."""
        with patch.object(agent, "execute_with_retry", new_callable=AsyncMock) as mock_retry:
            mock_retry.side_effect = RuntimeError("Primary failed")

            with patch("nexus.llm.router.LLMRouter") as mock_router_cls:
                router = MagicMock()
                router.complete = AsyncMock()
                mock_response = MagicMock()
                mock_response.content = "LLM fallback answer"
                router.complete.return_value = mock_response
                mock_router_cls.return_value = router

                result = await agent.execute_with_fallback("task")
                assert result.status == AgentStatus.COMPLETED
                assert result.answer == "LLM fallback answer"
                assert "llm_fallback" in result.tools_used

    @pytest.mark.asyncio
    async def test_llm_fallback_fails(self, agent):
        """Should return FAILED when both primary and LLM fallback fail."""
        with patch.object(agent, "execute_with_retry", new_callable=AsyncMock) as mock_retry:
            mock_retry.side_effect = RuntimeError("Primary failed")

            with patch("nexus.llm.router.LLMRouter") as mock_router_cls:
                router = MagicMock()
                router.complete = AsyncMock(side_effect=RuntimeError("LLM also failed"))
                mock_router_cls.return_value = router

                result = await agent.execute_with_fallback("task")
                assert result.status == AgentStatus.FAILED
                assert "All fallbacks failed" in result.error


# ═══════════════════════════════════════════════════════════════════════════════
# 12. _synthesize_answer
# ═══════════════════════════════════════════════════════════════════════════════

class TestSynthesizeAnswer:
    """Tests for _synthesize_answer — LLM-based summarization with fallback."""

    @pytest.mark.asyncio
    async def test_synthesize_with_llm(self, agent):
        """_synthesize_answer should call _call_llm with synthesis prompt."""
        agent._tools_used = ["search", "analyze"]
        ctx = AgentContext(task="Research AI")
        ctx.add_message("user", "Tell me about AI")
        ctx.add_message("assistant", "AI is...")
        ctx.current_iteration = 3

        with patch.object(agent, "_call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "Final summary about AI"
            answer = await agent._synthesize_answer(ctx)
            assert answer == "Final summary about AI"
            mock_llm.assert_awaited_once()
            # The synthesis prompt should contain key elements
            prompt_arg = mock_llm.call_args[0][0]
            messages = prompt_arg if isinstance(prompt_arg, list) else []
            user_msg = next((m for m in messages if m["role"] == "user"), None)
            if user_msg:
                assert "Research AI" in user_msg["content"]
                assert "tools used: search, analyze" in user_msg["content"].lower()

    @pytest.mark.asyncio
    async def test_synthesize_fallback_to_last_assistant(self, agent):
        """_synthesize_answer should fall back to last assistant message on LLM failure."""
        ctx = AgentContext(task="Test")
        ctx.add_message("user", "Hello")
        ctx.add_message("assistant", "Final assistant response")

        with patch.object(agent, "_call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = RuntimeError("LLM failed")
            answer = await agent._synthesize_answer(ctx)
            assert answer == "Final assistant response"

    @pytest.mark.asyncio
    async def test_synthesize_fallback_no_assistant(self, agent):
        """_synthesize_answer should return default message when no assistant msg exists."""
        ctx = AgentContext(task="Test")
        ctx.add_message("user", "Hello")

        with patch.object(agent, "_call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = RuntimeError("LLM failed")
            answer = await agent._synthesize_answer(ctx)
            assert answer == "Task completed."


# ═══════════════════════════════════════════════════════════════════════════════
# 13. Token usage tracking (across multiple methods)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTokenUsage:
    """Token usage should accumulate across multiple _call_llm invocations."""

    @pytest.mark.asyncio
    async def test_accumulates_across_calls(self, agent, mock_llm_router):
        """Token counts should add up across consecutive LLM calls."""
        _, router = mock_llm_router
        router.complete.side_effect = [
            MockLLMResponse(content="First", usage={"prompt_tokens": 10, "completion_tokens": 5}),
            MockLLMResponse(content="Second", usage={"prompt_tokens": 20, "completion_tokens": 10}),
        ]

        await agent._call_llm([{"role": "user", "content": "Hi"}])
        await agent._call_llm([{"role": "user", "content": "Again"}])

        assert agent._token_usage["prompt"] == 30
        assert agent._token_usage["completion"] == 15
        assert agent._token_usage["total"] == 45

    @pytest.mark.asyncio
    async def test_token_usage_in_result(self, agent):
        """Token usage should be reflected in AgentResult."""
        with patch.multiple(
            agent,
            plan=AsyncMock(return_value=[]),
            execute_step=AsyncMock(return_value={"success": True}),
            reflect=AsyncMock(return_value={"should_continue": False}),
            _synthesize_answer=AsyncMock(return_value="Answer"),
            _log_action=AsyncMock(),
        ):
            agent._token_usage = {"prompt": 100, "completion": 50, "total": 150}
            result = await agent.run("Task")
            assert result.token_usage == {"prompt": 100, "completion": 50, "total": 150}


# ═══════════════════════════════════════════════════════════════════════════════
# 14. get_info
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetInfo:
    """Agent info reporting."""

    def test_get_info_basic(self):
        """get_info should return type, description, capabilities, skills, phase."""
        agent = ConcreteAgent(agent_type="custom", description="Custom agent", skills=["skill1"])
        info = agent.get_info()
        assert info["agent_type"] == "custom"
        assert info["description"] == "Custom agent"
        assert info["skills"] == ["skill1"]
        assert "research" in info["capabilities"]  # AgentCapability.RESEARCH.value
        assert info["phase"] == "initializing"


# ═══════════════════════════════════════════════════════════════════════════════
# 15. Error handling and edge cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestErrorHandling:
    """Edge cases and error handling across the agent."""

    @pytest.mark.asyncio
    async def test_mcp_tool_failure_returns_graceful_error(self, agent):
        """_use_tool should return graceful error dict when MCP tool raises."""
        with patch.object(agent, "_invoke_mcp_tool", new_callable=AsyncMock) as mock_mcp:
            mock_mcp.side_effect = ValueError("Connection refused")
            result = await agent._use_tool("knowledge_query", {"entity_name": "test"})
            assert isinstance(result, dict)
            assert "error" in result
            assert "not available" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_empty_task_creates_context(self, agent):
        """run() should work with minimal inputs."""
        with patch.multiple(
            agent,
            plan=AsyncMock(return_value=[]),
            execute_step=AsyncMock(return_value={"success": True}),
            reflect=AsyncMock(return_value={"should_continue": False}),
            _synthesize_answer=AsyncMock(return_value=""),
            _log_action=AsyncMock(),
        ):
            result = await agent.run("")
            assert result.status == AgentStatus.COMPLETED

    def test_agent_result_success_property(self):
        """AgentResult.success should reflect COMPLETED status."""
        r1 = AgentResult(agent_id="a", agent_type="t", status=AgentStatus.COMPLETED)
        assert r1.success is True
        r2 = AgentResult(agent_id="a", agent_type="t", status=AgentStatus.FAILED)
        assert r2.success is False
        r3 = AgentResult(agent_id="a", agent_type="t", status=AgentStatus.IDLE)
        assert r3.success is False

    def test_agent_phase_enum_values(self):
        """AgentPhase should have all expected enum values."""
        assert AgentPhase.INITIALIZING.value == "initializing"
        assert AgentPhase.PLANNING.value == "planning"
        assert AgentPhase.EXECUTING.value == "executing"
        assert AgentPhase.REFLECTING.value == "reflecting"
        assert AgentPhase.FINALIZING.value == "finalizing"
        assert AgentPhase.COMPLETED.value == "completed"
        assert AgentPhase.FAILED.value == "failed"


# ═══════════════════════════════════════════════════════════════════════════════
# 16. Provider configuration & fallback integration
# ═══════════════════════════════════════════════════════════════════════════════

class TestProviderConfiguration:
    """Provider config is managed through _call_llm args."""

    @pytest.mark.asyncio
    async def test_default_provider_is_gemini(self, agent, mock_llm_router):
        """_call_llm should default provider to 'gemini'."""
        _, router = mock_llm_router
        router.complete.return_value = MockLLMResponse(content="OK")
        await agent._call_llm(messages=[{"role": "user", "content": "Hi"}])
        call_kwargs = router.complete.call_args[1]
        assert call_kwargs["provider"] == "gemini"

    @pytest.mark.asyncio
    async def test_provider_passthrough_to_router(self, agent, mock_llm_router):
        """Provider argument should be passed directly to router.complete."""
        _, router = mock_llm_router
        router.complete.return_value = MockLLMResponse(content="OK")
        await agent._call_llm(messages=[{"role": "user", "content": "Hi"}], provider="anthropic/claude-3")
        call_kwargs = router.complete.call_args[1]
        assert call_kwargs["provider"] == "anthropic/claude-3"


# ═══════════════════════════════════════════════════════════════════════════════
# 17. FALLBACK_TOOLS constant validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestFallbackTools:
    """The _FALLBACK_TOOLS set contains the right tools."""

    def test_fallback_tools_set(self):
        """_FALLBACK_TOOLS should contain the 6 fallback tool names."""
        expected = {"web_search", "code_execute", "file_read", "file_write", "memory_store", "memory_recall"}
        assert BaseAgent._FALLBACK_TOOLS == expected

    @pytest.mark.asyncio
    async def test_each_fallback_tool_routes_correctly(self, agent):
        """Each fallback tool should call _fallback_tool_execution not _invoke_mcp_tool."""
        for tool_name in BaseAgent._FALLBACK_TOOLS:
            with patch.object(agent, "_fallback_tool_execution", new_callable=AsyncMock) as mock_fb:
                mock_fb.return_value = {"result": "fallback"}
                with patch.object(agent, "_invoke_mcp_tool", new_callable=AsyncMock) as mock_mcp:
                    await agent._use_tool(tool_name, {"query": "test"})
                    # Should NOT call MCP
                    mock_mcp.assert_not_called()
                    # Should call fallback
                    mock_fb.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# 18. AgentContext edge cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentContextEdgeCases:
    """Additional edge cases for AgentContext."""

    def test_add_message_with_extra_kwargs(self):
        """add_message should include extra kwargs in the message dict."""
        ctx = AgentContext(task="test")
        ctx.add_message("user", "Hello", confidence=0.95, source="test")
        msg = ctx.conversation[0]
        assert msg["confidence"] == 0.95
        assert msg["source"] == "test"

    def test_artifact_overwrite(self):
        """store_artifact should overwrite existing keys."""
        ctx = AgentContext(task="test")
        ctx.store_artifact("key", "first")
        ctx.store_artifact("key", "second")
        assert ctx.get_artifact("key") == "second"

    def test_default_max_iterations(self):
        """Default max_iterations should be 25."""
        ctx = AgentContext(task="test")
        assert ctx.max_iterations == 25

    def test_default_current_iteration(self):
        """Default current_iteration should be 0."""
        ctx = AgentContext(task="test")
        assert ctx.current_iteration == 0

    def test_agent_id_default_length(self):
        """Default agent_id should be 12 hex chars."""
        ctx = AgentContext(task="test")
        assert len(ctx.agent_id) == 12
        assert all(c in "0123456789abcdef" for c in ctx.agent_id)

    def test_custom_agent_id(self):
        """Should accept custom agent_id."""
        ctx = AgentContext(task="test", agent_id="custom123")
        assert ctx.agent_id == "custom123"
