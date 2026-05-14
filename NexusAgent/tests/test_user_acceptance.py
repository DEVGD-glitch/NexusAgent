"""
NEXUS User Acceptance Tests — Pre-flight checks before using the agent.

This is what YOU should run before using NEXUS in production.
Each test verifies a critical functionality.

Run: python -m pytest tests/test_user_acceptance.py -v
"""

import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# ═══════════════════════════════════════════════════════════════
# TEST 1: Can the agent start?
# ═══════════════════════════════════════════════════════════════

class TestAgentStartup:
    """Can NEXUS start and respond to health checks?"""

    def test_nexus_imports_cleanly(self):
        """NEXUS modules should import without errors."""
        from nexus.core.config import get_settings
        from nexus.llm.router import LLMRouter
        from nexus.agents.base import BaseAgent
        from nexus.memory.chroma_service import NexusMemoryService
        from nexus.security.vault import SecretsVault
        from nexus.core.gateway import app

        assert True

    def test_health_endpoint(self):
        """Health endpoint should return OK."""
        from fastapi.testclient import TestClient
        from nexus.core.gateway import app

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_status_endpoint(self):
        """Status endpoint should return agent info."""
        from fastapi.testclient import TestClient
        from nexus.core.gateway import app

        client = TestClient(app)
        response = client.get("/status")

        assert response.status_code == 200
        data = response.json()
        assert data["agent"] == "NEXUS"
        assert data["status"] == "running"


# ═══════════════════════════════════════════════════════════════
# TEST 2: Can the LLM respond?
# ═══════════════════════════════════════════════════════════════

class TestLLMConnectivity:
    """Can NEXUS connect to and use the LLM model?"""

    def test_llm_router_initializes(self):
        """LLM router should initialize without errors."""
        from nexus.llm.router import LLMRouter

        router = LLMRouter()
        assert router is not None

    def test_gemma_model_configured(self):
        """Gemma-4-31b-it should be in available function calling models."""
        from nexus.llm.router import GEMINI_FUNCTION_CALLING_MODELS

        assert "gemma-4-31b-it" in GEMINI_FUNCTION_CALLING_MODELS

    @pytest.mark.asyncio
    async def test_llm_mock_call_succeeds(self):
        """LLM should handle mock call without errors."""
        from nexus.llm.router import LLMRouter

        router = LLMRouter()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "candidates": [{
                    "content": {
                        "parts": [{"text": "Bonjour"}]
                    },
                    "finishReason": "STOP"
                }],
                "usageMetadata": {
                    "promptTokenCount": 6,
                    "candidatesTokenCount": 1,
                    "totalTokenCount": 7
                }
            }
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            content, usage, finish, tools = await router._call_gemini_direct(
                model="gemma-4-31b-it",
                messages=[{"role": "user", "content": "Dis bonjour"}],
                temperature=0.7,
                max_tokens=100,
            )

            assert content == "Bonjour"
            assert usage["prompt_tokens"] == 6


# ═══════════════════════════════════════════════════════════════
# TEST 3: Can the agent think (orchestrator)?
# ═══════════════════════════════════════════════════════════════

class TestOrchestrator:
    """Can NEXUS plan and execute tasks?"""

    @pytest.mark.asyncio
    async def test_orchestrator_runs_simple_task(self):
        """Orchestrator should handle a simple task."""
        from nexus.orchestrator.langgraph_engine import planner_node

        state = {
            "task": "Test task",
            "messages": [],
            "iteration": 0,
        }

        result = await planner_node(state)

        assert "plan" in result
        assert "sub_tasks" in result
        assert result["iteration"] == 1

    def test_orchestrator_router_exists(self):
        """Orchestrator router should exist."""
        from nexus.orchestrator.router import OrchestrationRouter

        router = OrchestrationRouter()
        assert router is not None

    def test_langgraph_engine_imports(self):
        """LangGraph engine should import without errors."""
        from nexus.orchestrator.langgraph_engine import (
            NexusState,
            planner_node,
            executor_node,
            reflector_node,
            build_nexus_graph,
        )

        assert NexusState is not None
        assert callable(planner_node)


# ═══════════════════════════════════════════════════════════════
# TEST 4: Is memory working?
# ═══════════════════════════════════════════════════════════════

class TestMemory:
    """Can NEXUS store and retrieve memories?"""

    @pytest.fixture
    def memory_service(self, tmp_path):
        """Create a clean memory service."""
        with patch.dict("os.environ", {"CHROMA_PERSIST_DIR": str(tmp_path)}):
            from nexus.memory.chroma_service import NexusMemoryService
            return NexusMemoryService(persist_dir=str(tmp_path))

    @pytest.mark.asyncio
    async def test_store_document(self, memory_service):
        """Should store a document in valid namespace."""
        doc_id = await memory_service.store(
            text="Testing memory storage",
            namespace="conversations",
        )
        assert doc_id is not None

    @pytest.mark.asyncio
    async def test_search_document(self, memory_service):
        """Should search stored document."""
        await memory_service.store(
            text="Important information about AI agents",
            namespace="conversations",
        )

        results = await memory_service.search(
            query="AI agents",
            namespace="conversations",
            top_k=5,
        )
        assert results is not None

    def test_working_memory(self):
        """Working memory should track tokens."""
        from nexus.memory.working import WorkingMemory, MessageRole

        mem = WorkingMemory(max_tokens=1000)
        mem.add(MessageRole.USER, "Hello")
        tokens = mem.total_tokens
        assert tokens > 0


# ═══════════════════════════════════════════════════════════════
# TEST 5: Is code execution sandboxed?
# ═══════════════════════════════════════════════════════════════

class TestSandbox:
    """Can NEXUS execute code safely?"""

    @pytest.mark.asyncio
    async def test_safe_code_runs(self):
        """Safe Python code should execute."""
        from nexus.security.sandbox import LocalSandbox

        sandbox = LocalSandbox(timeout=10)
        result = await sandbox.execute_python("print('Hello from sandbox')")

        assert result.exit_code == 0
        assert "Hello from sandbox" in result.stdout

    @pytest.mark.asyncio
    async def test_dangerous_code_blocked(self):
        """Dangerous code should be blocked."""
        from nexus.security.sandbox import LocalSandbox
        from nexus.core.exceptions import SandboxError

        sandbox = LocalSandbox()

        with pytest.raises(SandboxError):
            await sandbox.execute_python("rm -rf /")

    @pytest.mark.asyncio
    async def test_subprocess_injection_blocked(self):
        """Subprocess injection should be blocked."""
        from nexus.security.sandbox import LocalSandbox
        from nexus.core.exceptions import SandboxError

        sandbox = LocalSandbox()

        with pytest.raises(SandboxError):
            await sandbox.execute_python('subprocess.run(["rm", "-rf", "/"])')

    @pytest.mark.asyncio
    async def test_timeout_enforced(self):
        """Long-running code should timeout."""
        from nexus.security.sandbox import LocalSandbox

        sandbox = LocalSandbox(timeout=2)
        result = await sandbox.execute_python("import time; time.sleep(10)")

        assert result.timed_out is True


# ═══════════════════════════════════════════════════════════════
# TEST 6: Are secrets protected?
# ═══════════════════════════════════════════════════════════════

class TestSecrets:
    """Are API keys and secrets properly protected?"""

    def test_vault_creates_pepper(self, tmp_path):
        """Vault should create a pepper file."""
        from nexus.security.vault import SecretsVault

        vault = SecretsVault(vault_dir=str(tmp_path / "vault"))
        assert hasattr(vault, "_pepper_file")
        # Pepper file created or exists
        assert vault._pepper_file is not None

    def test_vault_store_retrieve(self, tmp_path):
        """Should store and retrieve secrets."""
        from nexus.security.vault import SecretsVault

        vault = SecretsVault(vault_dir=str(tmp_path / "vault"))

        success = vault.store("TEST_API_KEY", "secret123")
        assert success is True

        retrieved = vault.retrieve("TEST_API_KEY")
        assert retrieved == "secret123"

    def test_permission_manager_dangerous_actions(self):
        """Dangerous actions should require permission."""
        from nexus.security.permissions import PermissionManager, PermissionAction

        pm = PermissionManager()

        req = pm.check_permission(PermissionAction.DELETE_FILE)
        assert req.requires_confirmation is True

        req = pm.check_permission(PermissionAction.EXECUTE_CODE)
        assert req.requires_confirmation is True


# ═══════════════════════════════════════════════════════════════
# TEST 7: Is the API secure?
# ═══════════════════════════════════════════════════════════════

class TestAPISecurity:
    """Are API endpoints properly secured?"""

    def test_path_traversal_blocked(self):
        """Path traversal attempts should be blocked."""
        from nexus.api.gateway import _safe_path

        working_dir = Path("C:/nexus_data")
        result = _safe_path("../../../etc/passwd", working_dir)
        assert result is None

        result = _safe_path("C:/Windows/System32/file.txt", working_dir)
        assert result is None

    def test_cors_configured(self):
        """CORS should be configured for allowed origins."""
        from nexus.core.gateway import _frontend_origins

        assert "http://localhost:3000" in _frontend_origins


# ═══════════════════════════════════════════════════════════════
# TEST 8: Can agents be spawned?
# ═══════════════════════════════════════════════════════════════

class TestAgents:
    """Can NEXUS spawn and use specialized agents?"""

    def test_agent_types_registered(self):
        """All agent types should be registered."""
        from nexus.agents import AGENT_TYPE_MAP

        assert "researcher" in AGENT_TYPE_MAP
        assert "developer" in AGENT_TYPE_MAP
        assert "analyst" in AGENT_TYPE_MAP
        assert "operator" in AGENT_TYPE_MAP

    def test_researcher_agent_works(self):
        """Researcher agent should initialize."""
        from nexus.agents.researcher import ResearcherAgent

        agent = ResearcherAgent()
        assert agent.agent_type == "researcher"

    def test_developer_agent_works(self):
        """Developer agent should initialize."""
        from nexus.agents.developer import DeveloperAgent

        agent = DeveloperAgent()
        assert agent.agent_type == "developer"

    def test_agent_context_conversation(self):
        """Agent context should track conversation."""
        from nexus.agents.base import AgentContext

        ctx = AgentContext(task="test")
        assert ctx.task == "test"
        assert ctx.agent_id is not None
        assert isinstance(ctx.conversation, list)


# ═══════════════════════════════════════════════════════════════
# TEST 9: Is configuration valid?
# ═══════════════════════════════════════════════════════════════

class TestConfiguration:
    """Is NEXUS configuration correct?"""

    def test_config_loads(self):
        """Config should load from environment."""
        from nexus.core.config import get_settings

        settings = get_settings()
        assert settings.nexus_port > 0
        assert settings.nexus_env is not None

    def test_port_in_valid_range(self):
        """Port should be in valid range."""
        from nexus.core.config import NexusConfig

        config = NexusConfig(nexus_port=8080)
        assert config.nexus_port == 8080

        with pytest.raises(ValueError):
            NexusConfig(nexus_port=0)

    def test_working_dir_configurable(self):
        """Working directory should be configurable."""
        from nexus.core.config import NexusConfig

        config = NexusConfig(nexus_working_dir="./test_data")
        assert config.nexus_working_dir == "./test_data"


# ═══════════════════════════════════════════════════════════════
# TEST 10: Error handling
# ═══════════════════════════════════════════════════════════════

class TestErrors:
    """Does NEXUS handle errors gracefully?"""

    def test_llm_error_has_details(self):
        """LLM errors should have provider and reason in message."""
        from nexus.core.exceptions import LLMProviderError

        error = LLMProviderError(provider="gemini", reason="API failed", model="gemma-4-31b-it")
        assert "gemini" in error.message
        assert "API failed" in error.message

    @pytest.mark.asyncio
    async def test_sandbox_error_raised(self):
        """Sandbox errors should be raised for dangerous code."""
        from nexus.core.exceptions import SandboxError
        from nexus.security.sandbox import LocalSandbox

        sandbox = LocalSandbox()
        with pytest.raises(SandboxError):
            await sandbox.execute_python("rm -rf /")

    def test_orchestrator_error_exists(self):
        """Orchestrator errors should exist."""
        from nexus.core.exceptions import OrchestratorError

        error = OrchestratorError(message="Task failed")
        assert "Task failed" in error.message


# ═══════════════════════════════════════════════════════════════
# TEST 11: Knowledge Graph
# ═══════════════════════════════════════════════════════════════

class TestKnowledge:
    """Can NEXUS manage knowledge graphs?"""

    def test_knowledge_graph_imports(self):
        """Knowledge graph should import without errors."""
        from nexus.knowledge.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        assert kg is not None

    def test_add_entity(self):
        """Should add entities to graph."""
        from nexus.knowledge.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        node_id = kg.add_entity("TestEntity", entity_type="concept")
        assert node_id is not None

    def test_search_entities(self):
        """Should search entities."""
        from nexus.knowledge.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        # add some entities first
        kg.add_entity("PythonFunction", entity_type="concept")
        kg.add_entity("JavaScriptFunction", entity_type="concept")
        results = kg.search_entities("function")
        assert isinstance(results, list)


# ═══════════════════════════════════════════════════════════════
# TEST 12: A2A Protocol (agent communication)
# ═══════════════════════════════════════════════════════════════

class TestA2A:
    """Can agents communicate with each other?"""

    def test_message_types_defined(self):
        """All message types should be defined."""
        from nexus.core.a2a import MessageType

        assert MessageType.TASK_REQUEST.value == "task_request"
        assert MessageType.TASK_RESPONSE.value == "task_response"
        assert MessageType.PROGRESS_UPDATE.value == "progress_update"

    def test_task_delegate_creates(self):
        """TaskDelegate should be creatable with task_id and target_agent."""
        from nexus.core.a2a import TaskDelegate

        delegate = TaskDelegate(
            task_id="test-task-123",
            target_agent="researcher",
        )
        assert delegate.task_id == "test-task-123"
        assert delegate.target_agent == "researcher"

    def test_a2a_protocol_creates(self):
        """A2AProtocol should initialize."""
        from nexus.core.a2a import A2AProtocol

        protocol = A2AProtocol()
        assert protocol is not None


# ═══════════════════════════════════════════════════════════════
# TEST 13: MCP Server tools
# ═══════════════════════════════════════════════════════════════

class TestMCPServer:
    """Do MCP tools exist and work?"""

    def test_mcp_server_instance(self):
        """MCP server should be instantiated."""
        from nexus.mcp_server import nexus_mcp
        assert nexus_mcp is not None

    def test_tool_functions_exist(self):
        """Tool handler functions should exist."""
        from nexus.mcp_server import (
            read_file,
            write_file,
            execute_code,
            spawn_agent,
        )

        assert callable(read_file)
        assert callable(write_file)
        assert callable(execute_code)
        assert callable(spawn_agent)

    @pytest.mark.asyncio
    async def test_execute_code_python(self):
        """execute_code should run Python code."""
        from nexus.mcp_server import execute_code

        result = await execute_code(code="print(2 + 2)", language="python")
        data = json.loads(result)
        assert data["exit_code"] == 0
        assert "4" in data["stdout"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
