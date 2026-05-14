"""
NEXUS Comprehensive Tests — What a user MUST test before using the agent.

Tests cover what matters for production use:
  1. Gateway endpoints
  2. LLM Router with gemma-4-31b-it
  3. Path traversal protection
  4. Memory system
  5. Code execution (sandbox)
  6. Agent spawning and lifecycle
  7. Config validation
  8. Security (secrets, CORS)
  9. Knowledge Graph
  10. A2A Protocol
  11. Error handling
  12. Observability

Run: python -m pytest tests/test_all_new.py -v
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# ═══════════════════════════════════════════════════════════════
# 1. Gateway Endpoints
# ═══════════════════════════════════════════════════════════════

class TestGatewayEndpoints:
    """Tests for gateway HTTP endpoints."""

    def test_health_endpoint(self):
        """GET /health should return status OK."""
        from fastapi.testclient import TestClient
        from nexus.core.gateway import app

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "uptime_seconds" in data

    def test_status_endpoint(self):
        """GET /status should return agent info."""
        from fastapi.testclient import TestClient
        from nexus.core.gateway import app

        client = TestClient(app)
        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert data["agent"] == "NEXUS"
        assert data["status"] == "running"


# ═══════════════════════════════════════════════════════════════
# 2. LLM Router
# ═══════════════════════════════════════════════════════════════

class TestLLMRouter:
    """Tests for LLM router."""

    def test_gemma_in_function_calling_models(self):
        """Gemma-4-31b-it should be in function calling models."""
        from nexus.llm.router import GEMINI_FUNCTION_CALLING_MODELS
        assert "gemma-4-31b-it" in GEMINI_FUNCTION_CALLING_MODELS

    def test_llm_router_initializes(self):
        """LLM router should initialize."""
        from nexus.llm.router import LLMRouter
        router = LLMRouter()
        assert router is not None

    @pytest.mark.asyncio
    async def test_gemma_thought_tags_stripped(self):
        """Gemma <thought> tags should be stripped from response."""
        from nexus.llm.router import LLMRouter

        router = LLMRouter()
        router.settings = MagicMock()
        router.settings.google_api_key = "sk-test-google"
        router.settings.llm_timeout_seconds = 30

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "candidates": [{
                    "content": {
                        "parts": [
                            {"text": "thinking step", "thought": True},
                            {"text": "Final answer"},
                        ]
                    },
                    "finishReason": "STOP",
                }],
                "usageMetadata": {"promptTokenCount": 6, "candidatesTokenCount": 2, "totalTokenCount": 8},
            }
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            content, usage, finish, tools = await router._call_gemini_direct(
                model="gemma-4-31b-it",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.7,
                max_tokens=100,
            )

        assert "<thought>" not in content
        assert "Final answer" in content


# ═══════════════════════════════════════════════════════════════
# 3. Path Traversal Protection
# ═══════════════════════════════════════════════════════════════

class TestPathTraversalProtection:
    """Tests for path traversal protection."""

    def test_safe_path_within_working_dir(self, tmp_path):
        """Paths within working_dir should be allowed."""
        from nexus.api.gateway import _safe_path

        working_dir = tmp_path
        safe_dir = working_dir / "subdir"
        safe_dir.mkdir(exist_ok=True)
        (safe_dir / "file.txt").touch()

        result = _safe_path(str(safe_dir / "file.txt"), working_dir)
        assert result is not None
        assert isinstance(result, Path)

    def test_safe_path_traversal_blocked(self):
        """Path traversal should be blocked."""
        from nexus.api.gateway import _safe_path

        working_dir = Path(tempfile.gettempdir()) / "nexus_test"

        result = _safe_path("../../../etc/passwd", working_dir)
        assert result is None

    def test_safe_path_absolute_outside(self):
        """Absolute paths outside working_dir should be blocked."""
        from nexus.api.gateway import _safe_path

        working_dir = Path(tempfile.gettempdir()) / "nexus_test"

        result = _safe_path("C:/Windows/System32/config", working_dir)
        assert result is None


# ═══════════════════════════════════════════════════════════════
# 4. Memory System
# ═══════════════════════════════════════════════════════════════

class TestMemorySystem:
    """Tests for memory system."""

    def test_working_memory_initializes(self):
        """Working memory should initialize."""
        from nexus.memory.working import WorkingMemory

        wm = WorkingMemory(max_tokens=1000)
        assert wm is not None
        assert wm.max_tokens == 1000

    def test_working_memory_add(self):
        """Working memory should add messages via add()."""
        from nexus.memory.working import WorkingMemory, MessageRole

        wm = WorkingMemory(max_tokens=1000)
        wm.add(MessageRole.USER, "Hello")
        tokens = wm.total_tokens
        assert tokens > 0

    def test_memory_service_imports(self):
        """Memory service should import."""
        from nexus.memory.chroma_service import NexusMemoryService
        assert NexusMemoryService is not None


# ═══════════════════════════════════════════════════════════════
# 5. Code Execution (Sandbox)
# ═══════════════════════════════════════════════════════════════

class TestSandbox:
    """Tests for sandboxed code execution."""

    @pytest.mark.asyncio
    async def test_safe_python_executes(self):
        """Safe Python should execute."""
        from nexus.security.sandbox import LocalSandbox

        sandbox = LocalSandbox(timeout=10)
        result = await sandbox.execute_python("print(2 + 2)")
        assert result.exit_code == 0
        assert "4" in result.stdout

    @pytest.mark.asyncio
    async def test_timeout_enforced(self):
        """Timeout should be enforced."""
        from nexus.security.sandbox import LocalSandbox

        sandbox = LocalSandbox(timeout=1)
        result = await sandbox.execute_python("import time; time.sleep(10)")
        assert result.timed_out is True

    @pytest.mark.asyncio
    async def test_dangerous_pattern_blocked(self):
        """Dangerous patterns should be blocked."""
        from nexus.security.sandbox import LocalSandbox
        from nexus.core.exceptions import SandboxError

        sandbox = LocalSandbox()

        with pytest.raises(SandboxError):
            await sandbox.execute_python("rm -rf /")

    @pytest.mark.asyncio
    async def test_os_import_blocked(self):
        """os.system should be blocked."""
        from nexus.security.sandbox import LocalSandbox
        from nexus.core.exceptions import SandboxError

        sandbox = LocalSandbox()

        with pytest.raises(SandboxError):
            await sandbox.execute_python("import os; os.system('echo hacked')")


# ═══════════════════════════════════════════════════════════════
# 6. Agent Lifecycle
# ═══════════════════════════════════════════════════════════════

class TestAgentLifecycle:
    """Tests for agent lifecycle."""

    def test_agent_type_map(self):
        """AGENT_TYPE_MAP should have all agents."""
        from nexus.agents import AGENT_TYPE_MAP

        assert "researcher" in AGENT_TYPE_MAP
        assert "developer" in AGENT_TYPE_MAP
        assert "analyst" in AGENT_TYPE_MAP
        assert "operator" in AGENT_TYPE_MAP

    def test_researcher_agent(self):
        """Researcher agent should initialize."""
        from nexus.agents.researcher import ResearcherAgent

        agent = ResearcherAgent()
        assert agent.agent_type == "researcher"

    def test_developer_agent(self):
        """Developer agent should initialize."""
        from nexus.agents.developer import DeveloperAgent

        agent = DeveloperAgent()
        assert agent.agent_type == "developer"

    def test_analyst_agent(self):
        """Analyst agent should initialize."""
        from nexus.agents.analyst import AnalystAgent

        agent = AnalystAgent()
        assert agent.agent_type == "analyst"

    def test_operator_agent(self):
        """Operator agent should initialize."""
        from nexus.agents.operator import OperatorAgent

        agent = OperatorAgent()
        assert agent.agent_type == "operator"

    def test_agent_context(self):
        """AgentContext should create with task."""
        from nexus.agents.base import AgentContext

        ctx = AgentContext(task="Test task")
        assert ctx.task == "Test task"
        assert ctx.agent_id is not None


# ═══════════════════════════════════════════════════════════════
# 7. Config Validation
# ═══════════════════════════════════════════════════════════════

class TestConfig:
    """Tests for configuration."""

    def test_config_loads(self):
        """Config should load."""
        from nexus.core.config import get_settings

        settings = get_settings()
        assert settings.nexus_port > 0

    def test_environment_enum(self):
        """Environment enum should have values."""
        from nexus.core.config import Environment

        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.PRODUCTION.value == "production"

    def test_port_validation(self):
        """Port validation should work."""
        from nexus.core.config import NexusConfig

        config = NexusConfig(nexus_port=8080)
        assert config.nexus_port == 8080

        with pytest.raises(ValueError):
            NexusConfig(nexus_port=0)


# ═══════════════════════════════════════════════════════════════
# 8. Security
# ═══════════════════════════════════════════════════════════════

class TestSecurity:
    """Tests for security features."""

    def test_permission_manager_exists(self):
        """PermissionManager should exist."""
        from nexus.security.permissions import PermissionManager, PermissionAction

        pm = PermissionManager()
        req = pm.check_permission(PermissionAction.DELETE_FILE)
        assert req.requires_confirmation is True

    def test_cors_configured(self):
        """CORS should be configured."""
        from nexus.core.gateway import _frontend_origins
        assert "http://localhost:3000" in _frontend_origins

    def test_secrets_vault_initializes(self, tmp_path):
        """SecretsVault should initialize with pepper."""
        from nexus.security.vault import SecretsVault

        vault = SecretsVault(vault_dir=str(tmp_path / "vault"))
        assert hasattr(vault, "_pepper_file")


# ═══════════════════════════════════════════════════════════════
# 9. Knowledge Graph
# ═══════════════════════════════════════════════════════════════

class TestKnowledgeGraph:
    """Tests for knowledge graph."""

    def test_knowledge_graph_initializes(self):
        """Knowledge graph should initialize."""
        from nexus.knowledge.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        assert kg is not None

    def test_add_entity(self):
        """Should add entity."""
        from nexus.knowledge.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        node_id = kg.add_entity("TestEntity", entity_type="concept")
        assert node_id is not None

    def test_add_relationship(self):
        """Should add relationship."""
        from nexus.knowledge.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        kg.add_entity("Source", entity_type="entity")
        kg.add_entity("Target", entity_type="entity")
        kg.add_relationship("Source", "Target", "connects_to")


# ═══════════════════════════════════════════════════════════════
# 10. A2A Protocol
# ═══════════════════════════════════════════════════════════════

class TestA2AProtocol:
    """Tests for agent-to-agent protocol."""

    def test_message_type_enum(self):
        """MessageType enum should have values."""
        from nexus.core.a2a import MessageType

        assert MessageType.TASK_REQUEST.value == "task_request"
        assert MessageType.TASK_RESPONSE.value == "task_response"
        assert MessageType.PROGRESS_UPDATE.value == "progress_update"

    def test_task_state_enum(self):
        """TaskState enum should have values."""
        from nexus.core.a2a import TaskState

        assert TaskState.SUBMITTED.value == "submitted"
        assert TaskState.COMPLETED.value == "completed"

    def test_a2a_message_creates(self):
        """A2AMessage should create."""
        from nexus.core.a2a import A2AMessage, MessageType

        msg = A2AMessage(message_type=MessageType.TASK_REQUEST)
        assert msg.message_type == MessageType.TASK_REQUEST

    def test_a2a_protocol(self):
        """A2AProtocol should initialize."""
        from nexus.core.a2a import A2AProtocol

        protocol = A2AProtocol()
        assert protocol is not None


# ═══════════════════════════════════════════════════════════════
# 11. Error Handling
# ═══════════════════════════════════════════════════════════════

class TestErrorHandling:
    """Tests for error handling."""

    def test_llm_provider_error(self):
        """LLMProviderError should have correct message."""
        from nexus.core.exceptions import LLMProviderError

        error = LLMProviderError(provider="gemini", reason="API failed")
        assert "gemini" in error.message
        assert "API failed" in error.message

    def test_sandbox_error(self):
        """SandboxError should exist."""
        from nexus.core.exceptions import SandboxError

        error = SandboxError(reason="Dangerous code")
        assert "Dangerous code" in error.message

    def test_orchestrator_error(self):
        """OrchestratorError should exist."""
        from nexus.core.exceptions import OrchestratorError

        error = OrchestratorError(message="Task failed")
        assert "Task failed" in error.message

    def test_max_iterations_error(self):
        """MaxIterationsError should exist."""
        from nexus.core.exceptions import MaxIterationsError

        error = MaxIterationsError(max_iterations=10, task="test task")
        assert error is not None


# ═══════════════════════════════════════════════════════════════
# 12. Observability
# ═══════════════════════════════════════════════════════════════

class TestObservability:
    """Tests for observability/tracing."""

    def test_span_creates(self):
        """Span should create with timing."""
        from nexus.core.observability import Span

        span = Span(name="test_op")
        assert span.name == "test_op"

    def test_observability_manager(self):
        """ObservabilityManager should initialize."""
        from nexus.core.observability import ObservabilityManager

        manager = ObservabilityManager()
        assert manager is not None


# ═══════════════════════════════════════════════════════════════
# 13. Skill Lifecycle
# ═══════════════════════════════════════════════════════════════

class TestSkillLifecycle:
    """Tests for skill lifecycle."""

    def test_skill_stage_enum(self):
        """SkillStage enum should have values."""
        from nexus.orchestrator.skill_lifecycle import SkillStage

        assert SkillStage.DISCOVERY.value == "discovery"
        assert SkillStage.DESIGN.value == "design"
        assert SkillStage.IMPLEMENT.value == "implement"
        assert SkillStage.VALIDATE.value == "validate"
        assert SkillStage.DEPLOY.value == "deploy"

    def test_skill_status_enum(self):
        """SkillStatus enum should have values."""
        from nexus.orchestrator.skill_lifecycle import SkillStatus

        assert SkillStatus.DRAFT.value == "draft"
        assert SkillStatus.ACTIVE.value == "active"
        assert SkillStatus.DISCOVERED.value == "discovered"

    def test_skill_category_enum(self):
        """SkillCategory enum should have values."""
        from nexus.orchestrator.skill_lifecycle import SkillCategory

        assert SkillCategory.CODING.value == "coding"
        assert SkillCategory.RESEARCH.value == "research"


# ═══════════════════════════════════════════════════════════════
# 14. Orchestrator
# ═══════════════════════════════════════════════════════════════

class TestOrchestrator:
    """Tests for orchestrator."""

    def test_planner_node(self):
        """Planner node should exist."""
        from nexus.orchestrator.langgraph_engine import planner_node
        assert callable(planner_node)

    def test_executor_node(self):
        """Executor node should exist."""
        from nexus.orchestrator.langgraph_engine import executor_node
        assert callable(executor_node)

    def test_reflector_node(self):
        """Reflector node should exist."""
        from nexus.orchestrator.langgraph_engine import reflector_node
        assert callable(reflector_node)

    def test_nexus_state(self):
        """NexusState should be defined."""
        from nexus.orchestrator.langgraph_engine import NexusState
        assert NexusState is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
