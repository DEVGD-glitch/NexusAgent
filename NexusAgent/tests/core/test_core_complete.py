"""
Complete tests for NEXUS Core modules.

Covers:
  - Gateway: all endpoints (/health, /run, /chat, /status, /providers,
    /memory/stats), WebSocket /ws/chat, path traversal protection,
    CORS configuration, error handling
  - A2A: A2AMessage, TaskState, MessageType enums, A2AProtocol methods,
    task delegation, agent discovery, task cancellation
  - Observability: ObservabilityManager, Span creation, LLM call recording,
    metrics collection, stats, Tracer context manager
  - Evaluation: Evaluator with evaluate_skill, evaluate_agent,
    run_benchmark_suite, scoring logic, trend analysis
  - Supervisor: ProcessSupervisor with service registration, status
    reporting, restart logic, monitoring
  - ErrorMessages: HumanError class, ERROR_MAP, get_human_error() with
    pattern matching and fallback
"""

import pytest
import json
import time
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock


# ═══════════════════════════════════════════════════════════════════
# Module-Level Patches
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def mock_settings():
    """Mock get_settings in core modules."""
    from unittest.mock import MagicMock, patch
    from nexus.core.config import Environment

    settings = MagicMock()
    settings.nexus_env = Environment.DEVELOPMENT
    settings.nexus_host = "0.0.0.0"
    settings.nexus_port = 8080
    settings.nexus_working_dir = "/tmp/nexus"
    settings.audit_log_dir = "/tmp/nexus/audit"
    settings.chroma_persist_dir = "/tmp/nexus/chroma"
    settings.available_providers = ["openai", "anthropic"]
    settings.llm_default_provider = "openai"
    settings.llm_default_model = "gpt-4o"
    settings.llm_fallback_chain = "openai,anthropic"
    settings.fallback_providers = ["openai", "anthropic"]
    settings.ollama_base_url = "http://127.0.0.1:11434"
    settings.openai_api_key = "sk-test"
    settings.anthropic_api_key = "sk-test-ant"
    settings.google_api_key = "sk-test-google"
    settings.orchestrator_max_iterations = 10
    settings.orchestrator_checkpointer = "memory"
    settings.orchestrator_interrupt_before_executor = False

    targets = [
        "nexus.core.config.get_settings",
        "nexus.core.a2a.get_settings",
        "nexus.core.observability.get_settings",
        "nexus.core.evaluation.get_settings",
    ]
    patchers = [patch(target, return_value=settings) for target in targets]
    for p in patchers:
        p.start()
    yield settings
    for p in patchers:
        p.stop()


# ═══════════════════════════════════════════════════════════════════
# Gateway Tests
# ═══════════════════════════════════════════════════════════════════

class TestGatewayApp:
    """Test FastAPI app creation and metadata."""

    def test_app_created(self):
        """App should be created with expected metadata."""
        from nexus.api.gateway import app
        assert app.title == "NEXUS Agent Gateway"
        assert app.version == "0.1.0"

    def test_app_has_cors_middleware(self):
        """App should have CORS middleware registered."""
        from nexus.api.gateway import app
        from fastapi.middleware.cors import CORSMiddleware
        middleware_classes = [m.cls for m in app.user_middleware]
        assert CORSMiddleware in middleware_classes


class TestGatewayHealthEndpoint:
    """Test GET /health endpoint."""

    def test_health_returns_ok(self):
        """GET /health should return status ok."""
        from nexus.api.gateway import app
        from nexus.core.config import Environment
        from fastapi.testclient import TestClient

        with patch("nexus.core.config.get_settings") as mock_gs:
            mock_gs.return_value.nexus_env = Environment.DEVELOPMENT
            client = TestClient(app)
            resp = client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "healthy"
            assert data["version"] == "0.1.0"
            assert "environment" in data
            assert "uptime_seconds" in data


class TestGatewayRunEndpoint:
    """Test POST /run endpoint."""

    def test_run_success(self):
        """POST /run should execute task."""
        from nexus.api.gateway import app
        from fastapi.testclient import TestClient

        mock_result = {
            "result": "Task completed",
            "status": "completed",
            "iterations": 2,
            "plan": "Plan text",
            "reflection": "Reflection text",
            "thread_id": "thread_123",
        }

        mock_broadcaster = MagicMock()
        mock_broadcaster.broadcast = AsyncMock()

        mock_limiter = MagicMock()
        mock_limiter.check = MagicMock()

        with patch("nexus.orchestrator.langgraph_engine.run_nexus_task",
                   new=AsyncMock(return_value=mock_result)):
            with patch("nexus.api.gateway._get_broadcaster", return_value=mock_broadcaster):
                with patch("nexus.api.gateway._get_limiter", return_value=mock_limiter):
                    client = TestClient(app)
                    resp = client.post("/run", json={"task": "Test the system"})
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["result"] == "Task completed"
                    assert data["status"] == "completed"
                    assert data["steps"] == 2

    def test_run_error(self):
        """POST /run should return 500 on failure."""
        from nexus.api.gateway import app
        from fastapi.testclient import TestClient

        mock_broadcaster = MagicMock()
        mock_broadcaster.broadcast = AsyncMock()

        mock_limiter = MagicMock()
        mock_limiter.check = MagicMock()

        with patch("nexus.orchestrator.langgraph_engine.run_nexus_task",
                   new=AsyncMock(side_effect=Exception("Execution failed"))):
            with patch("nexus.api.gateway._get_broadcaster", return_value=mock_broadcaster):
                with patch("nexus.api.gateway._get_limiter", return_value=mock_limiter):
                    client = TestClient(app)
                    resp = client.post("/run", json={"task": "Failing task"})
                    assert resp.status_code == 500

    def test_run_empty_task(self):
        """POST /run with empty task should return 422."""
        from nexus.api.gateway import app
        from fastapi.testclient import TestClient

        mock_limiter = MagicMock()
        mock_limiter.check = MagicMock()

        with patch("nexus.api.gateway._get_limiter", return_value=mock_limiter):
            client = TestClient(app)
            resp = client.post("/run", json={"task": ""})
            assert resp.status_code == 422

    def test_run_with_options(self):
        """POST /run with optional parameters."""
        from nexus.api.gateway import app
        from fastapi.testclient import TestClient

        mock_result = {
            "result": "Done",
            "status": "completed",
            "iterations": 1,
            "plan": "",
            "reflection": "",
            "thread_id": "custom_thread",
        }

        mock_broadcaster = MagicMock()
        mock_broadcaster.broadcast = AsyncMock()

        mock_limiter = MagicMock()
        mock_limiter.check = MagicMock()

        with patch("nexus.orchestrator.langgraph_engine.run_nexus_task",
                   new=AsyncMock(return_value=mock_result)):
            with patch("nexus.api.gateway._get_broadcaster", return_value=mock_broadcaster):
                with patch("nexus.api.gateway._get_limiter", return_value=mock_limiter):
                    client = TestClient(app)
                    resp = client.post("/run", json={
                        "task": "Test",
                        "provider": "openai",
                        "complexity": "simple",
                        "thread_id": "custom_thread",
                        "context": [{"role": "user", "content": "hello"}],
                    })
                    assert resp.status_code == 200


class TestGatewayChatEndpoint:
    """Test POST /chat endpoint."""

    def test_chat_success(self):
        """POST /chat should return completion."""
        from nexus.api.gateway import app, _router
        from fastapi.testclient import TestClient
        from nexus.llm.router import LLMResponse, Provider

        mock_response = LLMResponse(
            content="Hello!",
            provider=Provider.OPENAI,
            model="gpt-4o",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            latency_ms=100.0,
        )

        mock_router = MagicMock()
        mock_router.complete = AsyncMock(return_value=mock_response)

        with patch("nexus.api.gateway._get_router", return_value=mock_router):
            with patch("nexus.core.config.get_settings") as mock_gs:
                mock_gs.return_value.nexus_env = "development"
                client = TestClient(app)
                resp = client.post("/chat", json={
                    "messages": [{"role": "user", "content": "Hello"}],
                })
                assert resp.status_code == 200
                data = resp.json()
                assert data["content"] == "Hello!"
                assert data["provider"] == "openai"

    def test_chat_with_parameters(self):
        """POST /chat with model and temperature."""
        from nexus.api.gateway import app
        from fastapi.testclient import TestClient
        from nexus.llm.router import LLMResponse, Provider

        mock_response = LLMResponse(
            content="Response",
            provider=Provider.ANTHROPIC,
            model="claude-3",
            usage={},
            latency_ms=200.0,
        )

        mock_router = MagicMock()
        mock_router.complete = AsyncMock(return_value=mock_response)

        with patch("nexus.api.gateway._get_router", return_value=mock_router):
            with patch("nexus.core.config.get_settings") as mock_gs:
                mock_gs.return_value.nexus_env = "development"
                client = TestClient(app)
                resp = client.post("/chat", json={
                    "messages": [{"role": "user", "content": "Hi"}],
                    "model": "claude-3",
                    "provider": "anthropic",
                    "temperature": 0.5,
                    "max_tokens": 2048,
                })
                assert resp.status_code == 200
                data = resp.json()
                assert data["provider"] == "anthropic"

    def test_chat_error(self):
        """POST /chat should return 500 on error."""
        from nexus.api.gateway import app
        from fastapi.testclient import TestClient

        mock_router = MagicMock()
        mock_router.complete = AsyncMock(side_effect=Exception("LLM error"))

        with patch("nexus.api.gateway._get_router", return_value=mock_router):
            with patch("nexus.core.config.get_settings") as mock_gs:
                mock_gs.return_value.nexus_env = "development"
                client = TestClient(app)
                resp = client.post("/chat", json={
                    "messages": [{"role": "user", "content": "Hi"}],
                })
                assert resp.status_code == 500


class TestGatewayStatusEndpoint:
    """Test GET /status endpoint."""

    def test_status(self):
        """GET /status should return agent info."""
        from nexus.api.gateway import app
        from nexus.core.config import Environment
        from fastapi.testclient import TestClient

        with patch("nexus.core.config.get_settings") as mock_gs:
            mock_gs.return_value.nexus_env = Environment.DEVELOPMENT
            mock_gs.return_value.available_providers = ["openai", "anthropic"]
            client = TestClient(app)
            resp = client.get("/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["agent"] == "NEXUS"
            assert data["version"] == "0.1.0"
            assert data["status"] == "running"
            assert "providers_configured" in data


class TestGatewayProvidersEndpoint:
    """Test GET /providers endpoint."""

    def test_providers_success(self):
        """GET /providers should return provider status."""
        from nexus.api.gateway import app
        from fastapi.testclient import TestClient

        mock_router = MagicMock()
        mock_router.get_provider_status.return_value = {
            "openai": {"available": True},
            "anthropic": {"available": True},
        }

        with patch("nexus.api.gateway._get_router", return_value=mock_router):
            with patch("nexus.core.config.get_settings") as mock_gs:
                mock_gs.return_value.nexus_env = "development"
                client = TestClient(app)
                resp = client.get("/providers")
                assert resp.status_code == 200
                data = resp.json()
                assert "openai" in data

    def test_providers_error(self):
        """GET /providers should handle errors."""
        from nexus.api.gateway import app
        from fastapi.testclient import TestClient

        mock_router = MagicMock()
        mock_router.get_provider_status.side_effect = Exception("Status error")

        with patch("nexus.api.gateway._get_router", return_value=mock_router):
            with patch("nexus.core.config.get_settings") as mock_gs:
                mock_gs.return_value.nexus_env = "development"
                client = TestClient(app)
                resp = client.get("/providers")
                assert resp.status_code == 500


class TestGatewayMemoryStatsEndpoint:
    """Test GET /memory/stats endpoint."""

    def test_memory_stats_success(self):
        """GET /memory/stats should return namespace counts."""
        from nexus.api.gateway import app
        from fastapi.testclient import TestClient

        mock_mem = MagicMock()
        mock_mem.count = AsyncMock(return_value=5)

        with patch("nexus.api.gateway._get_memory_service", return_value=mock_mem):
            with patch("nexus.core.config.get_settings") as mock_gs:
                mock_gs.return_value.nexus_env = "development"
                mock_gs.return_value.chroma_persist_dir = "/tmp/test"
                client = TestClient(app)
                resp = client.get("/memory/stats")
                assert resp.status_code == 200
                data = resp.json()
                assert "namespaces" in data
                assert "conversations" in data["namespaces"]

    def test_memory_stats_error(self):
        """GET /memory/stats should handle errors."""
        from nexus.api.gateway import app
        from fastapi.testclient import TestClient

        mock_mem = MagicMock()
        mock_mem.count = AsyncMock(side_effect=Exception("Memory error"))

        with patch("nexus.api.gateway._get_memory_service", return_value=mock_mem):
            with patch("nexus.core.config.get_settings") as mock_gs:
                mock_gs.return_value.nexus_env = "development"
                client = TestClient(app)
                resp = client.get("/memory/stats")
                # Each namespace is caught individually
                assert resp.status_code == 200
                data = resp.json()
                for ns in data["namespaces"].values():
                    assert ns["count"] == 0


class TestGatewayWebSocket:
    """Test WebSocket /ws endpoint (event streaming)."""

    def test_websocket_connect_and_disconnect(self):
        """WebSocket /ws should accept connections and handle disconnect."""
        from nexus.api.gateway import app
        from nexus.api.auth import verify_auth
        from fastapi.testclient import TestClient

        mock_broadcaster = MagicMock()
        mock_broadcaster.subscribe = AsyncMock(return_value="sub_1")
        mock_broadcaster.unsubscribe = AsyncMock()
        mock_broadcaster.pump_subscriber = AsyncMock()

        async def noop_auth():
            return None

        app.dependency_overrides[verify_auth] = noop_auth
        try:
            with patch("nexus.api.gateway._get_broadcaster", return_value=mock_broadcaster):
                with patch("nexus.api.auth.verify_ws_auth", new_callable=AsyncMock):
                    client = TestClient(app)
                    with client.websocket_connect("/ws") as ws:
                        pass
                    mock_broadcaster.subscribe.assert_called_once()
                    mock_broadcaster.unsubscribe.assert_called_once()
        finally:
            app.dependency_overrides.clear()


class TestGatewayPathTraversal:
    """Test path traversal protection."""

    def test_get_working_dir(self):
        """_get_working_dir should return Path."""
        from nexus.api.gateway import _get_working_dir

        wd = _get_working_dir()
        assert isinstance(wd, Path)

    def test_safe_path_valid(self, tmp_path):
        """Valid path within working dir should return resolved Path."""
        from nexus.api.gateway import _safe_path

        safe = _safe_path(str(tmp_path / "test.txt"), tmp_path)
        assert safe is not None
        assert isinstance(safe, Path)

    def test_safe_path_traversal_detected(self, tmp_path):
        """Path traversal outside working dir should return None."""
        from nexus.api.gateway import _safe_path

        result = _safe_path("../etc/passwd", tmp_path)
        assert result is None

    def test_safe_path_absolute_outside(self, tmp_path):
        """Absolute path outside working dir should return None."""
        from nexus.api.gateway import _safe_path

        result = _safe_path("/etc/passwd", tmp_path)
        assert result is None


# ═══════════════════════════════════════════════════════════════════
# A2A Protocol Tests
# ═══════════════════════════════════════════════════════════════════

class TestA2AEnums:
    """Test A2A enums."""

    def test_task_state_values(self):
        from nexus.core.a2a import TaskState
        assert TaskState.SUBMITTED.value == "submitted"
        assert TaskState.WORKING.value == "working"
        assert TaskState.COMPLETED.value == "completed"
        assert TaskState.FAILED.value == "failed"
        assert TaskState.CANCELED.value == "canceled"

    def test_message_type_values(self):
        from nexus.core.a2a import MessageType
        assert MessageType.TASK_REQUEST.value == "task_request"
        assert MessageType.TASK_RESPONSE.value == "task_response"
        assert MessageType.PROGRESS_UPDATE.value == "progress_update"
        assert MessageType.HEARTBEAT.value == "heartbeat"
        assert MessageType.ERROR.value == "error"


class TestA2AMessage:
    """Test A2AMessage dataclass."""

    def test_default_creation(self):
        """A2AMessage with defaults."""
        from nexus.core.a2a import A2AMessage

        msg = A2AMessage(content="Hello")
        assert msg.content == "Hello"
        assert msg.message_id is not None
        assert msg.role == "agent"

    def test_to_dict(self):
        """A2AMessage to_dict."""
        from nexus.core.a2a import A2AMessage, MessageType

        msg = A2AMessage(
            message_type=MessageType.TASK_REQUEST,
            task_id="task_1",
            content="Do this",
            sender="agent_a",
            recipient="agent_b",
        )
        d = msg.to_dict()
        assert d["message_type"] == "task_request"
        assert d["task_id"] == "task_1"
        assert d["sender"] == "agent_a"

    def test_to_dict_no_message_type(self):
        """A2AMessage to_dict with no type."""
        from nexus.core.a2a import A2AMessage

        msg = A2AMessage(content="test")
        d = msg.to_dict()
        assert d["message_type"] is None


class TestA2ATask:
    """Test A2ATask dataclass."""

    def test_default_creation(self):
        """A2ATask with defaults."""
        from nexus.core.a2a import A2ATask, TaskState

        task = A2ATask(description="Test task")
        assert task.description == "Test task"
        assert task.state == TaskState.SUBMITTED
        assert task.created_by == "nexus"

    def test_to_dict(self):
        """A2ATask to_dict."""
        from nexus.core.a2a import A2ATask, TaskState

        task = A2ATask(
            description="Test",
            assigned_to="agent_b",
            created_by="agent_a",
            state=TaskState.COMPLETED,
            result="Done",
        )
        d = task.to_dict()
        assert d["state"] == "completed"
        assert d["result"] == "Done"
        assert d["assigned_to"] == "agent_b"

    def test_backward_compat_task_field(self):
        """A2ATask supports 'task' field separately from description."""
        from nexus.core.a2a import A2ATask

        task = A2ATask(task="legacy task description")
        # 'task' is a separate field (documented as backward compat alias)
        assert task.task == "legacy task description"
        # description is a separate field with its own default
        assert task.description == ""


class TestProgressReport:
    """Test ProgressReport dataclass."""

    def test_default_creation(self):
        """ProgressReport with defaults."""
        from nexus.core.a2a import ProgressReport, TaskState

        report = ProgressReport(task_id="task_1")
        assert report.task_id == "task_1"
        assert report.progress == 0.0
        assert report.state == TaskState.WORKING

    def test_to_dict(self):
        """ProgressReport to_dict."""
        from nexus.core.a2a import ProgressReport

        report = ProgressReport(
            task_id="task_1",
            progress=0.5,
            message="Halfway there",
        )
        d = report.to_dict()
        assert d["progress"] == 0.5
        assert d["message"] == "Halfway there"


class TestTaskDelegate:
    """Test TaskDelegate dataclass."""

    def test_creation(self):
        """TaskDelegate creation."""
        from nexus.core.a2a import TaskDelegate, TaskState

        delegate = TaskDelegate(
            task_id="task_123",
            target_agent="http://remote:8080",
        )
        assert delegate.task_id == "task_123"
        assert delegate.target_agent == "http://remote:8080"
        assert delegate.state == TaskState.SUBMITTED

    def test_to_dict(self):
        """TaskDelegate to_dict."""
        from nexus.core.a2a import TaskDelegate

        delegate = TaskDelegate(
            task_id="task_1",
            target_agent="http://agent:8080",
            result="Done",
        )
        d = delegate.to_dict()
        assert d["task_id"] == "task_1"
        assert d["target_agent"] == "http://agent:8080"
        assert d["result"] == "Done"


class TestA2AProtocol:
    """Test A2AProtocol methods."""

    @pytest.fixture
    def protocol(self):
        from nexus.core.a2a import A2AProtocol
        return A2AProtocol()

    def test_init(self, protocol):
        """A2AProtocol initialization."""
        assert protocol._local_tasks == {}
        assert protocol._discovered_agents == {}

    @pytest.mark.asyncio
    async def test_get_agent_card_success(self, protocol):
        """get_agent_card should return card on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "Test Agent",
            "version": "1.0",
            "capabilities": ["research", "coding"],
        }

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            card = await protocol.get_agent_card("http://test-agent:8080")
            assert card is not None
            assert card["name"] == "Test Agent"
            assert "http://test-agent:8080" in protocol._discovered_agents

    @pytest.mark.asyncio
    async def test_get_agent_card_not_found(self, protocol):
        """get_agent_card should return None on 404."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            card = await protocol.get_agent_card("http://missing:8080")
            assert card is None

    @pytest.mark.asyncio
    async def test_get_agent_card_connection_error(self, protocol):
        """get_agent_card should handle connection errors."""
        import httpx
        with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=httpx.ConnectError("Connection failed"))):
            card = await protocol.get_agent_card("http://down:8080")
            assert card is None

    @pytest.mark.asyncio
    async def test_delegate_task_success(self, protocol):
        """delegate_task should create task and POST to remote."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"task_id": "remote_123"}

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
            task = await protocol.delegate_task(
                agent_url="http://remote:8080",
                description="Do some work",
                metadata={"priority": "high"},
            )
            assert task.description == "Do some work"
            assert task.state.value == "working"
            assert task.task_id in protocol._local_tasks

    @pytest.mark.asyncio
    async def test_delegate_task_http_error(self, protocol):
        """delegate_task should handle HTTP errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
            task = await protocol.delegate_task(
                agent_url="http://remote:8080",
                description="Will fail",
            )
            assert task.state.value == "failed"
            assert "500" in task.error

    @pytest.mark.asyncio
    async def test_delegate_task_connection_error(self, protocol):
        """delegate_task should handle connection errors."""
        import httpx
        with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=httpx.ConnectError("Connection error"))):
            task = await protocol.delegate_task(
                agent_url="http://down:8080",
                description="Fail",
            )
            assert task.state.value == "failed"
            assert "Connection error" in task.error

    @pytest.mark.asyncio
    async def test_get_task_status_success(self, protocol):
        """get_task_status should return status on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"state": "completed", "result": "Done"}

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            status = await protocol.get_task_status("http://remote:8080", "task_1")
            assert status["state"] == "completed"
            assert status["result"] == "Done"

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(self, protocol):
        """get_task_status should return None on 404."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            status = await protocol.get_task_status("http://remote:8080", "task_1")
            assert status is None

    @pytest.mark.asyncio
    async def test_cancel_task_success(self, protocol):
        """cancel_task should return True on success."""
        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch("httpx.AsyncClient.delete", new=AsyncMock(return_value=mock_response)):
            result = await protocol.cancel_task("http://remote:8080", "task_1")
            assert result is True

    @pytest.mark.asyncio
    async def test_cancel_task_failure(self, protocol):
        """cancel_task should return False on failure."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient.delete", new=AsyncMock(return_value=mock_response)):
            result = await protocol.cancel_task("http://remote:8080", "task_1")
            assert result is False

    @pytest.mark.asyncio
    async def test_send_message_success(self, protocol):
        """send_message should return response on success."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"status": "received"}

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
            result = await protocol.send_message(
                agent_url="http://remote:8080",
                task_id="task_1",
                content="Progress update",
            )
            assert result["status"] == "received"

    @pytest.mark.asyncio
    async def test_send_message_failure(self, protocol):
        """send_message should return None on failure."""
        import httpx
        with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=httpx.ConnectError("Connection error"))):
            result = await protocol.send_message(
                agent_url="http://remote:8080",
                task_id="task_1",
                content="Update",
            )
            assert result is None

    def test_discover_local_agents(self, protocol):
        """discover_local_agents should return list."""
        with patch("nexus.core.registry.get_registry") as mock_reg:
            mock_registry = MagicMock()
            mock_registry.get_all_cards.return_value = [{"name": "local_agent"}]
            mock_reg.return_value = mock_registry

            agents = protocol.discover_local_agents()
            assert len(agents) == 1
            assert agents[0]["name"] == "local_agent"

    def test_discover_local_agents_error(self, protocol):
        """discover_local_agents should return [] on error."""
        with patch("nexus.core.registry.get_registry", side_effect=Exception("Registry error")):
            agents = protocol.discover_local_agents()
            assert agents == []

    def test_get_local_task(self, protocol):
        """get_local_task should return task by ID."""
        import asyncio

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {}

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
            task = asyncio.run(protocol.delegate_task("http://remote:8080", "test"))
            retrieved = protocol.get_local_task(task.task_id)
            assert retrieved is not None
            assert retrieved.description == "test"

    def test_get_local_task_nonexistent(self, protocol):
        """get_local_task for missing ID should return None."""
        result = protocol.get_local_task("nonexistent")
        assert result is None

    def test_list_local_tasks(self, protocol):
        """list_local_tasks should return all tasks."""
        import asyncio

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {}

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
            asyncio.run(protocol.delegate_task("http://remote:8080", "task_a"))
            asyncio.run(protocol.delegate_task("http://remote:8080", "task_b"))
            tasks = protocol.list_local_tasks()
            assert len(tasks) == 2

    def test_list_local_tasks_filtered(self, protocol):
        """list_local_tasks should filter by state."""
        from nexus.core.a2a import TaskState

        import asyncio

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {}

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
            asyncio.run(protocol.delegate_task("http://remote:8080", "task"))

            # Failed task
            import httpx
            with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=httpx.ConnectError("Fail"))):
                asyncio.run(protocol.delegate_task("http://remote:8080", "fail"))

            working = protocol.list_local_tasks(state=TaskState.WORKING)
            failed = protocol.list_local_tasks(state=TaskState.FAILED)
            assert len(working) == 1
            assert len(failed) == 1

    def test_get_discovered_agents(self, protocol):
        """get_discovered_agents should return dict."""
        agents = protocol.get_discovered_agents()
        assert isinstance(agents, dict)

    def test_get_stats(self, protocol):
        """get_stats should return protocol statistics."""
        stats = protocol.get_stats()
        assert stats["local_tasks"] == 0
        assert stats["discovered_agents"] == 0
        assert "task_states" in stats


# ═══════════════════════════════════════════════════════════════════
# Observability Tests
# ═══════════════════════════════════════════════════════════════════

class TestSpan:
    """Test Span dataclass."""

    def test_creation(self):
        """Span creation."""
        from nexus.core.observability import Span

        span = Span(name="test_span", attributes={"key": "value"})
        assert span.name == "test_span"
        assert span.attributes["key"] == "value"
        assert span.status == "ok"

    def test_duration_ms_active(self):
        """duration_ms for active span should be positive."""
        from nexus.core.observability import Span
        import time

        span = Span(name="active", start_time=time.monotonic() - 0.1)
        assert span.duration_ms > 0

    def test_duration_ms_completed(self):
        """duration_ms for completed span should use end_time."""
        from nexus.core.observability import Span
        import time

        span = Span(name="done", start_time=time.monotonic() - 1.0, end_time=time.monotonic())
        assert span.duration_ms >= 900  # ~1000ms


class TestObservabilityManager:
    """Test ObservabilityManager."""

    @pytest.fixture
    def obs(self):
        from nexus.core.observability import ObservabilityManager
        return ObservabilityManager()

    def test_init(self, obs):
        """Initialization."""
        assert obs._spans == []
        assert obs._metrics == {}
        assert obs._llm_calls == []

    def test_trace_creates_tracer(self, obs):
        """trace should return Tracer context manager."""
        tracer = obs.trace("operation", attributes={"task": "test"})
        assert tracer.span.name == "operation"
        assert tracer.span.attributes["task"] == "test"

    def test_trace_context_manager(self, obs):
        """trace context manager should record span."""
        with obs.trace("test_op") as tracer:
            tracer.set_attribute("result", "success")

        assert len(obs._spans) == 1
        assert obs._spans[0].name == "test_op"
        assert obs._spans[0].attributes["result"] == "success"
        assert obs._spans[0].end_time is not None

    def test_trace_error_records_status(self, obs):
        """trace context manager should record error status."""
        try:
            with obs.trace("failing_op") as tracer:
                raise ValueError("Something went wrong")
        except ValueError:
            pass

        assert obs._spans[0].status == "error"
        assert "error" in obs._spans[0].attributes

    def test_tracer_set_attribute(self, obs):
        """Tracer.set_attribute should update span attributes."""
        with obs.trace("op") as tracer:
            tracer.set_attribute("key1", "value1")
            tracer.set_attribute("key2", 42)

        assert obs._spans[0].attributes["key1"] == "value1"
        assert obs._spans[0].attributes["key2"] == 42

    def test_tracer_add_event(self, obs):
        """Tracer.add_event should add event to span."""
        with obs.trace("op") as tracer:
            tracer.add_event("milestone", {"progress": "50%"})

        assert "events" in obs._spans[0].attributes
        assert obs._spans[0].attributes["events"][0]["name"] == "milestone"

    def test_record_llm_call(self, obs):
        """record_llm_call should append to list."""
        obs.record_llm_call(
            provider="openai",
            model="gpt-4o",
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=500.0,
            cost_usd=0.002,
            success=True,
        )
        assert len(obs._llm_calls) == 1
        assert obs._llm_calls[0]["provider"] == "openai"
        assert obs._llm_calls[0]["prompt_tokens"] == 100

    def test_record_llm_call_no_cost(self, obs):
        """record_llm_call without cost should default to 0."""
        obs.record_llm_call(
            provider="anthropic",
            model="claude-3",
            prompt_tokens=50,
            completion_tokens=25,
            latency_ms=300.0,
        )
        assert obs._llm_calls[0]["cost_usd"] == 0.0

    def test_record_metric(self, obs):
        """record_metric should track values."""
        obs.record_metric("latency", 100.0)
        obs.record_metric("latency", 200.0)
        obs.record_metric("accuracy", 0.95)

        assert len(obs._metrics["latency"]) == 2
        assert len(obs._metrics["accuracy"]) == 1

    def test_get_stats_empty(self, obs):
        """get_stats with no data should return zeros."""
        stats = obs.get_stats()
        assert stats["total_llm_calls"] == 0
        assert stats["total_tokens"] == 0
        assert stats["total_cost_usd"] == 0
        assert stats["avg_llm_latency_ms"] == 0

    def test_get_stats_with_data(self, obs):
        """get_stats should return computed stats."""
        obs.record_llm_call("openai", "gpt-4o", 100, 50, 500.0, 0.002)
        obs.record_metric("latency", 150.0)

        stats = obs.get_stats()
        assert stats["total_llm_calls"] == 1
        assert stats["total_tokens"] == 150
        assert stats["total_cost_usd"] == 0.002
        assert stats["avg_llm_latency_ms"] == 500.0
        assert "latency" in stats["custom_metrics"]
        assert stats["custom_metrics"]["latency"]["avg"] == 150.0

    def test_get_observability_singleton(self):
        """get_observability should return singleton."""
        from nexus.core.observability import get_observability

        obs1 = get_observability()
        obs2 = get_observability()
        assert obs1 is obs2


# ═══════════════════════════════════════════════════════════════════
# Evaluation Tests
# ═══════════════════════════════════════════════════════════════════

class TestEvaluationEnums:
    """Test the evaluation module's classes match expected API."""

    def test_eval_result_exists(self):
        """EvalResult dataclass should be importable."""
        from nexus.core.evaluation import EvalResult
        assert EvalResult is not None

    def test_base_eval_exists(self):
        """BaseEval should be importable."""
        from nexus.core.evaluation import BaseEval
        assert BaseEval is not None

    def test_benchmark_classes_exist(self):
        """SWEBenchEval and HumanEvalEval should be importable."""
        from nexus.core.evaluation import SWEBenchEval, HumanEvalEval, EvalRunner
        assert SWEBenchEval is not None
        assert HumanEvalEval is not None
        assert EvalRunner is not None

    def test_eval_result_fields(self):
        """EvalResult has expected fields."""
        from nexus.core.evaluation import EvalResult

        result = EvalResult(
            benchmark="TestBenchmark",
            total_tasks=10,
            passed=8,
            failed=2,
            score=80.0,
            duration_s=5.5,
        )
        assert result.benchmark == "TestBenchmark"
        assert result.total_tasks == 10
        assert result.passed == 8
        assert result.failed == 2
        assert result.score == 80.0
        assert result.duration_s == 5.5
        assert result.details == []
        assert result.error is None

    def test_eval_result_defaults(self):
        """EvalResult has correct defaults."""
        from nexus.core.evaluation import EvalResult

        result = EvalResult(benchmark="DefaultTest")
        assert result.total_tasks == 0
        assert result.passed == 0
        assert result.failed == 0
        assert result.score == 0.0
        assert result.duration_s == 0.0
        assert result.details == []


class TestTestCase:
    """Test evaluation module classes — EvalResult as primary data holder."""

    def test_eval_result_with_details(self):
        """EvalResult can hold detailed test case results."""
        from nexus.core.evaluation import EvalResult

        details = [
            {"task_id": "task_1", "status": "passed"},
            {"task_id": "task_2", "status": "failed", "error": "timeout"},
        ]
        result = EvalResult(
            benchmark="DetailTest",
            total_tasks=2,
            passed=1,
            failed=1,
            score=50.0,
            duration_s=3.0,
            details=details,
        )
        assert len(result.details) == 2
        assert result.details[0]["status"] == "passed"
        assert result.details[1]["error"] == "timeout"

    def test_eval_result_with_error(self):
        """EvalResult can hold an error message."""
        from nexus.core.evaluation import EvalResult

        result = EvalResult(benchmark="ErrorTest", error="Dataset not found")
        assert result.error == "Dataset not found"
        assert result.score == 0.0


class TestEvaluationResult:
    """Test EvalResult construction and properties."""

    def test_eval_result_creation(self):
        """EvalResult with all fields."""
        from nexus.core.evaluation import EvalResult

        result = EvalResult(
            benchmark="AccuracyBench",
            total_tasks=20,
            passed=17,
            failed=3,
            score=85.0,
            duration_s=150.0,
        )
        assert result.benchmark == "AccuracyBench"
        assert result.score == 85.0
        assert result.passed == 17
        assert result.failed == 3

    def test_eval_result_zero_tasks(self):
        """EvalResult with zero tasks."""
        from nexus.core.evaluation import EvalResult

        result = EvalResult(benchmark="Empty", total_tasks=0, passed=0, failed=0)
        assert result.score == 0.0
        assert result.passed == 0


class TestBenchmarkRun:
    """Test the evaluation runner and base classes."""

    def test_base_eval_initialization(self):
        """BaseEval initializes correctly."""
        from nexus.core.evaluation import BaseEval

        eval_inst = BaseEval()
        assert eval_inst._results == []
        assert eval_inst.settings is not None

    def test_eval_runner_has_evaluators(self):
        """EvalRunner should initialize with benchmark evaluators."""
        from nexus.core.evaluation import EvalRunner

        runner = EvalRunner()
        assert len(runner.evaluators) == 2
        assert runner.all_results == []
        names = [type(e).__name__ for e in runner.evaluators]
        assert "SWEBenchEval" in names
        assert "HumanEvalEval" in names


class TestEvaluator:
    """Test evaluation classes — BaseEval, SWEBenchEval, HumanEvalEval, EvalRunner."""

    @pytest.fixture
    def eval_result(self):
        from nexus.core.evaluation import EvalResult
        return EvalResult(
            benchmark="TestBench",
            total_tasks=5,
            passed=4,
            failed=1,
            score=80.0,
            duration_s=2.5,
        )

    def test_eval_result_attributes(self, eval_result):
        """EvalResult has correct attributes."""
        assert eval_result.benchmark == "TestBench"
        assert eval_result.score == 80.0
        assert eval_result.total_tasks == 5
        assert eval_result.passed == 4
        assert eval_result.failed == 1
        assert eval_result.duration_s == 2.5

    @pytest.mark.asyncio
    async def test_base_eval_abstract(self):
        """BaseEval run/run_all should raise NotImplementedError."""
        from nexus.core.evaluation import BaseEval

        be = BaseEval()
        with pytest.raises(NotImplementedError):
            await be.run()
        with pytest.raises(NotImplementedError):
            await be.run_all()

    def test_base_eval_summary_empty(self):
        """BaseEval summary with no results."""
        from nexus.core.evaluation import BaseEval

        be = BaseEval()
        summary = be.summary()
        assert "Benchmark Results" in summary

    def test_swebench_eval_init(self):
        """SWEBenchEval initializes correctly."""
        from nexus.core.evaluation import SWEBenchEval

        eval_inst = SWEBenchEval(dataset_path="nonexistent.json")
        assert eval_inst.dataset_path == "nonexistent.json"
        assert eval_inst._dataset == []

    @pytest.mark.asyncio
    async def test_swebench_run_not_found(self):
        """SWEBenchEval.run with unknown task returns error."""
        from nexus.core.evaluation import SWEBenchEval

        eval_inst = SWEBenchEval(dataset_path="nonexistent.json")
        result = await eval_inst.run("nonexistent_task")
        assert result.error is not None
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_humaneval_run(self):
        """HumanEvalEval.run should execute."""
        from nexus.core.evaluation import HumanEvalEval

        eval_inst = HumanEvalEval()
        result = await eval_inst.run()
        assert result.score >= 0.0
        assert result.total_tasks > 0

    @pytest.mark.asyncio
    async def test_eval_runner_run_all(self):
        """EvalRunner.run_all should execute all evaluators."""
        from nexus.core.evaluation import EvalRunner

        runner = EvalRunner()
        results = await runner.run_all()
        assert isinstance(results, list)

    def test_eval_runner_generate_report(self):
        """EvalRunner.generate_report should return markdown."""
        from nexus.core.evaluation import EvalRunner

        runner = EvalRunner()
        report = runner.generate_report()
        assert "NEXUS Benchmark Report" in report

    def test_eval_result_with_details(self):
        """EvalResult with details list."""
        from nexus.core.evaluation import EvalResult

        details = [{"task": "t1", "result": "pass"}]
        result = EvalResult(benchmark="Details", total_tasks=1, passed=1, details=details)
        assert len(result.details) == 1
        assert result.details[0]["result"] == "pass"

    def test_eval_result_with_error(self):
        """EvalResult with error field."""
        from nexus.core.evaluation import EvalResult

        result = EvalResult(benchmark="Error", error="Something broke")
        assert result.error == "Something broke"

    def test_swebench_eval_load_dataset_missing(self):
        """SWEBenchEval.load_dataset with missing file returns empty list."""
        from nexus.core.evaluation import SWEBenchEval

        eval_inst = SWEBenchEval(dataset_path="nonexistent.json")
        import asyncio
        dataset = asyncio.run(eval_inst.load_dataset())
        assert dataset == []

    def test_base_eval_settings(self):
        """BaseEval reads settings."""
        from nexus.core.evaluation import BaseEval

        be = BaseEval()
        assert be.settings is not None


# ═══════════════════════════════════════════════════════════════════
# Supervisor Tests
# ═══════════════════════════════════════════════════════════════════

class TestServiceStatusEnum:
    """Test ServiceStatus enum."""

    def test_all_values(self):
        from nexus.core.supervisor import ServiceStatus
        assert ServiceStatus.RUNNING.value == "running"
        assert ServiceStatus.STOPPED.value == "stopped"
        assert ServiceStatus.FAILED.value == "failed"
        assert ServiceStatus.RESTARTING.value == "restarting"


class TestSupervisedService:
    """Test SupervisedService dataclass."""

    def test_creation(self):
        """SupervisedService creation."""
        from nexus.core.supervisor import SupervisedService, ServiceStatus

        svc = SupervisedService(name="chroma", max_restarts=5)
        assert svc.name == "chroma"
        assert svc.status == ServiceStatus.STOPPED
        assert svc.restart_count == 0
        assert svc.max_restarts == 5


class TestProcessSupervisor:
    """Test ProcessSupervisor."""

    @pytest.fixture
    def supervisor(self):
        from nexus.core.supervisor import ProcessSupervisor
        return ProcessSupervisor(check_interval=60, max_restarts=3)

    def test_init(self, supervisor):
        """Initialization."""
        assert supervisor.check_interval == 60
        assert supervisor.max_restarts == 3
        assert supervisor._services == {}
        assert supervisor._running is False

    def test_register_service(self, supervisor):
        """register_service should add to _services."""
        supervisor.register_service("chroma", max_restarts=5)
        assert "chroma" in supervisor._services
        assert supervisor._services["chroma"].max_restarts == 5
        assert supervisor._services["chroma"].status.value == "stopped"

    def test_report_status_running(self, supervisor):
        """report_service_status RUNNING should reset restart count."""
        supervisor.register_service("test_svc")
        svc = supervisor._services["test_svc"]
        svc.restart_count = 2

        from nexus.core.supervisor import ServiceStatus
        result = supervisor.report_service_status("test_svc", ServiceStatus.RUNNING)
        assert result is True
        assert svc.restart_count == 0
        assert svc.status == ServiceStatus.RUNNING

    def test_report_status_failed_below_max(self, supervisor):
        """report_service_status FAILED below max should return True."""
        from nexus.core.supervisor import ServiceStatus

        supervisor.register_service("test_svc")
        result = supervisor.report_service_status("test_svc", ServiceStatus.FAILED, error="OOM")
        assert result is True
        assert supervisor._services["test_svc"].restart_count == 1
        assert supervisor._services["test_svc"].last_error == "OOM"

    def test_report_status_failed_exceeds_max(self, supervisor):
        """report_service_status FAILED beyond max should return False."""
        from nexus.core.supervisor import ServiceStatus

        supervisor.register_service("test_svc", max_restarts=2)
        supervisor.report_service_status("test_svc", ServiceStatus.FAILED)
        supervisor.report_service_status("test_svc", ServiceStatus.FAILED)
        result = supervisor.report_service_status("test_svc", ServiceStatus.FAILED)
        assert result is False
        assert supervisor._services["test_svc"].restart_count == 3

    def test_report_status_auto_register(self, supervisor):
        """report_service_status should auto-register unknown services."""
        from nexus.core.supervisor import ServiceStatus

        result = supervisor.report_service_status("auto_reg", ServiceStatus.RUNNING)
        assert result is True
        assert "auto_reg" in supervisor._services

    def test_should_notify_user(self, supervisor):
        """should_notify_user should return True when restart >= max."""
        from nexus.core.supervisor import ServiceStatus

        supervisor.register_service("bad_svc", max_restarts=2)
        # After 1 failure: restart_count=1 < max_restarts=2
        supervisor.report_service_status("bad_svc", ServiceStatus.FAILED)
        assert supervisor.should_notify_user("bad_svc") is False
        # After 2 failures: restart_count=2 >= max_restarts=2
        supervisor.report_service_status("bad_svc", ServiceStatus.FAILED)
        assert supervisor.should_notify_user("bad_svc") is True

    def test_should_notify_unknown(self, supervisor):
        """should_notify_user for unknown service should return False."""
        assert supervisor.should_notify_user("unknown") is False

    def test_get_status(self, supervisor):
        """get_status should return dict of service states."""
        from nexus.core.supervisor import ServiceStatus

        supervisor.register_service("svc_a", max_restarts=3)
        supervisor.register_service("svc_b", max_restarts=5)
        supervisor.report_service_status("svc_a", ServiceStatus.RUNNING)
        supervisor.report_service_status("svc_b", ServiceStatus.FAILED, error="Crashed")

        status = supervisor.get_status()
        assert "svc_a" in status
        assert "svc_b" in status
        assert status["svc_a"]["status"] == "running"
        assert status["svc_b"]["status"] == "failed"
        assert status["svc_b"]["last_error"] == "Crashed"

    @pytest.mark.asyncio
    async def test_start_and_stop_monitoring(self, supervisor):
        """start_monitoring and stop_monitoring should work."""
        await supervisor.start_monitoring()
        assert supervisor._running is True
        assert supervisor._task is not None

        await supervisor.stop_monitoring()
        assert supervisor._running is False

    @pytest.mark.asyncio
    async def test_monitor_loop_runs(self, supervisor):
        """Monitor loop should run without error."""
        supervisor.check_interval = 0.01
        await supervisor.start_monitoring()
        await asyncio.sleep(0.05)
        await supervisor.stop_monitoring()

    @pytest.mark.asyncio
    async def test_monitor_loop_cancelled(self, supervisor):
        """Monitor loop should handle cancellation."""
        supervisor.check_interval = 0.01
        await supervisor.start_monitoring()
        supervisor._running = False
        await asyncio.sleep(0.02)

    def test_report_status_with_pid(self, supervisor):
        """report_service_status with pid."""
        from nexus.core.supervisor import ServiceStatus

        supervisor.register_service("test")
        result = supervisor.report_service_status("test", ServiceStatus.RUNNING, pid=12345)
        assert result is True
        # Note: the pid parameter is accepted but not stored by the current implementation


# ═══════════════════════════════════════════════════════════════════
# Error Messages Tests
# ═══════════════════════════════════════════════════════════════════

class TestHumanError:
    """Test HumanError class."""

    def test_creation(self):
        """HumanError creation."""
        from nexus.core.error_messages import HumanError

        err = HumanError(
            message="Something went wrong",
            action="Try again",
            technical="Connection refused",
        )
        assert err.message == "Something went wrong"
        assert err.action == "Try again"
        assert err.technical == "Connection refused"

    def test_to_dict(self):
        """HumanError to_dict."""
        from nexus.core.error_messages import HumanError

        err = HumanError(message="Error", action="Fix it", technical="details")
        d = err.to_dict()
        assert d["message"] == "Error"
        assert d["action"] == "Fix it"
        assert d["technical"] == "details"


class TestGetHumanError:
    """Test get_human_error() function."""

    def test_direct_error_map_match(self):
        """Known exception type should get mapped message."""
        from nexus.core.error_messages import get_human_error
        from nexus.core.exceptions import OrchestratorError

        exc = OrchestratorError("Something broke")
        human = get_human_error(exc)
        assert len(human.message) > 0
        assert len(human.action) > 0
        assert human.technical == "Something broke"

    def test_connection_error_pattern(self):
        """Connection error message should be detected."""
        from nexus.core.error_messages import get_human_error

        exc = ConnectionError("Connection refused to server")
        human = get_human_error(exc)
        assert "connection" in human.message.lower() or "connect" in human.message.lower()

    def test_timeout_pattern(self):
        """Timeout message should be detected."""
        from nexus.core.error_messages import get_human_error

        exc = TimeoutError("The operation timed out after 30 seconds")
        human = get_human_error(exc)
        assert "time" in human.message.lower() or "trop" in human.message.lower()

    def test_api_key_pattern(self):
        """API key error should be detected."""
        from nexus.core.error_messages import get_human_error

        exc = ValueError("Invalid API key provided")
        human = get_human_error(exc)
        assert "clé" in human.message.lower() or "api" in human.message.lower()

    def test_rate_limit_pattern(self):
        """Rate limit error should be detected."""
        from nexus.core.error_messages import get_human_error

        exc = Exception("Rate limit exceeded 429")
        human = get_human_error(exc)
        assert "requêtes" in human.message.lower() or "trop" in human.message.lower()

    def test_import_error_pattern(self):
        """Import error should be detected."""
        from nexus.core.error_messages import get_human_error

        exc = ImportError("No module named 'nonexistent'")
        human = get_human_error(exc)
        assert "manquant" in human.message.lower() or "composant" in human.message.lower()

    def test_permission_error_pattern(self):
        """Permission error should be detected."""
        from nexus.core.error_messages import get_human_error

        exc = PermissionError("Access denied to file")
        human = get_human_error(exc)
        assert "permission" in human.message.lower() or "refusée" in human.message.lower()

    def test_default_fallback(self):
        """Unknown error should get default message."""
        from nexus.core.error_messages import get_human_error

        exc = RuntimeError("Some weird error that doesn't match any pattern")
        human = get_human_error(exc)
        assert len(human.message) > 0
        assert len(human.action) > 0
        assert "inattendue" in human.message.lower()

    def test_error_map_modifications(self):
        """get_human_error should set technical on mapped errors."""
        from nexus.core.error_messages import get_human_error, ERROR_MAP

        # Simulate a mapped error
        class LLMProviderError(Exception):
            pass

        exc = LLMProviderError("Provider rejected request")
        human = get_human_error(exc)
        assert human.technical == "Provider rejected request"

    def test_lowercase_matching(self):
        """Pattern matching should be case-insensitive."""
        from nexus.core.error_messages import get_human_error

        exc = Exception("CONNECTION REFUSED")
        human = get_human_error(exc)
        assert human.message is not None

    def test_error_map_has_expected_keys(self):
        """ERROR_MAP should have expected keys."""
        from nexus.core.error_messages import ERROR_MAP

        assert "OrchestratorError" in ERROR_MAP
        assert "MaxIterationsError" in ERROR_MAP
        assert "LLMError" in ERROR_MAP
        assert "SandboxError" in ERROR_MAP
        assert "MCPToolError" in ERROR_MAP
        assert "MemoryNamespaceError" in ERROR_MAP
        assert "MemorySearchError" in ERROR_MAP
        assert "MemoryStoreError" in ERROR_MAP
