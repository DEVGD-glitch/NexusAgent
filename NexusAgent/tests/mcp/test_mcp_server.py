"""
Comprehensive tests for nexus.mcp_server — FastMCP tool server.

Covers ALL 40+ MCP tools, resource endpoints, prompt templates, server
runner, and error handling. All external dependencies are mocked at their
import sites in nexus.mcp_server.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexus.core.exceptions import MCPToolError


# =============================================================================
# Helper: Auto-AsyncMock module
# =============================================================================

class _AsyncMockModule:
    """
    A namespace-like object where every attribute access (except dunders)
    returns an AsyncMock. This replicates a module whose every function
    is async, allowing ``await module.func(...)`` to work in tests.
    """

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        m = AsyncMock()
        setattr(self, name, m)
        return m


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def mock_all_mcp_tool_modules():
    """
    Mock ALL mcp_tools.* modules used by nexus.mcp_server BEFORE import.
    Each mock module is an _AsyncMockModule so every function access
    returns an AsyncMock — the server's tool functions can ``await`` them.
    """
    patcher_modules = patch.multiple(
        "nexus.mcp_server",
        memory_tools=_AsyncMockModule(),
        knowledge_tools=_AsyncMockModule(),
        llm_tools=_AsyncMockModule(),
        agent_tools=_AsyncMockModule(),
        code_tools=_AsyncMockModule(),
        file_tools=_AsyncMockModule(),
        web_tools=_AsyncMockModule(),
        reasoning_tools=_AsyncMockModule(),
        orchestration_tools=_AsyncMockModule(),
        system_tools=_AsyncMockModule(),
        bonus_tools=_AsyncMockModule(),
    )
    patcher_modules.start()

    # Now import the module — it will see the mocked tool modules
    import nexus.mcp_server as mcp_mod
    global mcp
    mcp = mcp_mod

    yield

    patcher_modules.stop()


@pytest.fixture
def mock_logger():
    """Patch logger in mcp_server to suppress log output."""
    with patch("nexus.mcp_server.logger") as mock_log:
        yield mock_log


# ═══════════════════════════════════════════════════════════════════════════
# MEMORY TOOLS (5)
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPMemoryTools:
    """Tests for memory MCP tools."""

    @pytest.mark.asyncio
    async def test_search_memory_happy(self):
        """search_memory delegates to memory_tools and returns result."""
        expected = json.dumps({"documents": [{"id": "1", "text": "test"}]})
        mcp.memory_tools.search_memory.return_value = expected

        result = await mcp.search_memory("test query")
        assert result == expected
        mcp.memory_tools.search_memory.assert_called_once_with("test query", "knowledge", 5)

    @pytest.mark.asyncio
    async def test_search_memory_with_args(self):
        """search_memory passes namespace and top_k correctly."""
        mcp.memory_tools.search_memory.return_value = "[]"

        await mcp.search_memory("q", namespace="episodes", top_k=10)
        mcp.memory_tools.search_memory.assert_called_once_with("q", "episodes", 10)

    @pytest.mark.asyncio
    async def test_search_memory_error(self):
        """search_memory raises MCPToolError on failure."""
        mcp.memory_tools.search_memory.side_effect = Exception("memory error")
        with pytest.raises(MCPToolError, match="search_memory"):
            await mcp.search_memory("q")

    @pytest.mark.asyncio
    async def test_store_memory_happy(self):
        """store_memory delegates to memory_tools."""
        mcp.memory_tools.store_memory.return_value = '{"status": "stored"}'
        result = await mcp.store_memory("content", namespace="conversations", metadata={"key": "val"})
        assert "stored" in result
        mcp.memory_tools.store_memory.assert_called_once_with("content", "conversations", {"key": "val"})

    @pytest.mark.asyncio
    async def test_store_memory_no_metadata(self):
        """store_memory passes None metadata when not provided."""
        mcp.memory_tools.store_memory.return_value = "ok"
        await mcp.store_memory("text")
        mcp.memory_tools.store_memory.assert_called_once_with("text", "knowledge", None)

    @pytest.mark.asyncio
    async def test_store_memory_error(self):
        """store_memory raises MCPToolError on failure."""
        mcp.memory_tools.store_memory.side_effect = Exception("store fail")
        with pytest.raises(MCPToolError, match="store_memory"):
            await mcp.store_memory("text")

    @pytest.mark.asyncio
    async def test_delete_memory_happy(self):
        """delete_memory delegates to memory_tools."""
        mcp.memory_tools.delete_memory.return_value = '{"deleted": 2}'
        result = await mcp.delete_memory(["id1", "id2"], namespace="conversations")
        assert "deleted" in result
        mcp.memory_tools.delete_memory.assert_called_once_with(["id1", "id2"], "conversations")

    @pytest.mark.asyncio
    async def test_delete_memory_default_namespace(self):
        """delete_memory uses 'conversations' as default namespace."""
        mcp.memory_tools.delete_memory.return_value = "ok"
        await mcp.delete_memory(["id1"])
        mcp.memory_tools.delete_memory.assert_called_once_with(["id1"], "conversations")

    @pytest.mark.asyncio
    async def test_delete_memory_error(self):
        """delete_memory raises MCPToolError on failure."""
        mcp.memory_tools.delete_memory.side_effect = Exception("delete fail")
        with pytest.raises(MCPToolError, match="delete_memory"):
            await mcp.delete_memory(["id1"])

    @pytest.mark.asyncio
    async def test_list_namespaces_happy(self):
        """list_namespaces delegates to memory_tools."""
        mcp.memory_tools.list_namespaces.return_value = '["conversations", "knowledge"]'
        result = await mcp.list_namespaces()
        assert "conversations" in result
        mcp.memory_tools.list_namespaces.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_namespaces_error(self):
        """list_namespaces raises MCPToolError on failure."""
        mcp.memory_tools.list_namespaces.side_effect = Exception("list fail")
        with pytest.raises(MCPToolError, match="list_namespaces"):
            await mcp.list_namespaces()

    @pytest.mark.asyncio
    async def test_memory_stats_happy(self):
        """memory_stats delegates to memory_tools."""
        mcp.memory_tools.memory_stats.return_value = '{"total_docs": 500}'
        result = await mcp.memory_stats()
        assert "total_docs" in result
        mcp.memory_tools.memory_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_memory_stats_error(self):
        """memory_stats raises MCPToolError on failure."""
        mcp.memory_tools.memory_stats.side_effect = Exception("stats fail")
        with pytest.raises(MCPToolError, match="memory_stats"):
            await mcp.memory_stats()


# ═══════════════════════════════════════════════════════════════════════════
# KNOWLEDGE TOOLS (5)
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPKnowledgeTools:
    """Tests for knowledge graph MCP tools."""

    @pytest.mark.asyncio
    async def test_knowledge_query_happy(self):
        """knowledge_query delegates to knowledge_tools."""
        mcp.knowledge_tools.knowledge_query.return_value = '{"entity": "Python", "relations": []}'
        result = await mcp.knowledge_query("Python", depth=2)
        assert "Python" in result
        mcp.knowledge_tools.knowledge_query.assert_called_once_with("Python", 2)

    @pytest.mark.asyncio
    async def test_knowledge_query_default_depth(self):
        """knowledge_query uses default depth of 1."""
        mcp.knowledge_tools.knowledge_query.return_value = "{}"
        await mcp.knowledge_query("Python")
        mcp.knowledge_tools.knowledge_query.assert_called_once_with("Python", 1)

    @pytest.mark.asyncio
    async def test_knowledge_query_error(self):
        """knowledge_query raises MCPToolError on failure."""
        mcp.knowledge_tools.knowledge_query.side_effect = Exception("kg error")
        with pytest.raises(MCPToolError, match="knowledge_query"):
            await mcp.knowledge_query("x")

    @pytest.mark.asyncio
    async def test_knowledge_add_entity_happy(self):
        """knowledge_add_entity delegates to knowledge_tools."""
        mcp.knowledge_tools.knowledge_add_entity.return_value = '{"id": "ent-1"}'
        result = await mcp.knowledge_add_entity("concept", "Python", {"creator": "Guido"})
        assert "ent-1" in result
        mcp.knowledge_tools.knowledge_add_entity.assert_called_once_with("concept", "Python", {"creator": "Guido"})

    @pytest.mark.asyncio
    async def test_knowledge_add_entity_no_properties(self):
        """knowledge_add_entity passes None when properties omitted."""
        mcp.knowledge_tools.knowledge_add_entity.return_value = "ok"
        await mcp.knowledge_add_entity("concept", "Python")
        mcp.knowledge_tools.knowledge_add_entity.assert_called_once_with("concept", "Python", None)

    @pytest.mark.asyncio
    async def test_knowledge_add_entity_error(self):
        """knowledge_add_entity raises MCPToolError on failure."""
        mcp.knowledge_tools.knowledge_add_entity.side_effect = Exception("add fail")
        with pytest.raises(MCPToolError, match="knowledge_add_entity"):
            await mcp.knowledge_add_entity("t", "n")

    @pytest.mark.asyncio
    async def test_knowledge_add_relation_happy(self):
        """knowledge_add_relation delegates to knowledge_tools."""
        mcp.knowledge_tools.knowledge_add_relation.return_value = '{"status": "linked"}'
        result = await mcp.knowledge_add_relation("A", "B", "connects", {"weight": 1})
        assert "linked" in result
        mcp.knowledge_tools.knowledge_add_relation.assert_called_once_with("A", "B", "connects", {"weight": 1})

    @pytest.mark.asyncio
    async def test_knowledge_add_relation_no_props(self):
        """knowledge_add_relation passes None for properties."""
        mcp.knowledge_tools.knowledge_add_relation.return_value = "ok"
        await mcp.knowledge_add_relation("A", "B", "connects")
        mcp.knowledge_tools.knowledge_add_relation.assert_called_once_with("A", "B", "connects", None)

    @pytest.mark.asyncio
    async def test_knowledge_add_relation_error(self):
        """knowledge_add_relation raises MCPToolError on failure."""
        mcp.knowledge_tools.knowledge_add_relation.side_effect = Exception("rel fail")
        with pytest.raises(MCPToolError, match="knowledge_add_relation"):
            await mcp.knowledge_add_relation("A", "B", "x")

    @pytest.mark.asyncio
    async def test_knowledge_search_happy(self):
        """knowledge_search delegates to knowledge_tools."""
        mcp.knowledge_tools.knowledge_search.return_value = '{"results": []}'
        result = await mcp.knowledge_search("test query", entity_type="concept", limit=10)
        assert "results" in result
        mcp.knowledge_tools.knowledge_search.assert_called_once_with("test query", "concept", 10)

    @pytest.mark.asyncio
    async def test_knowledge_search_defaults(self):
        """knowledge_search uses default entity_type and limit."""
        mcp.knowledge_tools.knowledge_search.return_value = "{}"
        await mcp.knowledge_search("test")
        mcp.knowledge_tools.knowledge_search.assert_called_once_with("test", None, 20)

    @pytest.mark.asyncio
    async def test_knowledge_search_error(self):
        """knowledge_search raises MCPToolError on failure."""
        mcp.knowledge_tools.knowledge_search.side_effect = Exception("search fail")
        with pytest.raises(MCPToolError, match="knowledge_search"):
            await mcp.knowledge_search("test")

    @pytest.mark.asyncio
    async def test_knowledge_paths_happy(self):
        """knowledge_paths delegates to knowledge_tools."""
        mcp.knowledge_tools.knowledge_paths.return_value = '{"paths": []}'
        result = await mcp.knowledge_paths("A", "B", max_length=3)
        assert "paths" in result
        mcp.knowledge_tools.knowledge_paths.assert_called_once_with("A", "B", 3)

    @pytest.mark.asyncio
    async def test_knowledge_paths_default_max_length(self):
        """knowledge_paths uses default max_length of 5."""
        mcp.knowledge_tools.knowledge_paths.return_value = "{}"
        await mcp.knowledge_paths("A", "B")
        mcp.knowledge_tools.knowledge_paths.assert_called_once_with("A", "B", 5)

    @pytest.mark.asyncio
    async def test_knowledge_paths_error(self):
        """knowledge_paths raises MCPToolError on failure."""
        mcp.knowledge_tools.knowledge_paths.side_effect = Exception("path fail")
        with pytest.raises(MCPToolError, match="knowledge_paths"):
            await mcp.knowledge_paths("A", "B")


# ═══════════════════════════════════════════════════════════════════════════
# LLM TOOLS (4)
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPLLMTools:
    """Tests for LLM MCP tools."""

    @pytest.mark.asyncio
    async def test_llm_complete_happy(self):
        """llm_complete delegates to llm_tools."""
        mcp.llm_tools.llm_complete.return_value = '{"content": "Hello!"}'
        result = await mcp.llm_complete("Hi", model="gpt-4", temperature=0.5, max_tokens=2048)
        assert "Hello" in result
        mcp.llm_tools.llm_complete.assert_called_once_with("Hi", "gpt-4", 0.5, 2048)

    @pytest.mark.asyncio
    async def test_llm_complete_defaults(self):
        """llm_complete uses default model, temperature, max_tokens."""
        mcp.llm_tools.llm_complete.return_value = "ok"
        await mcp.llm_complete("Hi")
        mcp.llm_tools.llm_complete.assert_called_once_with("Hi", None, 0.7, 4096)

    @pytest.mark.asyncio
    async def test_llm_complete_error(self):
        """llm_complete raises MCPToolError on failure."""
        mcp.llm_tools.llm_complete.side_effect = Exception("llm error")
        with pytest.raises(MCPToolError, match="llm_complete"):
            await mcp.llm_complete("Hi")

    @pytest.mark.asyncio
    async def test_llm_list_models_happy(self):
        """llm_list_models delegates to llm_tools."""
        mcp.llm_tools.llm_list_models.return_value = '["gpt-4", "claude-3"]'
        result = await mcp.llm_list_models()
        assert "gpt-4" in result
        mcp.llm_tools.llm_list_models.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_list_models_error(self):
        """llm_list_models raises MCPToolError on failure."""
        mcp.llm_tools.llm_list_models.side_effect = Exception("list fail")
        with pytest.raises(MCPToolError, match="llm_list_models"):
            await mcp.llm_list_models()

    @pytest.mark.asyncio
    async def test_llm_provider_status_happy(self):
        """llm_provider_status delegates to llm_tools."""
        mcp.llm_tools.llm_provider_status.return_value = '{"openai": "ok"}'
        result = await mcp.llm_provider_status()
        assert "openai" in result
        mcp.llm_tools.llm_provider_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_provider_status_error(self):
        """llm_provider_status raises MCPToolError on failure."""
        mcp.llm_tools.llm_provider_status.side_effect = Exception("status fail")
        with pytest.raises(MCPToolError, match="llm_provider_status"):
            await mcp.llm_provider_status()

    @pytest.mark.asyncio
    async def test_llm_stream_happy(self):
        """llm_stream delegates to llm_tools."""
        mcp.llm_tools.llm_stream.return_value = "streamed content"
        result = await mcp.llm_stream("Hi", model="gpt-4", temperature=0.3)
        assert result == "streamed content"
        mcp.llm_tools.llm_stream.assert_called_once_with("Hi", "gpt-4", 0.3)

    @pytest.mark.asyncio
    async def test_llm_stream_defaults(self):
        """llm_stream uses default model and temperature."""
        mcp.llm_tools.llm_stream.return_value = "ok"
        await mcp.llm_stream("Hi")
        mcp.llm_tools.llm_stream.assert_called_once_with("Hi", None, 0.7)

    @pytest.mark.asyncio
    async def test_llm_stream_error(self):
        """llm_stream raises MCPToolError on failure."""
        mcp.llm_tools.llm_stream.side_effect = Exception("stream fail")
        with pytest.raises(MCPToolError, match="llm_stream"):
            await mcp.llm_stream("Hi")


# ═══════════════════════════════════════════════════════════════════════════
# AGENT TOOLS (5)
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPAgentTools:
    """Tests for agent MCP tools."""

    @pytest.mark.asyncio
    async def test_spawn_agent_happy(self):
        """spawn_agent delegates to agent_tools."""
        mcp.agent_tools.spawn_agent.return_value = '{"agent_id": "a-1", "status": "running"}'
        result = await mcp.spawn_agent("coder", "write tests", config={"model": "gpt-4"})
        assert "a-1" in result
        mcp.agent_tools.spawn_agent.assert_called_once_with("coder", "write tests", {"model": "gpt-4"})

    @pytest.mark.asyncio
    async def test_spawn_agent_no_config(self):
        """spawn_agent passes None when config omitted."""
        mcp.agent_tools.spawn_agent.return_value = "ok"
        await mcp.spawn_agent("coder", "task")
        mcp.agent_tools.spawn_agent.assert_called_once_with("coder", "task", None)

    @pytest.mark.asyncio
    async def test_spawn_agent_error(self):
        """spawn_agent raises MCPToolError on failure."""
        mcp.agent_tools.spawn_agent.side_effect = Exception("spawn fail")
        with pytest.raises(MCPToolError, match="spawn_agent"):
            await mcp.spawn_agent("coder", "task")

    @pytest.mark.asyncio
    async def test_list_agents_happy(self):
        """list_agents delegates to agent_tools."""
        mcp.agent_tools.list_agents.return_value = '["coder", "researcher"]'
        result = await mcp.list_agents()
        assert "coder" in result
        mcp.agent_tools.list_agents.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_agents_error(self):
        """list_agents raises MCPToolError on failure."""
        mcp.agent_tools.list_agents.side_effect = Exception("list fail")
        with pytest.raises(MCPToolError, match="list_agents"):
            await mcp.list_agents()

    @pytest.mark.asyncio
    async def test_agent_status_happy(self):
        """agent_status delegates to agent_tools."""
        mcp.agent_tools.agent_status.return_value = '{"instance_id": "i-1", "status": "running"}'
        result = await mcp.agent_status("i-1")
        assert "running" in result
        mcp.agent_tools.agent_status.assert_called_once_with("i-1")

    @pytest.mark.asyncio
    async def test_agent_status_error(self):
        """agent_status raises MCPToolError on failure."""
        mcp.agent_tools.agent_status.side_effect = Exception("status fail")
        with pytest.raises(MCPToolError, match="agent_status"):
            await mcp.agent_status("i-1")

    @pytest.mark.asyncio
    async def test_agent_delegate_happy(self):
        """agent_delegate delegates to agent_tools."""
        mcp.agent_tools.agent_delegate.return_value = '{"status": "delegated"}'
        result = await mcp.agent_delegate("agent-a", "agent-b", "do task", {"priority": "high"})
        assert "delegated" in result
        mcp.agent_tools.agent_delegate.assert_called_once_with("agent-a", "agent-b", "do task", {"priority": "high"})

    @pytest.mark.asyncio
    async def test_agent_delegate_no_context(self):
        """agent_delegate passes None for context."""
        mcp.agent_tools.agent_delegate.return_value = "ok"
        await mcp.agent_delegate("a", "b", "task")
        mcp.agent_tools.agent_delegate.assert_called_once_with("a", "b", "task", None)

    @pytest.mark.asyncio
    async def test_agent_delegate_error(self):
        """agent_delegate raises MCPToolError on failure."""
        mcp.agent_tools.agent_delegate.side_effect = Exception("delegate fail")
        with pytest.raises(MCPToolError, match="agent_delegate"):
            await mcp.agent_delegate("a", "b", "task")

    @pytest.mark.asyncio
    async def test_a2a_discover_happy(self):
        """a2a_discover delegates to agent_tools."""
        mcp.agent_tools.a2a_discover.return_value = '{"agent": "ext-agent", "capabilities": []}'
        result = await mcp.a2a_discover("http://agent.example.com")
        assert "ext-agent" in result
        mcp.agent_tools.a2a_discover.assert_called_once_with("http://agent.example.com")

    @pytest.mark.asyncio
    async def test_a2a_discover_error(self):
        """a2a_discover raises MCPToolError on failure."""
        mcp.agent_tools.a2a_discover.side_effect = Exception("discover fail")
        with pytest.raises(MCPToolError, match="a2a_discover"):
            await mcp.a2a_discover("http://x.com")


# ═══════════════════════════════════════════════════════════════════════════
# CODE TOOLS (3)
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPCodeTools:
    """Tests for code execution MCP tools."""

    @pytest.mark.asyncio
    async def test_execute_code_happy(self):
        """execute_code delegates to code_tools."""
        mcp.code_tools.execute_code.return_value = '{"stdout": "Hello", "exit_code": 0}'
        result = await mcp.execute_code("print('hi')", language="python", timeout=15)
        assert "Hello" in result
        mcp.code_tools.execute_code.assert_called_once_with("print('hi')", "python", 15)

    @pytest.mark.asyncio
    async def test_execute_code_defaults(self):
        """execute_code uses default language and timeout."""
        mcp.code_tools.execute_code.return_value = "ok"
        await mcp.execute_code("x")
        mcp.code_tools.execute_code.assert_called_once_with("x", "python", 30)

    @pytest.mark.asyncio
    async def test_execute_code_error(self):
        """execute_code raises MCPToolError on failure."""
        mcp.code_tools.execute_code.side_effect = Exception("code fail")
        with pytest.raises(MCPToolError, match="execute_code"):
            await mcp.execute_code("x")

    @pytest.mark.asyncio
    async def test_execute_sandboxed_happy(self):
        """execute_sandboxed delegates to code_tools."""
        mcp.code_tools.execute_sandboxed.return_value = '{"stdout": "ok", "exit_code": 0}'
        result = await mcp.execute_sandboxed("ls", timeout=60, allowed_dirs=["/tmp"])
        assert "ok" in result
        mcp.code_tools.execute_sandboxed.assert_called_once_with("ls", 60, ["/tmp"])

    @pytest.mark.asyncio
    async def test_execute_sandboxed_defaults(self):
        """execute_sandboxed uses defaults when args omitted."""
        mcp.code_tools.execute_sandboxed.return_value = "ok"
        await mcp.execute_sandboxed("ls")
        mcp.code_tools.execute_sandboxed.assert_called_once_with("ls", 30, None)

    @pytest.mark.asyncio
    async def test_execute_sandboxed_error(self):
        """execute_sandboxed raises MCPToolError on failure."""
        mcp.code_tools.execute_sandboxed.side_effect = Exception("sandbox fail")
        with pytest.raises(MCPToolError, match="execute_sandboxed"):
            await mcp.execute_sandboxed("cmd")

    @pytest.mark.asyncio
    async def test_install_package_happy(self):
        """install_package delegates to code_tools."""
        mcp.code_tools.install_package.return_value = '{"status": "installed"}'
        result = await mcp.install_package("requests", version="2.31.0")
        assert "installed" in result
        mcp.code_tools.install_package.assert_called_once_with("requests", "2.31.0")

    @pytest.mark.asyncio
    async def test_install_package_no_version(self):
        """install_package passes None for version when omitted."""
        mcp.code_tools.install_package.return_value = "ok"
        await mcp.install_package("requests")
        mcp.code_tools.install_package.assert_called_once_with("requests", None)

    @pytest.mark.asyncio
    async def test_install_package_error(self):
        """install_package raises MCPToolError on failure."""
        mcp.code_tools.install_package.side_effect = Exception("install fail")
        with pytest.raises(MCPToolError, match="install_package"):
            await mcp.install_package("x")


# ═══════════════════════════════════════════════════════════════════════════
# FILE TOOLS (7)
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPFileTools:
    """Tests for file operation MCP tools."""

    @pytest.mark.asyncio
    async def test_read_file_happy(self):
        """read_file delegates to file_tools."""
        mcp.file_tools.read_file.return_value = '{"content": "file content", "path": "/tmp/f.txt"}'
        result = await mcp.read_file("/tmp/f.txt", encoding="utf-8")
        assert "file content" in result
        mcp.file_tools.read_file.assert_called_once_with("/tmp/f.txt", "utf-8")

    @pytest.mark.asyncio
    async def test_read_file_default_encoding(self):
        """read_file uses utf-8 as default encoding."""
        mcp.file_tools.read_file.return_value = "ok"
        await mcp.read_file("/tmp/f.txt")
        mcp.file_tools.read_file.assert_called_once_with("/tmp/f.txt", "utf-8")

    @pytest.mark.asyncio
    async def test_read_file_error(self):
        """read_file raises MCPToolError on failure."""
        mcp.file_tools.read_file.side_effect = Exception("read fail")
        with pytest.raises(MCPToolError, match="read_file"):
            await mcp.read_file("x")

    @pytest.mark.asyncio
    async def test_write_file_happy(self):
        """write_file delegates to file_tools."""
        mcp.file_tools.write_file.return_value = '{"status": "written"}'
        result = await mcp.write_file("/tmp/f.txt", "content", encoding="utf-8")
        assert "written" in result
        mcp.file_tools.write_file.assert_called_once_with("/tmp/f.txt", "content", "utf-8")

    @pytest.mark.asyncio
    async def test_write_file_default_encoding(self):
        """write_file uses utf-8 as default encoding."""
        mcp.file_tools.write_file.return_value = "ok"
        await mcp.write_file("/tmp/f.txt", "c")
        mcp.file_tools.write_file.assert_called_once_with("/tmp/f.txt", "c", "utf-8")

    @pytest.mark.asyncio
    async def test_write_file_error(self):
        """write_file raises MCPToolError on failure."""
        mcp.file_tools.write_file.side_effect = Exception("write fail")
        with pytest.raises(MCPToolError, match="write_file"):
            await mcp.write_file("x", "c")

    @pytest.mark.asyncio
    async def test_list_files_happy(self):
        """list_files delegates to file_tools."""
        mcp.file_tools.list_files.return_value = '["f1.txt", "f2.py"]'
        result = await mcp.list_files(directory="/tmp", pattern="*.txt")
        assert "f1.txt" in result
        mcp.file_tools.list_files.assert_called_once_with("/tmp", "*.txt")

    @pytest.mark.asyncio
    async def test_list_files_defaults(self):
        """list_files uses defaults for directory and pattern."""
        mcp.file_tools.list_files.return_value = "[]"
        await mcp.list_files()
        mcp.file_tools.list_files.assert_called_once_with(".", "*")

    @pytest.mark.asyncio
    async def test_list_files_error(self):
        """list_files raises MCPToolError on failure."""
        mcp.file_tools.list_files.side_effect = Exception("list fail")
        with pytest.raises(MCPToolError, match="list_files"):
            await mcp.list_files()

    @pytest.mark.asyncio
    async def test_delete_file_happy(self):
        """delete_file delegates to file_tools."""
        mcp.file_tools.delete_file.return_value = '{"status": "deleted"}'
        result = await mcp.delete_file("/tmp/f.txt")
        assert "deleted" in result
        mcp.file_tools.delete_file.assert_called_once_with("/tmp/f.txt")

    @pytest.mark.asyncio
    async def test_delete_file_error(self):
        """delete_file raises MCPToolError on failure."""
        mcp.file_tools.delete_file.side_effect = Exception("delete fail")
        with pytest.raises(MCPToolError, match="delete_file"):
            await mcp.delete_file("x")

    @pytest.mark.asyncio
    async def test_move_file_happy(self):
        """move_file delegates to file_tools."""
        mcp.file_tools.move_file.return_value = '{"status": "moved"}'
        result = await mcp.move_file("/tmp/a", "/tmp/b")
        assert "moved" in result
        mcp.file_tools.move_file.assert_called_once_with("/tmp/a", "/tmp/b")

    @pytest.mark.asyncio
    async def test_move_file_error(self):
        """move_file raises MCPToolError on failure."""
        mcp.file_tools.move_file.side_effect = Exception("move fail")
        with pytest.raises(MCPToolError, match="move_file"):
            await mcp.move_file("a", "b")

    @pytest.mark.asyncio
    async def test_copy_file_happy(self):
        """copy_file delegates to file_tools."""
        mcp.file_tools.copy_file.return_value = '{"status": "copied"}'
        result = await mcp.copy_file("/tmp/a", "/tmp/b")
        assert "copied" in result
        mcp.file_tools.copy_file.assert_called_once_with("/tmp/a", "/tmp/b")

    @pytest.mark.asyncio
    async def test_copy_file_error(self):
        """copy_file raises MCPToolError on failure."""
        mcp.file_tools.copy_file.side_effect = Exception("copy fail")
        with pytest.raises(MCPToolError, match="copy_file"):
            await mcp.copy_file("a", "b")

    @pytest.mark.asyncio
    async def test_search_files_happy(self):
        """search_files delegates to file_tools."""
        mcp.file_tools.search_files.return_value = '{"matches": [{"file": "x.py", "line": 10}]}'
        result = await mcp.search_files("query", path="/src", file_pattern="*.py")
        assert "x.py" in result
        mcp.file_tools.search_files.assert_called_once_with("query", "/src", "*.py")

    @pytest.mark.asyncio
    async def test_search_files_defaults(self):
        """search_files uses defaults for path and file_pattern."""
        mcp.file_tools.search_files.return_value = "{}"
        await mcp.search_files("query")
        mcp.file_tools.search_files.assert_called_once_with("query", ".", "*")

    @pytest.mark.asyncio
    async def test_search_files_error(self):
        """search_files raises MCPToolError on failure."""
        mcp.file_tools.search_files.side_effect = Exception("search fail")
        with pytest.raises(MCPToolError, match="search_files"):
            await mcp.search_files("q")


# ═══════════════════════════════════════════════════════════════════════════
# WEB TOOLS (3)
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPWebTools:
    """Tests for web MCP tools."""

    @pytest.mark.asyncio
    async def test_web_search_happy(self):
        """web_search delegates to web_tools."""
        mcp.web_tools.web_search.return_value = '{"results": [{"title": "NEXUS AI"}]}'
        result = await mcp.web_search("test query", num_results=10)
        assert "NEXUS AI" in result
        mcp.web_tools.web_search.assert_called_once_with("test query", 10)

    @pytest.mark.asyncio
    async def test_web_search_default_results(self):
        """web_search uses default num_results of 5."""
        mcp.web_tools.web_search.return_value = "{}"
        await mcp.web_search("query")
        mcp.web_tools.web_search.assert_called_once_with("query", 5)

    @pytest.mark.asyncio
    async def test_web_search_error(self):
        """web_search raises MCPToolError on failure."""
        mcp.web_tools.web_search.side_effect = Exception("web fail")
        with pytest.raises(MCPToolError, match="web_search"):
            await mcp.web_search("q")

    @pytest.mark.asyncio
    async def test_web_scrape_happy(self):
        """web_scrape delegates to web_tools."""
        mcp.web_tools.web_scrape.return_value = '{"content": "page text", "url": "https://x.com"}'
        result = await mcp.web_scrape("https://x.com", max_length=5000)
        assert "page text" in result
        mcp.web_tools.web_scrape.assert_called_once_with("https://x.com", 5000)

    @pytest.mark.asyncio
    async def test_web_scrape_default_max_length(self):
        """web_scrape uses default max_length."""
        mcp.web_tools.web_scrape.return_value = "ok"
        await mcp.web_scrape("https://x.com")
        mcp.web_tools.web_scrape.assert_called_once_with("https://x.com", 10000)

    @pytest.mark.asyncio
    async def test_web_scrape_error(self):
        """web_scrape raises MCPToolError on failure."""
        mcp.web_tools.web_scrape.side_effect = Exception("scrape fail")
        with pytest.raises(MCPToolError, match="web_scrape"):
            await mcp.web_scrape("https://x.com")

    @pytest.mark.asyncio
    async def test_web_screenshot_happy(self):
        """web_screenshot delegates to web_tools."""
        mcp.web_tools.web_screenshot.return_value = '{"screenshot": "base64data..."}'
        result = await mcp.web_screenshot("https://x.com")
        assert "screenshot" in result
        mcp.web_tools.web_screenshot.assert_called_once_with("https://x.com")

    @pytest.mark.asyncio
    async def test_web_screenshot_error(self):
        """web_screenshot raises MCPToolError on failure."""
        mcp.web_tools.web_screenshot.side_effect = Exception("screenshot fail")
        with pytest.raises(MCPToolError, match="web_screenshot"):
            await mcp.web_screenshot("https://x.com")


# ═══════════════════════════════════════════════════════════════════════════
# REASONING TOOLS (3)
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPReasoningTools:
    """Tests for reasoning MCP tools."""

    @pytest.mark.asyncio
    async def test_reason_react_happy(self):
        """reason_react delegates to reasoning_tools."""
        mcp.reasoning_tools.reason_react.return_value = '{"steps": ["thought", "action"], "result": "done"}'
        result = await mcp.reason_react("solve problem", max_iterations=5)
        assert "steps" in result
        mcp.reasoning_tools.reason_react.assert_called_once_with("solve problem", 5)

    @pytest.mark.asyncio
    async def test_reason_react_default_iterations(self):
        """reason_react uses default max_iterations of 10."""
        mcp.reasoning_tools.reason_react.return_value = "{}"
        await mcp.reason_react("task")
        mcp.reasoning_tools.reason_react.assert_called_once_with("task", 10)

    @pytest.mark.asyncio
    async def test_reason_react_error(self):
        """reason_react raises MCPToolError on failure."""
        mcp.reasoning_tools.reason_react.side_effect = Exception("react fail")
        with pytest.raises(MCPToolError, match="reason_react"):
            await mcp.reason_react("task")

    @pytest.mark.asyncio
    async def test_reason_tot_happy(self):
        """reason_tot delegates to reasoning_tools."""
        mcp.reasoning_tools.reason_tot.return_value = '{"tree": {"nodes": []}, "result": "done"}'
        result = await mcp.reason_tot("complex task", max_depth=4, branch_factor=2)
        assert "tree" in result
        mcp.reasoning_tools.reason_tot.assert_called_once_with("complex task", 4, 2)

    @pytest.mark.asyncio
    async def test_reason_tot_defaults(self):
        """reason_tot uses default max_depth and branch_factor."""
        mcp.reasoning_tools.reason_tot.return_value = "{}"
        await mcp.reason_tot("task")
        mcp.reasoning_tools.reason_tot.assert_called_once_with("task", 3, 3)

    @pytest.mark.asyncio
    async def test_reason_tot_error(self):
        """reason_tot raises MCPToolError on failure."""
        mcp.reasoning_tools.reason_tot.side_effect = Exception("tot fail")
        with pytest.raises(MCPToolError, match="reason_tot"):
            await mcp.reason_tot("task")

    @pytest.mark.asyncio
    async def test_reason_lats_happy(self):
        """reason_lats delegates to reasoning_tools."""
        mcp.reasoning_tools.reason_lats.return_value = '{"best_path": [], "result": "done"}'
        result = await mcp.reason_lats("task", max_simulations=5, max_depth=3)
        assert "best_path" in result
        mcp.reasoning_tools.reason_lats.assert_called_once_with("task", 5, 3)

    @pytest.mark.asyncio
    async def test_reason_lats_defaults(self):
        """reason_lats uses default max_simulations and max_depth."""
        mcp.reasoning_tools.reason_lats.return_value = "{}"
        await mcp.reason_lats("task")
        mcp.reasoning_tools.reason_lats.assert_called_once_with("task", 10, 4)

    @pytest.mark.asyncio
    async def test_reason_lats_error(self):
        """reason_lats raises MCPToolError on failure."""
        mcp.reasoning_tools.reason_lats.side_effect = Exception("lats fail")
        with pytest.raises(MCPToolError, match="reason_lats"):
            await mcp.reason_lats("task")


# ═══════════════════════════════════════════════════════════════════════════
# ORCHESTRATION TOOLS (4)
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPOrchestrationTools:
    """Tests for orchestration MCP tools."""

    @pytest.mark.asyncio
    async def test_run_pipeline_happy(self):
        """run_pipeline delegates to orchestration_tools."""
        mcp.orchestration_tools.run_pipeline.return_value = '{"results": ["ok", "ok"], "status": "completed"}'
        result = await mcp.run_pipeline(["step1", "step2"], sequential=True)
        assert "completed" in result
        mcp.orchestration_tools.run_pipeline.assert_called_once_with(["step1", "step2"], True)

    @pytest.mark.asyncio
    async def test_run_pipeline_default_sequential(self):
        """run_pipeline uses sequential=True by default."""
        mcp.orchestration_tools.run_pipeline.return_value = "{}"
        await mcp.run_pipeline(["step1"])
        mcp.orchestration_tools.run_pipeline.assert_called_once_with(["step1"], True)

    @pytest.mark.asyncio
    async def test_run_pipeline_error(self):
        """run_pipeline raises MCPToolError on failure."""
        mcp.orchestration_tools.run_pipeline.side_effect = Exception("pipeline fail")
        with pytest.raises(MCPToolError, match="run_pipeline"):
            await mcp.run_pipeline(["step"])

    @pytest.mark.asyncio
    async def test_run_parallel_happy(self):
        """run_parallel delegates to orchestration_tools."""
        mcp.orchestration_tools.run_parallel.return_value = '{"results": ["a", "b"]}'
        result = await mcp.run_parallel(["task1", "task2"])
        assert "results" in result
        mcp.orchestration_tools.run_parallel.assert_called_once_with(["task1", "task2"])

    @pytest.mark.asyncio
    async def test_run_parallel_error(self):
        """run_parallel raises MCPToolError on failure."""
        mcp.orchestration_tools.run_parallel.side_effect = Exception("parallel fail")
        with pytest.raises(MCPToolError, match="run_parallel"):
            await mcp.run_parallel(["t"])

    @pytest.mark.asyncio
    async def test_run_supervisor_happy(self):
        """run_supervisor delegates to orchestration_tools."""
        mcp.orchestration_tools.run_supervisor.return_value = '{"status": "completed"}'
        result = await mcp.run_supervisor("complex task", ["agent1", "agent2"])
        assert "completed" in result
        mcp.orchestration_tools.run_supervisor.assert_called_once_with("complex task", ["agent1", "agent2"])

    @pytest.mark.asyncio
    async def test_run_supervisor_error(self):
        """run_supervisor raises MCPToolError on failure."""
        mcp.orchestration_tools.run_supervisor.side_effect = Exception("supervisor fail")
        with pytest.raises(MCPToolError, match="run_supervisor"):
            await mcp.run_supervisor("task", ["a"])

    @pytest.mark.asyncio
    async def test_run_swarm_happy(self):
        """run_swarm delegates to orchestration_tools."""
        mcp.orchestration_tools.run_swarm.return_value = '{"swarm_id": "s-1", "status": "running"}'
        result = await mcp.run_swarm(["task1", "task2"], agent_count=5)
        assert "s-1" in result
        mcp.orchestration_tools.run_swarm.assert_called_once_with(["task1", "task2"], 5)

    @pytest.mark.asyncio
    async def test_run_swarm_default_agent_count(self):
        """run_swarm uses default agent_count of 3."""
        mcp.orchestration_tools.run_swarm.return_value = "{}"
        await mcp.run_swarm(["task"])
        mcp.orchestration_tools.run_swarm.assert_called_once_with(["task"], 3)

    @pytest.mark.asyncio
    async def test_run_swarm_error(self):
        """run_swarm raises MCPToolError on failure."""
        mcp.orchestration_tools.run_swarm.side_effect = Exception("swarm fail")
        with pytest.raises(MCPToolError, match="run_swarm"):
            await mcp.run_swarm(["task"])


# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM TOOLS (3)
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPSystemTools:
    """Tests for system MCP tools."""

    @pytest.mark.asyncio
    async def test_get_status_happy(self):
        """get_status delegates to system_tools."""
        mcp.system_tools.get_status.return_value = '{"status": "running", "uptime": 3600}'
        result = await mcp.get_status()
        assert "running" in result
        mcp.system_tools.get_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_status_error(self):
        """get_status raises MCPToolError on failure."""
        mcp.system_tools.get_status.side_effect = Exception("status fail")
        with pytest.raises(MCPToolError, match="get_status"):
            await mcp.get_status()

    @pytest.mark.asyncio
    async def test_get_config_happy(self):
        """get_config delegates to system_tools."""
        mcp.system_tools.get_config.return_value = '{"nexus_env": "development"}'
        result = await mcp.get_config()
        assert "development" in result
        mcp.system_tools.get_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_config_error(self):
        """get_config raises MCPToolError on failure."""
        mcp.system_tools.get_config.side_effect = Exception("config fail")
        with pytest.raises(MCPToolError, match="get_config"):
            await mcp.get_config()

    @pytest.mark.asyncio
    async def test_health_check_happy(self):
        """health_check delegates to system_tools."""
        mcp.system_tools.health_check.return_value = '{"healthy": true, "components": {"llm": "ok"}}'
        result = await mcp.health_check()
        assert "healthy" in result
        mcp.system_tools.health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_error(self):
        """health_check raises MCPToolError on failure."""
        mcp.system_tools.health_check.side_effect = Exception("health fail")
        with pytest.raises(MCPToolError, match="health_check"):
            await mcp.health_check()


# ═══════════════════════════════════════════════════════════════════════════
# BONUS TOOLS (4)
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPBonusTools:
    """Tests for bonus MCP tools (audit, rate-limit, research, RAG)."""

    @pytest.mark.asyncio
    async def test_audit_query_happy(self):
        """audit_query delegates to bonus_tools."""
        mcp.bonus_tools.audit_query.return_value = '{"logs": [], "total": 0}'
        result = await mcp.audit_query("user:admin", start_date="2026-01-01", end_date="2026-12-31", limit=50)
        assert "logs" in result
        mcp.bonus_tools.audit_query.assert_called_once_with("user:admin", "2026-01-01", "2026-12-31", 50)

    @pytest.mark.asyncio
    async def test_audit_query_defaults(self):
        """audit_query uses defaults for optional args."""
        mcp.bonus_tools.audit_query.return_value = "{}"
        await mcp.audit_query("test")
        mcp.bonus_tools.audit_query.assert_called_once_with("test", None, None, 100)

    @pytest.mark.asyncio
    async def test_audit_query_error(self):
        """audit_query raises MCPToolError on failure."""
        mcp.bonus_tools.audit_query.side_effect = Exception("audit fail")
        with pytest.raises(MCPToolError, match="audit_query"):
            await mcp.audit_query("test")

    @pytest.mark.asyncio
    async def test_rate_limit_status_happy(self):
        """rate_limit_status delegates to bonus_tools."""
        mcp.bonus_tools.rate_limit_status.return_value = '{"identifier": "default", "remaining": 50}'
        result = await mcp.rate_limit_status(identifier="user-1")
        assert "remaining" in result
        mcp.bonus_tools.rate_limit_status.assert_called_once_with("user-1")

    @pytest.mark.asyncio
    async def test_rate_limit_status_default(self):
        """rate_limit_status uses default identifier."""
        mcp.bonus_tools.rate_limit_status.return_value = "{}"
        await mcp.rate_limit_status()
        mcp.bonus_tools.rate_limit_status.assert_called_once_with("default")

    @pytest.mark.asyncio
    async def test_rate_limit_status_error(self):
        """rate_limit_status raises MCPToolError on failure."""
        mcp.bonus_tools.rate_limit_status.side_effect = Exception("rate-limit fail")
        with pytest.raises(MCPToolError, match="rate_limit_status"):
            await mcp.rate_limit_status()

    @pytest.mark.asyncio
    async def test_deep_research_happy(self):
        """deep_research delegates to bonus_tools."""
        mcp.bonus_tools.deep_research.return_value = '{"topic": "AI", "findings": []}'
        result = await mcp.deep_research("Artificial Intelligence", depth="deep")
        assert "AI" in result
        mcp.bonus_tools.deep_research.assert_called_once_with("Artificial Intelligence", "deep")

    @pytest.mark.asyncio
    async def test_deep_research_default_depth(self):
        """deep_research uses default depth."""
        mcp.bonus_tools.deep_research.return_value = "{}"
        await mcp.deep_research("topic")
        mcp.bonus_tools.deep_research.assert_called_once_with("topic", "medium")

    @pytest.mark.asyncio
    async def test_deep_research_error(self):
        """deep_research raises MCPToolError on failure."""
        mcp.bonus_tools.deep_research.side_effect = Exception("research fail")
        with pytest.raises(MCPToolError, match="deep_research"):
            await mcp.deep_research("topic")

    @pytest.mark.asyncio
    async def test_rag_query_happy(self):
        """rag_query delegates to bonus_tools."""
        mcp.bonus_tools.rag_query.return_value = '{"results": [{"text": "info"}], "query": "test"}'
        result = await mcp.rag_query("test", namespace="knowledge", top_k=3)
        assert "results" in result
        mcp.bonus_tools.rag_query.assert_called_once_with("test", "knowledge", 3)

    @pytest.mark.asyncio
    async def test_rag_query_defaults(self):
        """rag_query uses defaults for namespace and top_k."""
        mcp.bonus_tools.rag_query.return_value = "{}"
        await mcp.rag_query("query")
        mcp.bonus_tools.rag_query.assert_called_once_with("query", "knowledge", 5)

    @pytest.mark.asyncio
    async def test_rag_query_error(self):
        """rag_query raises MCPToolError on failure."""
        mcp.bonus_tools.rag_query.side_effect = Exception("rag fail")
        with pytest.raises(MCPToolError, match="rag_query"):
            await mcp.rag_query("query")


# ═══════════════════════════════════════════════════════════════════════════
# RESOURCE ENDPOINTS (3)
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPResources:
    """Tests for MCP resource endpoints (nexus://config, nexus://status, nexus://tools)."""

    def _run_with_event_loop(self, async_func, *args, **kwargs):
        """Run an async function with a fresh event loop."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(async_func(*args, **kwargs))
        finally:
            loop.close()

    def test_get_config_resource_returns_json(self):
        """nexus://config resource returns JSON configuration."""
        mcp.system_tools.get_config = AsyncMock(return_value='{"env": "development"}')
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = mcp.get_config_resource()
        finally:
            loop.close()
        data = json.loads(result)
        assert "env" in data
        assert data["env"] == "development"

    def test_get_config_resource_error_returns_error_json(self):
        """nexus://config returns error JSON when system_tools fails."""
        mcp.system_tools.get_config = AsyncMock(side_effect=Exception("cfg fail"))
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = mcp.get_config_resource()
        finally:
            loop.close()
        data = json.loads(result)
        assert "error" in data

    def test_get_status_resource_returns_json(self):
        """nexus://status resource returns JSON status."""
        mcp.system_tools.get_status = AsyncMock(
            return_value='{"agent": "NEXUS", "status": "running"}')
        # Create and set an event loop so run_until_complete works
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = mcp.get_status_resource()
        finally:
            loop.close()
        data = json.loads(result)
        assert data.get("agent") == "NEXUS"
        assert data.get("status") == "running"

    def test_get_status_resource_error_returns_error_json(self):
        """nexus://status returns error JSON when system_tools fails."""
        mcp.system_tools.get_status = AsyncMock(side_effect=Exception("status fail"))
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = mcp.get_status_resource()
        finally:
            loop.close()
        data = json.loads(result)
        assert "error" in data

    def test_get_tools_resource_returns_tool_list(self):
        """nexus://tools resource returns all 42 tool names."""
        result = mcp.get_tools_resource()
        data = json.loads(result)
        assert data["total"] >= 40
        assert "search_memory" in data["tools"]
        assert "get_status" in data["tools"]
        assert "deep_research" in data["tools"]
        assert "rag_query" in data["tools"]


# ═══════════════════════════════════════════════════════════════════════════
# PROMPT TEMPLATES (3)
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPPrompts:
    """Tests for MCP prompt template functions."""

    def test_research_task_prompt(self):
        """research_task prompt includes topic and steps."""
        result = mcp.research_task("Test Topic", depth="deep")
        assert "Test Topic" in result
        assert "deep" in result
        assert "search_memory" in result
        assert "web_search" in result
        assert "deep_research" in result
        assert "knowledge_add_entity" in result

    def test_research_task_default_depth(self):
        """research_task uses default depth of 'medium'."""
        result = mcp.research_task("Topic")
        assert "medium" in result

    def test_code_task_prompt(self):
        """code_task prompt includes description and steps."""
        result = mcp.code_task("Write a test", language="python")
        assert "Write a test" in result
        assert "python" in result
        assert "read_file" in result
        assert "search_files" in result
        assert "execute_code" in result
        assert "write_file" in result

    def test_code_task_default_language(self):
        """code_task uses default language 'python'."""
        result = mcp.code_task("Do something")
        assert "python" in result

    def test_analysis_task_prompt(self):
        """analysis_task prompt includes data description and steps."""
        result = mcp.analysis_task("Sales data Q1", analysis_type="statistical")
        assert "Sales data Q1" in result
        assert "statistical" in result
        assert "read_file" in result
        assert "execute_code" in result
        assert "knowledge_query" in result
        assert "store_memory" in result

    def test_analysis_task_default_type(self):
        """analysis_task uses default analysis_type 'general'."""
        result = mcp.analysis_task("Data")
        assert "general" in result


# ═══════════════════════════════════════════════════════════════════════════
# SERVER RUNNER
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPRunner:
    """Tests for run_mcp_server function."""

    def test_run_mcp_server_starts_with_defaults(self):
        """run_mcp_server starts MCP server on default host:port."""
        mcp.nexus_mcp.run = MagicMock()
        mcp.run_mcp_server()
        mcp.nexus_mcp.run.assert_called_once_with(transport="streamable-http")

    @patch("nexus.mcp_server.logger")
    def test_run_mcp_server_logs_startup(self, mock_logger):
        """run_mcp_server logs startup message with host/port."""
        mcp.nexus_mcp.run = MagicMock()
        mcp.run_mcp_server(host="127.0.0.1", port=9000)
        mock_logger.info.assert_called_once()
        args = mock_logger.info.call_args[0]
        # logger.info("format %s %d", host, port) → args = (fmt, "127.0.0.1", 9000)
        assert "127.0.0.1" in args
        assert 9000 in args


# ═══════════════════════════════════════════════════════════════════════════
# GLOBAL ERROR HANDLING — ALL TOOLS RAISE MCPToolError
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPGlobalErrorHandling:
    """Parametrized test: ALL tools properly raise MCPToolError on failure."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_name,args", [
        ("search_memory", ("query",)),
        ("store_memory", ("text",)),
        ("delete_memory", (["id"],)),
        ("list_namespaces", ()),
        ("memory_stats", ()),
        ("knowledge_query", ("entity",)),
        ("knowledge_add_entity", ("type", "name")),
        ("knowledge_add_relation", ("src", "tgt", "rel")),
        ("knowledge_search", ("query",)),
        ("knowledge_paths", ("src", "tgt")),
        ("llm_complete", ("prompt",)),
        ("llm_list_models", ()),
        ("llm_provider_status", ()),
        ("llm_stream", ("prompt",)),
        ("spawn_agent", ("type", "task")),
        ("list_agents", ()),
        ("agent_status", ("id",)),
        ("agent_delegate", ("src", "tgt", "task")),
        ("a2a_discover", ("url",)),
        ("execute_code", ("code",)),
        ("execute_sandboxed", ("cmd",)),
        ("install_package", ("pkg",)),
        ("read_file", ("path",)),
        ("write_file", ("path", "content")),
        ("list_files", ()),
        ("delete_file", ("path",)),
        ("move_file", ("src", "dst")),
        ("copy_file", ("src", "dst")),
        ("search_files", ("query",)),
        ("web_search", ("query",)),
        ("web_scrape", ("url",)),
        ("web_screenshot", ("url",)),
        ("reason_react", ("task",)),
        ("reason_tot", ("task",)),
        ("reason_lats", ("task",)),
        ("run_pipeline", (["task"],)),
        ("run_parallel", (["task"],)),
        ("run_supervisor", ("task", ["a"])),
        ("run_swarm", (["task"],)),
        ("get_status", ()),
        ("get_config", ()),
        ("health_check", ()),
        ("audit_query", ("query",)),
        ("rate_limit_status", ()),
        ("deep_research", ("topic",)),
        ("rag_query", ("query",)),
    ])
    async def test_all_tools_raise_mcptoolerror_on_failure(self, tool_name, args):
        """
        Every MCP tool function should catch exceptions from the underlying
        tool module and re-raise them as MCPToolError.
        """
        tool_func = getattr(mcp, tool_name)

        # Determine which module owns this tool
        module_map = {
            "search_memory": "memory_tools",
            "store_memory": "memory_tools",
            "delete_memory": "memory_tools",
            "list_namespaces": "memory_tools",
            "memory_stats": "memory_tools",
            "knowledge_query": "knowledge_tools",
            "knowledge_add_entity": "knowledge_tools",
            "knowledge_add_relation": "knowledge_tools",
            "knowledge_search": "knowledge_tools",
            "knowledge_paths": "knowledge_tools",
            "llm_complete": "llm_tools",
            "llm_list_models": "llm_tools",
            "llm_provider_status": "llm_tools",
            "llm_stream": "llm_tools",
            "spawn_agent": "agent_tools",
            "list_agents": "agent_tools",
            "agent_status": "agent_tools",
            "agent_delegate": "agent_tools",
            "a2a_discover": "agent_tools",
            "execute_code": "code_tools",
            "execute_sandboxed": "code_tools",
            "install_package": "code_tools",
            "read_file": "file_tools",
            "write_file": "file_tools",
            "list_files": "file_tools",
            "delete_file": "file_tools",
            "move_file": "file_tools",
            "copy_file": "file_tools",
            "search_files": "file_tools",
            "web_search": "web_tools",
            "web_scrape": "web_tools",
            "web_screenshot": "web_tools",
            "reason_react": "reasoning_tools",
            "reason_tot": "reasoning_tools",
            "reason_lats": "reasoning_tools",
            "run_pipeline": "orchestration_tools",
            "run_parallel": "orchestration_tools",
            "run_supervisor": "orchestration_tools",
            "run_swarm": "orchestration_tools",
            "get_status": "system_tools",
            "get_config": "system_tools",
            "health_check": "system_tools",
            "audit_query": "bonus_tools",
            "rate_limit_status": "bonus_tools",
            "deep_research": "bonus_tools",
            "rag_query": "bonus_tools",
        }

        mod_name = module_map[tool_name]
        mod = getattr(mcp, mod_name)

        # Find the underlying function name (may differ from tool name)
        # We use the same name convention: tool name == function name in module
        fn_name = tool_name
        fn = getattr(mod, fn_name)
        fn.side_effect = Exception(f"{tool_name} failed")

        with pytest.raises(MCPToolError) as exc_info:
            await tool_func(*args)

        assert tool_name in str(exc_info.value)
        assert f"{tool_name} failed" in str(exc_info.value)
