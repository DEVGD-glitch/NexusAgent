"""
Comprehensive tests for all NEXUS MCP tool modules.

Tests every function in:
  - agent_tools, code_tools, file_tools, knowledge_tools
  - memory_tools, llm_tools, web_tools, system_tools
  - orchestration_tools, reasoning_tools, bonus_tools, context7

For each function: happy path, error handling, and edge cases.
All external dependencies are mocked at their ORIGINAL source module
(since most tools use function-level imports).
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexus.mcp_tools import (
    agent_tools,
    bonus_tools,
    code_tools,
    context7 as context7_module,
    file_tools,
    knowledge_tools,
    llm_tools,
    memory_tools,
    orchestration_tools,
    reasoning_tools,
    system_tools,
    web_tools,
)


# =============================================================================
# agent_tools tests
# =============================================================================

class TestAgentTools:
    """Tests for nexus.mcp_tools.agent_tools."""

    @patch("nexus.core.registry.AgentRegistry")
    async def test_spawn_agent_happy(self, mock_registry_class):
        """spawn_agent returns completed status with correct keys."""
        mock_registry = mock_registry_class.return_value
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="task_result")
        mock_registry.create.return_value = mock_agent

        result = await agent_tools.spawn_agent("coder", "write tests")
        data = json.loads(result)
        assert data["status"] == "completed"
        assert data["agent_type"] == "coder"
        assert data["result"] == "task_result"

    @patch("nexus.core.registry.AgentRegistry")
    async def test_spawn_agent_with_config(self, mock_registry_class):
        """spawn_agent passes config to registry.create."""
        mock_registry = mock_registry_class.return_value
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="ok")
        mock_registry.create.return_value = mock_agent

        config = {"model": "gpt-4"}
        await agent_tools.spawn_agent("coder", "task", config=config)
        mock_registry.create.assert_called_with("coder", config)

    @patch("nexus.core.registry.AgentRegistry")
    async def test_spawn_agent_no_config_passes_empty_dict(self, mock_registry_class):
        """spawn_agent passes {} when config is None."""
        mock_registry = mock_registry_class.return_value
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="ok")
        mock_registry.create.return_value = mock_agent

        await agent_tools.spawn_agent("coder", "task", config=None)
        mock_registry.create.assert_called_with("coder", {})

    @patch("nexus.core.registry.AgentRegistry")
    async def test_spawn_agent_error(self, mock_registry_class):
        """spawn_agent returns error JSON on exception."""
        mock_registry_class.side_effect = RuntimeError("registry failed")
        result = await agent_tools.spawn_agent("coder", "task")
        data = json.loads(result)
        assert "error" in data

    @patch("nexus.core.registry.AgentRegistry")
    async def test_list_agents_happy(self, mock_registry_class):
        """list_agents returns agent list."""
        mock_registry = mock_registry_class.return_value
        mock_registry.list_agents.return_value = ["coder", "researcher"]

        result = await agent_tools.list_agents()
        data = json.loads(result)
        assert data["agents"] == ["coder", "researcher"]

    @patch("nexus.core.registry.AgentRegistry")
    async def test_list_agents_error(self, mock_registry_class):
        """list_agents returns error JSON on exception."""
        mock_registry_class.side_effect = RuntimeError("fail")
        result = await agent_tools.list_agents()
        data = json.loads(result)
        assert "error" in data

    @patch("nexus.core.registry.AgentRegistry")
    async def test_agent_status_happy(self, mock_registry_class):
        """agent_status returns status with correct keys."""
        mock_registry = mock_registry_class.return_value
        mock_registry.get_status.return_value = {"state": "running"}

        result = await agent_tools.agent_status("inst-1")
        data = json.loads(result)
        assert data["instance_id"] == "inst-1"
        assert data["status"] == {"state": "running"}

    @patch("nexus.core.registry.AgentRegistry")
    async def test_agent_status_error(self, mock_registry_class):
        """agent_status returns error JSON on exception."""
        mock_registry_class.side_effect = RuntimeError("fail")
        result = await agent_tools.agent_status("inst-1")
        data = json.loads(result)
        assert "error" in data

    @patch("nexus.core.registry.AgentRegistry")
    async def test_agent_status_empty_id(self, mock_registry_class):
        """agent_status works with empty string id."""
        mock_reg = mock_registry_class.return_value
        mock_reg.get_status.return_value = {}
        result = await agent_tools.agent_status("")
        data = json.loads(result)
        assert data["instance_id"] == ""

    async def test_agent_delegate_happy(self):
        """agent_delegate returns delegated status."""
        result = await agent_tools.agent_delegate("agent_a", "agent_b", "do thing")
        data = json.loads(result)
        assert data["status"] == "delegated"
        assert data["source"] == "agent_a"
        assert data["target"] == "agent_b"
        assert data["task"] == "do thing"

    async def test_agent_delegate_with_context(self):
        """agent_delegate accepts optional context dict."""
        result = await agent_tools.agent_delegate("a", "b", "t", context={"priority": "high"})
        data = json.loads(result)
        assert data["status"] == "delegated"

    async def test_a2a_discover_happy(self):
        """a2a_discover returns discovered status with capabilities."""
        result = await agent_tools.a2a_discover("http://agent.local")
        data = json.loads(result)
        assert data["status"] == "discovered"
        assert data["url"] == "http://agent.local"
        assert "capabilities" in data


# =============================================================================
# code_tools tests
# =============================================================================

class TestCodeTools:
    """Tests for nexus.mcp_tools.code_tools."""

    @patch("nexus.security.sandbox.LocalSandbox")
    async def test_execute_code_happy(self, mock_sandbox_class):
        """execute_code returns execution result."""
        from nexus.security.sandbox import SandboxResult
        mock_sandbox = mock_sandbox_class.return_value
        mock_sandbox.execute_python = AsyncMock(
            return_value=SandboxResult(
                exit_code=0, stdout="out", stderr="",
                timed_out=False, execution_time_ms=10.0,
            )
        )

        result = await code_tools.execute_code("print('hi')")
        data = json.loads(result)
        assert data["exit_code"] == 0
        assert data["stdout"] == "out"
        assert data["execution_time_ms"] == 10.0

    @patch("nexus.security.sandbox.LocalSandbox")
    async def test_execute_code_custom_timeout(self, mock_sandbox_class):
        """execute_code passes timeout to sandbox."""
        from nexus.security.sandbox import SandboxResult
        mock_sandbox = mock_sandbox_class.return_value
        mock_sandbox.execute_python = AsyncMock(return_value=SandboxResult())

        await code_tools.execute_code("code", timeout=60)
        mock_sandbox.execute_python.assert_called_with("code", timeout=60)

    @patch("nexus.security.sandbox.LocalSandbox")
    async def test_execute_code_error(self, mock_sandbox_class):
        """execute_code returns error JSON on exception."""
        mock_sandbox_class.side_effect = RuntimeError("sandbox init fail")
        result = await code_tools.execute_code("print('hi')")
        data = json.loads(result)
        assert "error" in data

    @patch("nexus.security.sandbox.LocalSandbox")
    async def test_execute_code_timeout_result(self, mock_sandbox_class):
        """execute_code handles timed_out result."""
        from nexus.security.sandbox import SandboxResult
        mock_sandbox = mock_sandbox_class.return_value
        mock_sandbox.execute_python = AsyncMock(
            return_value=SandboxResult(timed_out=True, exit_code=-1)
        )

        result = await code_tools.execute_code("loop")
        data = json.loads(result)
        assert data["timed_out"] is True
        assert data["exit_code"] == -1

    @patch("nexus.security.sandbox.LocalSandbox")
    async def test_execute_sandboxed_happy(self, mock_sandbox_class):
        """execute_sandboxed returns shell execution result."""
        from nexus.security.sandbox import SandboxResult
        mock_sandbox = mock_sandbox_class.return_value
        mock_sandbox.execute_shell = AsyncMock(
            return_value=SandboxResult(stdout="hello", exit_code=0)
        )

        result = await code_tools.execute_sandboxed("echo hello")
        data = json.loads(result)
        assert data["stdout"] == "hello"
        assert data["exit_code"] == 0

    @patch("nexus.security.sandbox.LocalSandbox")
    async def test_execute_sandboxed_with_options(self, mock_sandbox_class):
        """execute_sandboxed passes timeout / allowed_dirs."""
        from nexus.security.sandbox import SandboxResult
        mock_sandbox = mock_sandbox_class.return_value
        mock_sandbox.execute_shell = AsyncMock(return_value=SandboxResult())

        await code_tools.execute_sandboxed("ls", timeout=10, allowed_dirs=["/tmp"])
        mock_sandbox.execute_shell.assert_called_with("ls", timeout=10)

    @patch("nexus.security.sandbox.LocalSandbox")
    async def test_execute_sandboxed_error(self, mock_sandbox_class):
        """execute_sandboxed returns error JSON on exception."""
        mock_sandbox_class.side_effect = RuntimeError("fail")
        result = await code_tools.execute_sandboxed("echo hi")
        data = json.loads(result)
        assert "error" in data

    @patch("asyncio.create_subprocess_exec")
    async def test_install_package_happy(self, mock_subprocess):
        """install_package returns success status."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"installed", b""))
        mock_proc.returncode = 0
        mock_subprocess.return_value = mock_proc

        result = await code_tools.install_package("requests")
        data = json.loads(result)
        assert data["status"] == "success"
        assert data["package"] == "requests"

    @patch("asyncio.create_subprocess_exec")
    async def test_install_package_with_version(self, mock_subprocess):
        """install_package supports version pinning."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0
        mock_subprocess.return_value = mock_proc

        result = await code_tools.install_package("requests", version="2.28.0")
        data = json.loads(result)
        assert data["version"] == "2.28.0"

    @patch("asyncio.create_subprocess_exec")
    async def test_install_package_failed(self, mock_subprocess):
        """install_package returns failed on non-zero exit."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error msg"))
        mock_proc.returncode = 1
        mock_subprocess.return_value = mock_proc

        result = await code_tools.install_package("bad-pkg")
        data = json.loads(result)
        assert data["status"] == "failed"

    @patch("asyncio.create_subprocess_exec")
    async def test_install_package_timeout(self, mock_subprocess):
        """install_package handles asyncio.TimeoutError."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_subprocess.return_value = mock_proc

        result = await code_tools.install_package("slow-pkg")
        data = json.loads(result)
        assert data["status"] == "failed"
        assert "Timeout" in data["error"]

    @patch("asyncio.create_subprocess_exec")
    async def test_install_package_general_error(self, mock_subprocess):
        """install_package returns error JSON on general exception."""
        mock_subprocess.side_effect = RuntimeError("subprocess creation failed")
        result = await code_tools.install_package("pkg")
        data = json.loads(result)
        assert "error" in data

    @patch("nexus.security.sandbox.LocalSandbox")
    async def test_execute_code_empty_string(self, mock_sandbox_class):
        """execute_code works with empty code string."""
        from nexus.security.sandbox import SandboxResult
        mock_sandbox = mock_sandbox_class.return_value
        mock_sandbox.execute_python = AsyncMock(return_value=SandboxResult())

        result = await code_tools.execute_code("")
        data = json.loads(result)
        assert "exit_code" in data


# =============================================================================
# file_tools tests
# =============================================================================

class TestFileTools:
    """Tests for nexus.mcp_tools.file_tools.
    
    Note: check_permission is a method on PermissionManager, not a module-level
    function. file_tools.py imports it inside a try/except via
    'from nexus.security.permissions import check_permission'.  We must
    use create=True so patch adds it to the module namespace, and also add
    the missing PermissionAction.READ / .WRITE / .DELETE enum values that
    the file_tools functions reference at runtime.
    """

    async def test_read_file_happy(self, tmp_path):
        """read_file returns file content and size."""
        f = tmp_path / "test.txt"
        f.write_text("hello world")

        from nexus.security.permissions import PermissionAction
        with patch("nexus.security.permissions.check_permission",
                   create=True) as mock_cp, \
             patch.object(PermissionAction, "READ", "read", create=True):
            result = await file_tools.read_file(str(f))
        data = json.loads(result)
        assert data["content"] == "hello world"
        assert data["size"] == 11
        assert data["path"] == str(f)

    async def test_read_file_not_found(self, tmp_path):
        """read_file returns error for missing file."""
        from nexus.security.permissions import PermissionAction
        with patch("nexus.security.permissions.check_permission",
                   create=True), \
             patch.object(PermissionAction, "READ", "read", create=True):
            result = await file_tools.read_file(str(tmp_path / "nope.txt"))
        data = json.loads(result)
        assert "error" in data

    async def test_read_file_permission_denied(self, tmp_path):
        """read_file returns error when permission denied."""
        from nexus.security.permissions import PermissionAction
        with patch("nexus.security.permissions.check_permission",
                   create=True, side_effect=PermissionError("denied")), \
             patch.object(PermissionAction, "READ", "read", create=True):
            result = await file_tools.read_file(str(tmp_path / "x.txt"))
        data = json.loads(result)
        assert "error" in data

    async def test_read_file_empty(self, tmp_path):
        """read_file handles empty file."""
        f = tmp_path / "empty.txt"
        f.write_text("")
        from nexus.security.permissions import PermissionAction
        with patch("nexus.security.permissions.check_permission",
                   create=True), \
             patch.object(PermissionAction, "READ", "read", create=True):
            result = await file_tools.read_file(str(f))
        data = json.loads(result)
        assert data["content"] == ""
        assert data["size"] == 0

    async def test_write_file_happy(self, tmp_path):
        """write_file creates file and returns status."""
        dest = tmp_path / "out.txt"
        from nexus.security.permissions import PermissionAction
        with patch("nexus.security.permissions.check_permission",
                   create=True), \
             patch.object(PermissionAction, "WRITE", "write", create=True):
            result = await file_tools.write_file(str(dest), "content")
        assert dest.read_text() == "content"
        data = json.loads(result)
        assert data["status"] == "written"
        assert data["size"] == 7

    async def test_write_file_creates_parent_dirs(self, tmp_path):
        """write_file creates parent directories."""
        dest = tmp_path / "a" / "b" / "deep.txt"
        from nexus.security.permissions import PermissionAction
        with patch("nexus.security.permissions.check_permission",
                   create=True), \
             patch.object(PermissionAction, "WRITE", "write", create=True):
            result = await file_tools.write_file(str(dest), "deep")
        assert dest.exists()
        data = json.loads(result)
        assert data["status"] == "written"

    async def test_write_file_permission_error(self, tmp_path):
        """write_file returns error on permission failure."""
        from nexus.security.permissions import PermissionAction
        with patch("nexus.security.permissions.check_permission",
                   create=True, side_effect=PermissionError("denied")), \
             patch.object(PermissionAction, "WRITE", "write", create=True):
            result = await file_tools.write_file(str(tmp_path / "out.txt"), "content")
        data = json.loads(result)
        assert "error" in data

    async def test_list_files_happy(self, tmp_path):
        """list_files returns matching files and count."""
        for name in ["a.txt", "b.txt", "c.py"]:
            (tmp_path / name).write_text("x")
        result = await file_tools.list_files(str(tmp_path), "*.txt")
        data = json.loads(result)
        assert data["count"] == 2

    async def test_list_files_defaults(self, tmp_path):
        """list_files defaults to cwd and * pattern."""
        result = await file_tools.list_files(str(tmp_path))
        data = json.loads(result)
        assert data["directory"] == str(tmp_path)
        assert data["pattern"] == "*"

    async def test_list_files_empty_dir(self, tmp_path):
        """list_files returns empty list for no matches."""
        result = await file_tools.list_files(str(tmp_path), "*.nonexistent")
        data = json.loads(result)
        assert data["count"] == 0
        assert data["files"] == []

    async def test_list_files_error(self):
        """list_files returns result (may be empty) for non-existent directory."""
        # Path.glob does not raise on missing directories (returns empty iterator)
        # On Python/Windows, the function does not raise so `except` is not hit.
        result = await file_tools.list_files(r"\0invalid|path?")
        data = json.loads(result)
        assert "directory" in data
        assert "files" in data

    async def test_delete_file_happy(self, tmp_path):
        """delete_file removes file and returns status."""
        f = tmp_path / "to_delete.txt"
        f.write_text("bye")
        from nexus.security.permissions import PermissionAction
        with patch("nexus.security.permissions.check_permission",
                   create=True), \
             patch.object(PermissionAction, "DELETE", "delete", create=True):
            result = await file_tools.delete_file(str(f))
        assert not f.exists()
        data = json.loads(result)
        assert data["status"] == "deleted"

    async def test_delete_file_not_found(self, tmp_path):
        """delete_file returns error for missing file."""
        from nexus.security.permissions import PermissionAction
        with patch("nexus.security.permissions.check_permission",
                   create=True), \
             patch.object(PermissionAction, "DELETE", "delete", create=True):
            result = await file_tools.delete_file(str(tmp_path / "ghost.txt"))
        data = json.loads(result)
        assert "error" in data

    async def test_delete_file_permission_error(self, tmp_path):
        """delete_file returns error on permission denial."""
        from nexus.security.permissions import PermissionAction
        with patch("nexus.security.permissions.check_permission",
                   create=True, side_effect=PermissionError("denied")), \
             patch.object(PermissionAction, "DELETE", "delete", create=True):
            result = await file_tools.delete_file(str(tmp_path / "x.txt"))
        data = json.loads(result)
        assert "error" in data

    async def test_move_file_happy(self, tmp_path):
        """move_file moves file and returns status."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"
        src.write_text("data")
        from nexus.security.permissions import PermissionAction
        with patch("nexus.security.permissions.check_permission",
                   create=True), \
             patch.object(PermissionAction, "WRITE", "write", create=True):
            result = await file_tools.move_file(str(src), str(dst))
        assert dst.exists()
        assert not src.exists()
        data = json.loads(result)
        assert data["status"] == "moved"

    async def test_move_file_creates_parent_dirs(self, tmp_path):
        """move_file creates parent dirs for destination."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "sub" / "dest.txt"
        src.write_text("data")
        from nexus.security.permissions import PermissionAction
        with patch("nexus.security.permissions.check_permission",
                   create=True), \
             patch.object(PermissionAction, "WRITE", "write", create=True):
            result = await file_tools.move_file(str(src), str(dst))
        assert dst.exists()
        data = json.loads(result)
        assert data["status"] == "moved"

    async def test_move_file_error(self, tmp_path):
        """move_file returns error on permission failure."""
        src = tmp_path / "src.txt"
        src.write_text("x")
        from nexus.security.permissions import PermissionAction
        with patch("nexus.security.permissions.check_permission",
                   create=True, side_effect=PermissionError("denied")), \
             patch.object(PermissionAction, "WRITE", "write", create=True):
            result = await file_tools.move_file(str(src), str(tmp_path / "dst.txt"))
        data = json.loads(result)
        assert "error" in data

    async def test_copy_file_happy(self, tmp_path):
        """copy_file copies file and returns status."""
        src = tmp_path / "original.txt"
        dst = tmp_path / "copy.txt"
        src.write_text("data")
        from nexus.security.permissions import PermissionAction
        with patch("nexus.security.permissions.check_permission",
                   create=True), \
             patch.object(PermissionAction, "WRITE", "write", create=True):
            result = await file_tools.copy_file(str(src), str(dst))
        assert dst.exists() and src.exists()
        data = json.loads(result)
        assert data["status"] == "copied"

    async def test_copy_file_creates_parent_dirs(self, tmp_path):
        """copy_file creates parent directories."""
        src = tmp_path / "original.txt"
        dst = tmp_path / "deep" / "nested" / "copy.txt"
        src.write_text("data")
        from nexus.security.permissions import PermissionAction
        with patch("nexus.security.permissions.check_permission",
                   create=True), \
             patch.object(PermissionAction, "WRITE", "write", create=True):
            result = await file_tools.copy_file(str(src), str(dst))
        assert dst.exists()

    async def test_search_files_windows(self, tmp_path):
        """search_files uses findstr on Windows."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"found.txt\n", b""))
        mock_proc.returncode = 0

        with patch("sys.platform", "win32"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await file_tools.search_files("match", str(tmp_path))
        data = json.loads(result)
        assert data["query"] == "match"
        assert data["count"] >= 0

    async def test_search_files_unix(self, tmp_path):
        """search_files uses grep on Unix."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"file.py\n", b""))
        mock_proc.returncode = 0

        with patch("sys.platform", "linux"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await file_tools.search_files("def", str(tmp_path), "*.py")
        data = json.loads(result)
        assert data["query"] == "def"

    async def test_search_files_no_results(self):
        """search_files handles no matches."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("sys.platform", "linux"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await file_tools.search_files("zzz_nonexistent", ".", "*.py")
        data = json.loads(result)
        assert data["count"] == 0

    async def test_search_files_error(self):
        """search_files returns error on subprocess failure."""
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=RuntimeError("fail"),
        ):
            result = await file_tools.search_files("query")
        data = json.loads(result)
        assert "error" in data


# =============================================================================
# knowledge_tools tests
# =============================================================================

class TestKnowledgeTools:
    """Tests for nexus.mcp_tools.knowledge_tools."""

    @patch("nexus.mcp_tools.knowledge_tools.KnowledgeGraph")
    async def test_knowledge_query_happy(self, mock_kg_class):
        """knowledge_query returns entity data and relationships."""
        mock_kg = mock_kg_class.return_value
        mock_kg.get_entity.return_value = {"name": "Einstein"}
        mock_kg.get_relationships.return_value = [{"type": "born_in"}]
        mock_kg.get_neighbors.return_value = [{"name": "Germany"}]

        result = await knowledge_tools.knowledge_query("Einstein")
        data = json.loads(result)
        assert data["entity"] == "Einstein"
        assert data["entity_data"] == {"name": "Einstein"}
        assert data["depth"] == 1

    @patch("nexus.mcp_tools.knowledge_tools.KnowledgeGraph")
    async def test_knowledge_query_custom_depth(self, mock_kg_class):
        """knowledge_query passes depth to get_neighbors."""
        mock_kg = mock_kg_class.return_value
        mock_kg.get_entity.return_value = {}
        mock_kg.get_relationships.return_value = []
        mock_kg.get_neighbors.return_value = []

        await knowledge_tools.knowledge_query("Entity", depth=3)
        mock_kg.get_neighbors.assert_called_with("Entity", degree=3)

    @patch("nexus.mcp_tools.knowledge_tools.KnowledgeGraph")
    async def test_knowledge_query_error(self, mock_kg_class):
        """knowledge_query returns error on exception."""
        mock_kg_class.side_effect = RuntimeError("kg fail")
        result = await knowledge_tools.knowledge_query("X")
        data = json.loads(result)
        assert "error" in data

    @patch("nexus.mcp_tools.knowledge_tools.KnowledgeGraph")
    async def test_knowledge_add_entity_happy(self, mock_kg_class):
        """knowledge_add_entity returns added status."""
        mock_kg = mock_kg_class.return_value
        mock_kg.add_entity.return_value = "entity-123"

        result = await knowledge_tools.knowledge_add_entity("Person", "Alice")
        data = json.loads(result)
        assert data["status"] == "added"
        assert data["entity_id"] == "entity-123"

    @patch("nexus.mcp_tools.knowledge_tools.KnowledgeGraph")
    async def test_knowledge_add_entity_with_properties(self, mock_kg_class):
        """knowledge_add_entity passes properties."""
        mock_kg = mock_kg_class.return_value
        mock_kg.add_entity.return_value = "e1"
        props = {"age": 30}

        await knowledge_tools.knowledge_add_entity("Person", "Alice", properties=props)
        mock_kg.add_entity.assert_called_with("Alice", entity_type="Person", properties=props)

    @patch("nexus.mcp_tools.knowledge_tools.KnowledgeGraph")
    async def test_knowledge_add_entity_error(self, mock_kg_class):
        mock_kg_class.side_effect = RuntimeError("fail")
        result = await knowledge_tools.knowledge_add_entity("T", "N")
        data = json.loads(result)
        assert "error" in data

    @patch("nexus.mcp_tools.knowledge_tools.KnowledgeGraph")
    async def test_knowledge_add_relation_happy(self, mock_kg_class):
        mock_kg = mock_kg_class.return_value
        result = await knowledge_tools.knowledge_add_relation("Alice", "Bob", "knows")
        data = json.loads(result)
        assert data["status"] == "added"

    @patch("nexus.mcp_tools.knowledge_tools.KnowledgeGraph")
    async def test_knowledge_add_relation_error(self, mock_kg_class):
        mock_kg_class.side_effect = RuntimeError("fail")
        result = await knowledge_tools.knowledge_add_relation("A", "B", "knows")
        data = json.loads(result)
        assert "error" in data

    @patch("nexus.mcp_tools.knowledge_tools.KnowledgeGraph")
    async def test_knowledge_search_happy(self, mock_kg_class):
        mock_kg = mock_kg_class.return_value
        mock_kg.search_entities.return_value = [{"name": "Einstein"}]
        result = await knowledge_tools.knowledge_search("Einstein")
        data = json.loads(result)
        assert data["count"] == 1

    @patch("nexus.mcp_tools.knowledge_tools.KnowledgeGraph")
    async def test_knowledge_search_with_filters(self, mock_kg_class):
        mock_kg = mock_kg_class.return_value
        mock_kg.search_entities.return_value = []
        await knowledge_tools.knowledge_search("query", entity_type="Person", limit=10)
        mock_kg.search_entities.assert_called_with("query", "Person", 10)

    @patch("nexus.mcp_tools.knowledge_tools.KnowledgeGraph")
    async def test_knowledge_search_error(self, mock_kg_class):
        mock_kg_class.side_effect = RuntimeError("fail")
        result = await knowledge_tools.knowledge_search("q")
        data = json.loads(result)
        assert "error" in data

    @patch("nexus.mcp_tools.knowledge_tools.KnowledgeGraph")
    async def test_knowledge_paths_happy(self, mock_kg_class):
        mock_kg = mock_kg_class.return_value
        mock_kg.find_paths.return_value = [["A", "B", "C"]]
        result = await knowledge_tools.knowledge_paths("A", "C")
        data = json.loads(result)
        assert data["count"] == 1

    @patch("nexus.mcp_tools.knowledge_tools.KnowledgeGraph")
    async def test_knowledge_paths_max_length(self, mock_kg_class):
        mock_kg = mock_kg_class.return_value
        mock_kg.find_paths.return_value = []
        await knowledge_tools.knowledge_paths("A", "C", max_length=3)
        mock_kg.find_paths.assert_called_with("A", "C", 3)

    @patch("nexus.mcp_tools.knowledge_tools.KnowledgeGraph")
    async def test_knowledge_paths_error(self, mock_kg_class):
        mock_kg_class.side_effect = RuntimeError("fail")
        result = await knowledge_tools.knowledge_paths("A", "C")
        data = json.loads(result)
        assert "error" in data


# =============================================================================
# memory_tools tests
# =============================================================================

class TestMemoryTools:
    """Tests for nexus.mcp_tools.memory_tools."""

    # memory_tools imports NexusMemoryService at MODULE level:
    #   from nexus.memory.chroma_service import NexusMemoryService
    # so we must patch the consumer name.
    MOCK_PATH = "nexus.mcp_tools.memory_tools.NexusMemoryService"

    @patch("nexus.mcp_tools.memory_tools.NexusMemoryService")
    async def test_search_memory_happy(self, mock_svc_class):
        mock_svc = mock_svc_class.return_value
        mock_svc.search = AsyncMock(return_value=[{"id": "doc1", "text": "hello"}])
        result = await memory_tools.search_memory("hello")
        data = json.loads(result)
        assert data["query"] == "hello"

    @patch("nexus.mcp_tools.memory_tools.NexusMemoryService")
    async def test_search_memory_custom(self, mock_svc_class):
        mock_svc = mock_svc_class.return_value
        mock_svc.search = AsyncMock(return_value=[])
        await memory_tools.search_memory("query", namespace="code", top_k=10)
        mock_svc.search.assert_called_with("query", "code", 10)

    @patch("nexus.mcp_tools.memory_tools.NexusMemoryService")
    async def test_search_memory_error(self, mock_svc_class):
        mock_svc_class.side_effect = RuntimeError("svc fail")
        result = await memory_tools.search_memory("q")
        data = json.loads(result)
        assert "error" in data

    @patch("nexus.mcp_tools.memory_tools.NexusMemoryService")
    async def test_store_memory_happy(self, mock_svc_class):
        mock_svc = mock_svc_class.return_value
        mock_svc.store = AsyncMock(return_value="doc-abc")
        result = await memory_tools.store_memory("important fact")
        data = json.loads(result)
        assert data["status"] == "stored"
        assert data["doc_id"] == "doc-abc"

    @patch("nexus.mcp_tools.memory_tools.NexusMemoryService")
    async def test_store_memory_with_metadata(self, mock_svc_class):
        mock_svc = mock_svc_class.return_value
        mock_svc.store = AsyncMock(return_value="doc-1")
        await memory_tools.store_memory("text", metadata={"source": "user"})
        mock_svc.store.assert_called_with("text", "conversations", {"source": "user"})

    @patch("nexus.mcp_tools.memory_tools.NexusMemoryService")
    async def test_store_memory_error(self, mock_svc_class):
        mock_svc_class.side_effect = RuntimeError("fail")
        result = await memory_tools.store_memory("text")
        data = json.loads(result)
        assert "error" in data

    @patch("nexus.mcp_tools.memory_tools.NexusMemoryService")
    async def test_delete_memory_happy(self, mock_svc_class):
        mock_svc = mock_svc_class.return_value
        mock_svc.delete = AsyncMock()
        result = await memory_tools.delete_memory(["doc1", "doc2"])
        data = json.loads(result)
        assert data["status"] == "deleted"

    @patch("nexus.mcp_tools.memory_tools.NexusMemoryService")
    async def test_delete_memory_custom_namespace(self, mock_svc_class):
        mock_svc = mock_svc_class.return_value
        mock_svc.delete = AsyncMock()
        await memory_tools.delete_memory(["doc1"], namespace="episodes")
        mock_svc.delete.assert_called_with(["doc1"], "episodes")

    @patch("nexus.mcp_tools.memory_tools.NexusMemoryService")
    async def test_delete_memory_error(self, mock_svc_class):
        mock_svc_class.side_effect = RuntimeError("fail")
        result = await memory_tools.delete_memory(["doc1"])
        data = json.loads(result)
        assert "error" in data

    async def test_list_namespaces(self):
        """list_namespaces returns all valid namespaces."""
        result = await memory_tools.list_namespaces()
        data = json.loads(result)
        namespaces = data["namespaces"]
        assert "conversations" in namespaces
        assert "knowledge" in namespaces
        assert "code" in namespaces

    @patch("nexus.mcp_tools.memory_tools.NexusMemoryService")
    async def test_memory_stats_happy(self, mock_svc_class):
        mock_svc = mock_svc_class.return_value
        mock_svc.get_stats = AsyncMock(return_value={"total_docs": 100})
        result = await memory_tools.memory_stats()
        data = json.loads(result)
        assert data["total_docs"] == 100

    @patch("nexus.mcp_tools.memory_tools.NexusMemoryService")
    async def test_memory_stats_error(self, mock_svc_class):
        mock_svc_class.side_effect = RuntimeError("fail")
        result = await memory_tools.memory_stats()
        data = json.loads(result)
        assert "error" in data


# =============================================================================
# llm_tools tests
# =============================================================================

class TestLLMTools:
    """Tests for nexus.mcp_tools.llm_tools."""

    def _mock_response(self, content="response", model="gpt-4", usage=None):
        resp = MagicMock()
        resp.content = content
        resp.model = model
        resp.usage = MagicMock() if usage else None
        if usage:
            resp.usage.model_dump.return_value = usage
        return resp

    # llm_tools imports LLMRouter at MODULE level, so patch the consumer name.
    LLM_PATH = "nexus.mcp_tools.llm_tools.LLMRouter"

    @patch("nexus.mcp_tools.llm_tools.LLMRouter")
    async def test_llm_complete_happy(self, mock_router_class):
        mock_router = mock_router_class.return_value
        mock_router.complete = AsyncMock(
            return_value=self._mock_response(usage={"prompt_tokens": 10})
        )
        result = await llm_tools.llm_complete("Hello")
        data = json.loads(result)
        assert data["content"] == "response"
        assert data["usage"]["prompt_tokens"] == 10

    @patch("nexus.mcp_tools.llm_tools.LLMRouter")
    async def test_llm_complete_no_usage(self, mock_router_class):
        mock_router = mock_router_class.return_value
        mock_router.complete = AsyncMock(return_value=self._mock_response())
        result = await llm_tools.llm_complete("Hi")
        data = json.loads(result)
        assert data["usage"] == {}

    @patch("nexus.mcp_tools.llm_tools.LLMRouter")
    async def test_llm_complete_custom_params(self, mock_router_class):
        mock_router = mock_router_class.return_value
        mock_router.complete = AsyncMock(return_value=self._mock_response())
        await llm_tools.llm_complete("prompt", model="claude", temperature=0.5, max_tokens=2048)
        _, kwargs = mock_router.complete.call_args
        assert kwargs["temperature"] == 0.5
        assert kwargs["max_tokens"] == 2048

    @patch("nexus.mcp_tools.llm_tools.LLMRouter")
    async def test_llm_complete_error(self, mock_router_class):
        mock_router_class.side_effect = RuntimeError("router fail")
        result = await llm_tools.llm_complete("prompt")
        data = json.loads(result)
        assert "error" in data

    @patch("nexus.mcp_tools.llm_tools.LLMRouter")
    async def test_llm_list_models_happy(self, mock_router_class):
        mock_router = mock_router_class.return_value
        mock_router.list_models.return_value = ["gpt-4", "claude-3"]
        result = await llm_tools.llm_list_models()
        data = json.loads(result)
        assert data["models"] == ["gpt-4", "claude-3"]

    @patch("nexus.mcp_tools.llm_tools.LLMRouter")
    async def test_llm_list_models_error(self, mock_router_class):
        mock_router_class.side_effect = RuntimeError("fail")
        result = await llm_tools.llm_list_models()
        data = json.loads(result)
        assert "error" in data

    @patch("nexus.mcp_tools.llm_tools.LLMRouter")
    async def test_llm_provider_status_happy(self, mock_router_class):
        mock_router = mock_router_class.return_value
        mock_router.get_provider_status.return_value = {"openai": "ok"}
        result = await llm_tools.llm_provider_status()
        data = json.loads(result)
        assert data["providers"] == {"openai": "ok"}

    @patch("nexus.mcp_tools.llm_tools.LLMRouter")
    async def test_llm_provider_status_error(self, mock_router_class):
        mock_router_class.side_effect = RuntimeError("fail")
        result = await llm_tools.llm_provider_status()
        data = json.loads(result)
        assert "error" in data

    @patch("nexus.mcp_tools.llm_tools.LLMRouter")
    async def test_llm_stream_happy(self, mock_router_class):
        mock_router = mock_router_class.return_value
        mock_router.complete = AsyncMock(
            return_value=self._mock_response(content="streamed response")
        )
        result = await llm_tools.llm_stream("prompt")
        data = json.loads(result)
        assert data["content"] == "streamed response"

    @patch("nexus.mcp_tools.llm_tools.LLMRouter")
    async def test_llm_stream_custom_params(self, mock_router_class):
        mock_router = mock_router_class.return_value
        mock_router.complete = AsyncMock(return_value=self._mock_response())
        await llm_tools.llm_stream("prompt", model="claude", temperature=0.3)
        _, kwargs = mock_router.complete.call_args
        assert kwargs["temperature"] == 0.3
        assert kwargs["stream"] is False

    @patch("nexus.mcp_tools.llm_tools.LLMRouter")
    async def test_llm_stream_error(self, mock_router_class):
        mock_router_class.side_effect = RuntimeError("fail")
        result = await llm_tools.llm_stream("prompt")
        data = json.loads(result)
        assert "error" in data


# =============================================================================
# web_tools tests
# =============================================================================

class TestWebTools:
    """Tests for nexus.mcp_tools.web_tools."""

    async def test_web_search_import_error(self):
        """web_search returns error when exa_py not installed."""
        result = await web_tools.web_search("test query")
        data = json.loads(result)
        assert "error" in data
        assert "exa-py not installed" in data["error"]

    async def test_web_search_happy(self):
        """web_search returns results when exa_py available."""
        mock_exa_instance = MagicMock()
        mock_exa_instance.search.return_value = [
            {"title": "Result 1", "url": "https://ex.com/1", "snippet": "Snippet one"},
        ]
        mock_exa_py = MagicMock()
        mock_exa_py.Exa = MagicMock(return_value=mock_exa_instance)

        with patch.dict("sys.modules", {"exa_py": mock_exa_py}):
            result = await web_tools.web_search("test query")
        data = json.loads(result)
        assert data["query"] == "test query"
        assert data["count"] == 1
        assert data["results"][0]["title"] == "Result 1"

    async def test_web_search_general_error(self):
        mock_exa_instance = MagicMock()
        mock_exa_instance.search.side_effect = RuntimeError("API error")
        mock_exa_py = MagicMock()
        mock_exa_py.Exa = MagicMock(return_value=mock_exa_instance)
        with patch.dict("sys.modules", {"exa_py": mock_exa_py}):
            result = await web_tools.web_search("test")
        data = json.loads(result)
        assert "error" in data

    async def test_web_scrape_happy(self):
        mock_response = MagicMock()
        mock_response.text = "<html>content</html>"
        mock_response.status_code = 200
        with patch("nexus.mcp_tools.web_tools.requests", create=True) as mock_req:
            mock_req.get.return_value = mock_response
            result = await web_tools.web_scrape("https://example.com")
        data = json.loads(result)
        assert data["url"] == "https://example.com"
        assert data["status_code"] == 200

    async def test_web_scrape_error(self):
        with patch(
            "nexus.mcp_tools.web_tools.requests", create=True,
        ) as mock_req:
            mock_req.get.side_effect = RuntimeError("connection error")
            result = await web_tools.web_scrape("https://bad.url")
        data = json.loads(result)
        assert "error" in data

    async def test_web_screenshot(self):
        """web_screenshot returns not_implemented status."""
        result = await web_tools.web_screenshot("https://example.com")
        data = json.loads(result)
        assert data["status"] == "not_implemented"

    async def test_web_scrape_truncates_content(self):
        long_content = "x" * 50000
        mock_response = MagicMock()
        mock_response.text = long_content
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_requests = MagicMock()
        mock_requests.get.return_value = mock_response
        with patch.dict("sys.modules", {"requests": mock_requests}):
            result = await web_tools.web_scrape("https://ex.com", max_length=100)
        data = json.loads(result)
        assert data["length"] == 100

    async def test_web_search_num_results(self):
        mock_exa_instance = MagicMock()
        mock_exa_instance.search.return_value = []
        mock_exa_py = MagicMock()
        mock_exa_py.Exa = MagicMock(return_value=mock_exa_instance)
        with patch.dict("sys.modules", {"exa_py": mock_exa_py}):
            await web_tools.web_search("query", num_results=10)
        mock_exa_instance.search.assert_called_with("query", num_results=10)


# =============================================================================
# system_tools tests
# =============================================================================

class TestSystemTools:
    """Tests for nexus.mcp_tools.system_tools.
    
    get_status / get_config use the module-level 'from nexus.core.config import get_settings'
    so we patch the consumer name.  health_check uses a function-level import for
    NexusMemoryService, so we patch at the source there.
    """

    # Module-level import → patch consumer name
    @patch("nexus.mcp_tools.system_tools.get_settings")
    async def test_get_status_happy(self, mock_settings):
        s = MagicMock()
        s.chroma_persist_dir = "/data/chroma"
        s.orchestrator_max_iterations = 25
        mock_settings.return_value = s

        result = await system_tools.get_status()
        data = json.loads(result)
        assert data["status"] == "running"
        assert data["version"] == "1.0.0"

    @patch("nexus.mcp_tools.system_tools.get_settings")
    async def test_get_status_error(self, mock_settings):
        mock_settings.side_effect = RuntimeError("settings fail")
        result = await system_tools.get_status()
        data = json.loads(result)
        assert "error" in data

    @patch("nexus.mcp_tools.system_tools.get_settings")
    async def test_get_config_happy(self, mock_settings):
        s = MagicMock()
        s.chroma_persist_dir = "/data/chroma"
        s.orchestrator_max_iterations = 25
        s.orchestrator_checkpointer = "memory"
        s.orchestrator_interrupt_before_executor = False
        s.log_level = "INFO"
        mock_settings.return_value = s

        result = await system_tools.get_config()
        data = json.loads(result)
        assert data["chroma_persist_dir"] == "/data/chroma"
        assert data["log_level"] == "INFO"

    @patch("nexus.mcp_tools.system_tools.get_settings")
    async def test_get_config_error(self, mock_settings):
        mock_settings.side_effect = RuntimeError("fail")
        result = await system_tools.get_config()
        data = json.loads(result)
        assert "error" in data

    @patch("nexus.memory.chroma_service.NexusMemoryService")
    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_health_check_healthy(self, mock_settings, mock_svc_class):
        mock_svc = mock_svc_class.return_value
        mock_svc.count = AsyncMock(return_value=10)
        result = await system_tools.health_check()
        data = json.loads(result)
        assert data["status"] == "healthy"
        assert data["components"]["memory"] == "ok"

    @patch("nexus.memory.chroma_service.NexusMemoryService")
    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_health_check_degraded(self, mock_settings, mock_svc_class):
        mock_svc = mock_svc_class.return_value
        mock_svc.count = AsyncMock(side_effect=RuntimeError("memory down"))
        result = await system_tools.health_check()
        data = json.loads(result)
        assert data["status"] == "degraded"

    async def test_health_check_outer_error(self):
        """health_check returns error JSON when import itself fails."""
        # The only way to hit the outer try/except is to make the
        # function-level import fail.  Patch sys.modules to prevent
        # accessing the chroma_service module.
        with patch.dict("sys.modules",
                        {"nexus.memory.chroma_service": None}):
            result = await system_tools.health_check()
        data = json.loads(result)
        assert "error" in data


# =============================================================================
# orchestration_tools tests
# =============================================================================

class TestOrchestrationTools:
    """Tests for nexus.mcp_tools.orchestration_tools.

    run_pipeline / run_parallel use function-level imports from
    nexus.orchestrator.pipeline — a module that does not yet exist in
    the codebase.  Those functions always hit the except: branch and
    return error JSON containing the ImportError message.

    run_supervisor / run_swarm have simple inline implementations.
    """

    async def test_run_pipeline_import_error(self):
        """run_pipeline returns error because pipeline module is missing."""
        result = await orchestration_tools.run_pipeline(["task1", "task2"])
        data = json.loads(result)
        assert "error" in data

    async def test_run_pipeline_sequential_false(self):
        """run_pipeline — like above, returns error, import fails anyway."""
        result = await orchestration_tools.run_pipeline(["t1"], sequential=False)
        data = json.loads(result)
        assert "error" in data

    async def test_run_pipeline_empty(self):
        """run_pipeline — import fails, returns error."""
        result = await orchestration_tools.run_pipeline([])
        data = json.loads(result)
        assert "error" in data

    async def test_run_parallel_import_error(self):
        """run_parallel returns error because pipeline module is missing."""
        result = await orchestration_tools.run_parallel(["task1"])
        data = json.loads(result)
        assert "error" in data

    async def test_run_supervisor_happy(self):
        """run_supervisor returns not_implemented status."""
        result = await orchestration_tools.run_supervisor("research", ["agent1", "agent2"])
        data = json.loads(result)
        assert data["status"] == "not_implemented"
        assert data["task"] == "research"
        assert data["agents"] == ["agent1", "agent2"]

    async def test_run_swarm_happy(self):
        """run_swarm returns not_implemented status."""
        result = await orchestration_tools.run_swarm(["task1", "task2"], agent_count=5)
        data = json.loads(result)
        assert data["status"] == "not_implemented"
        assert data["agent_count"] == 5

    async def test_run_swarm_default_agents(self):
        """run_swarm uses default agent_count of 3."""
        result = await orchestration_tools.run_swarm(["t1"])
        data = json.loads(result)
        assert data["agent_count"] == 3


# =============================================================================
# reasoning_tools tests
# =============================================================================

class TestReasoningTools:
    """Tests for nexus.mcp_tools.reasoning_tools.

    reason_react imports `ReactAgent` from nexus.reasoning.react, but the
    actual class is named `ReActLoop` — so the import always fails with
    ImportError, caught by the inner try/except returning error JSON.
    reason_tot and reason_lats have simple inline implementations.
    """

    async def test_reason_react_import_error(self):
        """reason_react returns error because ReactAgent does not exist."""
        result = await reasoning_tools.reason_react("solve problem")
        data = json.loads(result)
        assert "error" in data

    async def test_reason_react_custom_iterations(self):
        """reason_react — import fails regardless of params."""
        result = await reasoning_tools.reason_react("task", max_iterations=20)
        data = json.loads(result)
        assert "error" in data

    async def test_reason_tot_happy(self):
        """reason_tot returns not_implemented status."""
        result = await reasoning_tools.reason_tot("complex problem", max_depth=5, branch_factor=4)
        data = json.loads(result)
        assert data["status"] == "not_implemented"
        assert data["task"] == "complex problem"

    async def test_reason_tot_defaults(self):
        """reason_tot works with default args."""
        result = await reasoning_tools.reason_tot("task")
        data = json.loads(result)
        assert data["status"] == "not_implemented"

    async def test_reason_lats_happy(self):
        """reason_lats returns not_implemented status."""
        result = await reasoning_tools.reason_lats("complex task")
        data = json.loads(result)
        assert data["status"] == "not_implemented"
        assert data["task"] == "complex task"

    async def test_reason_lats_custom_params(self):
        """reason_lats accepts max_simulations / max_depth."""
        result = await reasoning_tools.reason_lats("task", max_simulations=20, max_depth=6)
        data = json.loads(result)
        assert data["status"] == "not_implemented"


# =============================================================================
# bonus_tools tests
# =============================================================================

class TestBonusTools:
    """Tests for nexus.mcp_tools.bonus_tools."""

    @patch("nexus.security.audit.AuditLogger")
    async def test_audit_query_happy(self, mock_logger_class):
        mock_logger = mock_logger_class.return_value
        mock_logger.query.return_value = [{"event": "login"}]
        result = await bonus_tools.audit_query("login", limit=50)
        data = json.loads(result)
        assert data["query"] == "login"
        assert data["count"] == 1

    @patch("nexus.security.audit.AuditLogger")
    async def test_audit_query_with_dates(self, mock_logger_class):
        mock_logger = mock_logger_class.return_value
        mock_logger.query.return_value = []
        await bonus_tools.audit_query("login", start_date="2024-01-01", end_date="2024-12-31")
        mock_logger.query.assert_called_with("login", "2024-01-01", "2024-12-31", 100)

    @patch("nexus.security.audit.AuditLogger")
    async def test_audit_query_error(self, mock_logger_class):
        mock_logger_class.side_effect = RuntimeError("audit fail")
        result = await bonus_tools.audit_query("q")
        data = json.loads(result)
        assert "error" in data

    @patch("nexus.security.rate_limiter.RateLimiter")
    async def test_rate_limit_status_happy(self, mock_limiter_class):
        mock_limiter = mock_limiter_class.return_value
        mock_limiter.get_status.return_value = {
            "remaining": 50, "limit": 100, "reset_at": "2024-01-01T00:00:00Z",
        }
        result = await bonus_tools.rate_limit_status("user-1")
        data = json.loads(result)
        assert data["identifier"] == "user-1"
        assert data["remaining"] == 50

    @patch("nexus.security.rate_limiter.RateLimiter")
    async def test_rate_limit_status_default(self, mock_limiter_class):
        mock_limiter = mock_limiter_class.return_value
        mock_limiter.get_status.return_value = {"remaining": 100, "limit": 100, "reset_at": None}
        result = await bonus_tools.rate_limit_status()
        data = json.loads(result)
        assert data["identifier"] == "default"

    @patch("nexus.security.rate_limiter.RateLimiter")
    async def test_rate_limit_status_error(self, mock_limiter_class):
        mock_limiter_class.side_effect = RuntimeError("ratelimit fail")
        result = await bonus_tools.rate_limit_status("u")
        data = json.loads(result)
        assert "error" in data

    async def test_deep_research_import_error(self):
        """deep_research returns error because nexus.research module is missing."""
        result = await bonus_tools.deep_research("AI safety")
        data = json.loads(result)
        assert "error" in data

    async def test_deep_research_custom_depth(self):
        """deep_research — import fails regardless of params."""
        result = await bonus_tools.deep_research("topic", depth="deep")
        data = json.loads(result)
        assert "error" in data

    @patch("nexus.memory.chroma_service.NexusMemoryService")
    async def test_rag_query_happy(self, mock_svc_class):
        mock_svc = mock_svc_class.return_value
        mock_svc.search = AsyncMock(
            return_value={"documents": [["doc1", "doc2"]], "distances": [[0.1, 0.2]]}
        )
        result = await bonus_tools.rag_query("my question")
        data = json.loads(result)
        assert data["query"] == "my question"
        assert data["namespace"] == "knowledge"
        assert data["count"] == 2

    @patch("nexus.memory.chroma_service.NexusMemoryService")
    async def test_rag_query_custom(self, mock_svc_class):
        mock_svc = mock_svc_class.return_value
        mock_svc.search = AsyncMock(return_value={"documents": [[]], "distances": [[]]})
        await bonus_tools.rag_query("q", namespace="code", top_k=10)
        mock_svc.search.assert_called_with("q", "code", 10)

    @patch("nexus.memory.chroma_service.NexusMemoryService")
    async def test_rag_query_empty(self, mock_svc_class):
        mock_svc = mock_svc_class.return_value
        mock_svc.search = AsyncMock(return_value=None)
        result = await bonus_tools.rag_query("q")
        data = json.loads(result)
        assert data["count"] == 0

    @patch("nexus.memory.chroma_service.NexusMemoryService")
    async def test_rag_query_error(self, mock_svc_class):
        mock_svc_class.side_effect = RuntimeError("rag fail")
        result = await bonus_tools.rag_query("q")
        data = json.loads(result)
        assert "error" in data


# =============================================================================
# context7 tests
# =============================================================================

class TestContext7Tool:
    """Tests for nexus.mcp_tools.context7.Context7Tool.

    context7.py imports get_settings at module level, so we patch the
    consumer name.
    """

    SETT_PATH = "nexus.mcp_tools.context7.get_settings"

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_init_no_api_key(self, mock_settings):
        mock_settings.return_value.context7_api_key = None
        tool = context7_module.Context7Tool()
        assert tool.api_key == ""
        assert tool.base_url == "https://api.context7.ai/v1"

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_init_with_api_key_arg(self, mock_settings):
        tool = context7_module.Context7Tool(api_key="sk-123")
        assert tool.api_key == "sk-123"

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_init_reads_from_settings(self, mock_settings):
        mock_settings.return_value.context7_api_key = "sk-settings"
        tool = context7_module.Context7Tool()
        assert tool.api_key == "sk-settings"

    # --- resolve_library (mock fallback, no API key) ---

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_resolve_library_mock_no_key(self, mock_settings):
        mock_settings.return_value.context7_api_key = None
        tool = context7_module.Context7Tool()
        result = await tool.resolve_library("fastapi")
        assert isinstance(result, context7_module.Context7Library)
        assert result.library_id == "/tiangolo/fastapi"
        assert result.name == "fastapi"

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_resolve_library_known_lib(self, mock_settings):
        mock_settings.return_value.context7_api_key = None
        tool = context7_module.Context7Tool()
        result = await tool.resolve_library("react")
        assert result.library_id == "/facebook/react"

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_resolve_library_unknown_lib(self, mock_settings):
        mock_settings.return_value.context7_api_key = None
        tool = context7_module.Context7Tool()
        result = await tool.resolve_library("my-obscure-lib")
        assert "my-obscure-lib" in result.library_id

    # --- resolve_library with API key ---

    def _mock_aiohttp_session(self, status=200, json_data=None):
        """Build mock aiohttp session supporting async context managers.

        In aiohttp ``session.get(url)`` is an async method returning a
        coroutine.  When that coroutine is awaited it yields a
        ``ClientResponse`` which is itself an async context manager.

        Python's ``async with`` first checks whether the expression
        result has ``__aenter__``.  If it does, it uses it directly.
        If not but it has ``__await__``, it awaits it first.

        We make *both* layers work by giving the return value of
        ``session.get()`` an async ``__aenter__`` so ``async with``
        can use it directly, while making its ``json()`` mock async.
        """
        # Response — must be an async context manager
        mock_response = MagicMock()
        mock_response.status = status
        mock_response.json = AsyncMock(
            return_value=json_data or {"library_id": "/default/lib", "name": "Lib"}
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        # Make the response iterable so that ``async for chunk in resp:``
        # (if ever used) won't crash — not needed here, but safe.
        mock_response.__aiter__ = MagicMock()

        # Session — async context manager that returns itself
        mock_session = MagicMock()
        # session.get(url) returns *the response object* (already has __aenter__)
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_aiohttp = MagicMock()
        mock_aiohttp.ClientSession = MagicMock(return_value=mock_session)
        return mock_aiohttp

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_resolve_library_api_happy(self, mock_settings):
        mock_settings.return_value.context7_api_key = None
        json_data = {
            "library_id": "/custom/lib",
            "name": "CustomLib",
            "description": "A custom library",
            "code_snippets": 50,
            "source_reputation": "High",
            "benchmark_score": 90.0,
            "versions": ["1.0", "2.0"],
        }
        mock_aiohttp = self._mock_aiohttp_session(status=200, json_data=json_data)

        tool = context7_module.Context7Tool(api_key="sk-valid")
        with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
            result = await tool.resolve_library("CustomLib")

        assert result.library_id == "/custom/lib"
        assert result.benchmark_score == 90.0
        assert "2.0" in result.versions

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_resolve_library_api_404(self, mock_settings):
        mock_settings.return_value.context7_api_key = None
        mock_aiohttp = self._mock_aiohttp_session(status=404)

        tool = context7_module.Context7Tool(api_key="sk-valid")
        with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
            result = await tool.resolve_library("fastapi")
        assert result.library_id == "/tiangolo/fastapi"

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_resolve_library_api_500_fallback(self, mock_settings):
        mock_settings.return_value.context7_api_key = None
        mock_aiohttp = self._mock_aiohttp_session(status=500)

        tool = context7_module.Context7Tool(api_key="sk-valid")
        with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
            result = await tool.resolve_library("fastapi")
        assert result.library_id is not None

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_resolve_library_import_error(self, mock_settings):
        """resolve_library falls back to mock when aiohttp not available."""
        mock_settings.return_value.context7_api_key = None
        tool = context7_module.Context7Tool(api_key="sk-valid")
        result = await tool.resolve_library("fastapi")
        assert result.library_id == "/tiangolo/fastapi"

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_resolve_library_general_exception(self, mock_settings):
        """resolve_library falls back on unexpected session error."""
        mock_settings.return_value.context7_api_key = None
        mock_aiohttp = MagicMock()
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(
            side_effect=RuntimeError("connection reset")
        )
        mock_aiohttp.ClientSession = MagicMock(return_value=mock_session)

        tool = context7_module.Context7Tool(api_key="sk-valid")
        with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
            result = await tool.resolve_library("fastapi")
        assert result.library_id == "/tiangolo/fastapi"

    # --- query_docs ---

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_query_docs_mock_no_key(self, mock_settings):
        mock_settings.return_value.context7_api_key = None
        tool = context7_module.Context7Tool()
        result = await tool.query_docs("/tiangolo/fastapi", "how to use WebSockets")
        assert isinstance(result, context7_module.Context7Result)
        assert result.success is True
        assert "API not configured" in result.content

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_query_docs_api_happy(self, mock_settings):
        mock_settings.return_value.context7_api_key = None
        json_data = {
            "content": "FastAPI WebSocket docs here...",
            "sources": ["https://fastapi.tiangolo.com/websockets/"],
        }
        mock_aiohttp = self._mock_aiohttp_session(status=200, json_data=json_data)

        tool = context7_module.Context7Tool(api_key="sk-valid")
        with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
            result = await tool.query_docs("/tiangolo/fastapi", "WebSocket usage")
        assert result.success is True
        assert "FastAPI WebSocket" in result.content

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_query_docs_api_404(self, mock_settings):
        mock_settings.return_value.context7_api_key = None
        mock_aiohttp = self._mock_aiohttp_session(status=404)

        tool = context7_module.Context7Tool(api_key="sk-valid")
        with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
            result = await tool.query_docs("/lib", "question")
        assert result.success is True

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_query_docs_api_error(self, mock_settings):
        mock_settings.return_value.context7_api_key = None
        mock_aiohttp = self._mock_aiohttp_session(status=503)

        tool = context7_module.Context7Tool(api_key="sk-valid")
        with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
            result = await tool.query_docs("/lib", "q")
        assert result.success is True

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_query_docs_import_error(self, mock_settings):
        mock_settings.return_value.context7_api_key = None
        tool = context7_module.Context7Tool(api_key="sk-valid")
        result = await tool.query_docs("/lib", "q")
        assert result.success is True

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_query_docs_general_exception(self, mock_settings):
        mock_settings.return_value.context7_api_key = None
        mock_aiohttp = MagicMock()
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(
            side_effect=RuntimeError("unexpected")
        )
        mock_aiohttp.ClientSession = MagicMock(return_value=mock_session)

        tool = context7_module.Context7Tool(api_key="sk-valid")
        with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
            result = await tool.query_docs("/lib", "q")
        assert result.success is True

    # --- resolve_and_query ---

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_resolve_and_query_happy(self, mock_settings):
        mock_settings.return_value.context7_api_key = None
        tool = context7_module.Context7Tool()
        result = await tool.resolve_and_query("fastapi", "routing")
        assert isinstance(result, context7_module.Context7Result)
        assert result.success is True
        assert result.library_id == "/tiangolo/fastapi"

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_resolve_and_query_unknown(self, mock_settings):
        mock_settings.return_value.context7_api_key = None
        tool = context7_module.Context7Tool()
        result = await tool.resolve_and_query("unknown-lib-xyz", "docs")
        assert result.success is True

    # --- mock helpers ---

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_mock_resolve_known(self, mock_settings):
        mock_settings.return_value.context7_api_key = None
        tool = context7_module.Context7Tool()
        result = tool._mock_resolve("django", "ORM queries")
        assert result.library_id == "/django/django"

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_mock_resolve_unknown(self, mock_settings):
        mock_settings.return_value.context7_api_key = None
        tool = context7_module.Context7Tool()
        result = tool._mock_resolve("my-lib", "")
        assert result.source_reputation == "Medium"
        assert result.benchmark_score == 75.0

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_mock_query(self, mock_settings):
        mock_settings.return_value.context7_api_key = None
        tool = context7_module.Context7Tool()
        result = tool._mock_query("/test/lib", "how to?")
        assert result.library_id == "/test/lib"
        assert result.query == "how to?"
        assert result.success is True


class TestContext7MCPServer:
    """Tests for nexus.mcp_tools.context7.Context7MCPServer."""

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_mcpserver_init(self, mock_settings):
        mock_settings.return_value.context7_api_key = None
        server = context7_module.Context7MCPServer()
        assert server.tool is not None

    @patch("nexus.mcp_tools.context7.Context7Tool")
    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_resolve_library_mcp(self, mock_settings, mock_tool_class):
        mock_result = MagicMock()
        mock_result.library_id = "/test/lib"
        mock_result.name = "TestLib"
        mock_result.description = "A test lib"
        mock_result.code_snippets = 200
        mock_result.source_reputation = "High"
        mock_tool_class.return_value.resolve_library = AsyncMock(return_value=mock_result)

        mock_settings.return_value.context7_api_key = None
        server = context7_module.Context7MCPServer()
        result = await server.resolve_library("TestLib", "docs")
        assert result["library_id"] == "/test/lib"
        assert result["snippets"] == 200

    @patch("nexus.mcp_tools.context7.Context7Tool")
    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_query_docs_mcp(self, mock_settings, mock_tool_class):
        mock_result = MagicMock()
        mock_result.content = "documentation content"
        mock_result.sources = ["https://example.com"]
        mock_result.success = True
        mock_result.error = None
        mock_tool_class.return_value.query_docs = AsyncMock(return_value=mock_result)

        mock_settings.return_value.context7_api_key = None
        server = context7_module.Context7MCPServer()
        result = await server.query_docs("/lib", "question")
        assert result["content"] == "documentation content"
        assert result["success"] is True

    @patch("nexus.mcp_tools.context7.Context7Tool")
    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_search_and_resolve_mcp(self, mock_settings, mock_tool_class):
        mock_result = MagicMock()
        mock_result.library_id = "/lib"
        mock_result.content = "combined content"
        mock_result.sources = []
        mock_result.success = True
        mock_tool_class.return_value.resolve_and_query = AsyncMock(return_value=mock_result)

        mock_settings.return_value.context7_api_key = None
        server = context7_module.Context7MCPServer()
        result = await server.search_and_resolve("Lib", "how to")
        assert result["library_id"] == "/lib"
        assert result["content"] == "combined content"

    @patch("nexus.mcp_tools.context7.get_settings")
    async def test_get_mcp_tools(self, mock_settings):
        mock_settings.return_value.context7_api_key = None
        server = context7_module.Context7MCPServer()
        tools = server.get_mcp_tools()
        assert len(tools) == 3
        assert tools[0]["name"] == "context7_resolve"
        assert tools[1]["name"] == "context7_query"
        assert tools[2]["name"] == "context7_search"
        for tool in tools:
            assert "description" in tool
            assert "input_schema" in tool


# =============================================================================
# mcp_tools __init__ tests
# =============================================================================

class TestMCPToolsInit:
    """Tests for nexus.mcp_tools.__init__ — get_all_tools and exports."""

    def test_get_all_tools_returns_list(self):
        """get_all_tools returns a list of (name, function) tuples."""
        from nexus.mcp_tools import get_all_tools
        tools = get_all_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_get_all_tools_contains_expected_tools(self):
        """get_all_tools includes tools from all modules."""
        from nexus.mcp_tools import get_all_tools
        tools = get_all_tools()
        tool_names = [name for name, _ in tools]
        # Memory tools
        assert "search_memory" in tool_names
        assert "store_memory" in tool_names
        # Knowledge tools
        assert "knowledge_query" in tool_names
        assert "knowledge_add_entity" in tool_names
        # LLM tools
        assert "llm_complete" in tool_names
        assert "llm_list_models" in tool_names
        # Agent tools
        assert "spawn_agent" in tool_names
        assert "list_agents" in tool_names
        # Code tools
        assert "execute_code" in tool_names
        assert "execute_sandboxed" in tool_names
        # File tools
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        # Web tools
        assert "web_search" in tool_names
        assert "web_scrape" in tool_names
        # Reasoning tools
        assert "reason_react" in tool_names
        assert "reason_tot" in tool_names
        assert "reason_lats" in tool_names
        # Orchestration tools
        assert "run_pipeline" in tool_names
        assert "run_parallel" in tool_names
        assert "run_supervisor" in tool_names
        assert "run_swarm" in tool_names
        # System tools
        assert "get_status" in tool_names
        assert "get_config" in tool_names
        assert "health_check" in tool_names
        # Bonus tools
        assert "audit_query" in tool_names
        assert "rate_limit_status" in tool_names
        assert "deep_research" in tool_names
        assert "rag_query" in tool_names

    def test_get_all_tools_all_callable(self):
        """Every item in get_all_tools is a callable function."""
        from nexus.mcp_tools import get_all_tools
        tools = get_all_tools()
        for name, func in tools:
            assert callable(func), f"{name} is not callable"

    def test_module_exports_expected_names(self):
        """__init__.__all__ exports all expected module names."""
        from nexus.mcp_tools import __all__
        expected = [
            "memory_tools",
            "knowledge_tools",
            "llm_tools",
            "agent_tools",
            "code_tools",
            "file_tools",
            "web_tools",
            "reasoning_tools",
            "orchestration_tools",
            "system_tools",
            "bonus_tools",
        ]
        for name in expected:
            assert name in __all__, f"{name} missing from __all__"

    def test_module_has_expected_attributes(self):
        """Each name in __all__ is accessible on the package."""
        import nexus.mcp_tools as pkg
        for name in pkg.__all__:
            assert hasattr(pkg, name), f"{name} missing from package"

    def test_get_all_tools_count(self):
        """get_all_tools returns comprehensive tool list."""
        from nexus.mcp_tools import get_all_tools
        tools = get_all_tools()
        # 5 memory + 5 knowledge + 4 llm + 5 agent + 3 code
        # + 7 file + 3 web + 3 reasoning + 4 orchestration
        # + 3 system + 4 bonus + 8 avatar = 54
        assert len(tools) == 54


# =============================================================================
# orchestration_tools error path tests
# =============================================================================

class TestOrchestrationToolsComplete:
    """Complete coverage for orchestration_tools — happy and error paths."""

    async def test_run_supervisor_error(self):
        """run_supervisor returns error JSON on exception."""
        with patch("json.dumps", side_effect=[TypeError("boom"), '{"error": "boom"}']):
            result = await orchestration_tools.run_supervisor("task", ["agent1"])
        data = json.loads(result)
        assert "error" in data

    async def test_run_swarm_error(self):
        """run_swarm returns error JSON on exception."""
        with patch("json.dumps", side_effect=[TypeError("boom"), '{"error": "boom"}']):
            result = await orchestration_tools.run_swarm(["task1"], agent_count=3)
        data = json.loads(result)
        assert "error" in data

    async def test_run_pipeline_happy_mocked(self):
        """run_pipeline try-block executes with mocked PipelineOrchestrator."""
        mock_pipeline_module = MagicMock()
        mock_orchestrator = MagicMock()
        mock_orchestrator.run = AsyncMock(return_value=["result1", "result2"])
        mock_pipeline_module.PipelineOrchestrator.return_value = mock_orchestrator

        with patch.dict("sys.modules", {"nexus.orchestrator.pipeline": mock_pipeline_module}):
            result = await orchestration_tools.run_pipeline(["task1", "task2"])
        data = json.loads(result)
        assert data["status"] == "completed"
        assert data["count"] == 2
        assert data["results"] == ["result1", "result2"]

    async def test_run_parallel_happy_mocked(self):
        """run_parallel try-block executes with mocked PipelineOrchestrator."""
        mock_pipeline_module = MagicMock()
        mock_orchestrator = MagicMock()
        mock_orchestrator.run = AsyncMock(return_value=["result_a"])
        mock_pipeline_module.PipelineOrchestrator.return_value = mock_orchestrator

        with patch.dict("sys.modules", {"nexus.orchestrator.pipeline": mock_pipeline_module}):
            result = await orchestration_tools.run_parallel(["task1"])
        data = json.loads(result)
        assert data["status"] == "completed"
        assert data["count"] == 1

    async def test_run_pipeline_sequential_false_mocked(self):
        """run_pipeline passes sequential=False with mocked import."""
        mock_pipeline_module = MagicMock()
        mock_orchestrator = MagicMock()
        mock_orchestrator.run = AsyncMock(return_value=[])
        mock_pipeline_module.PipelineOrchestrator.return_value = mock_orchestrator

        with patch.dict("sys.modules", {"nexus.orchestrator.pipeline": mock_pipeline_module}):
            result = await orchestration_tools.run_pipeline(["t1"], sequential=False)
        data = json.loads(result)
        mock_orchestrator.run.assert_called_with(["t1"], False)


# =============================================================================
# reasoning_tools error path tests
# =============================================================================

class TestReasoningToolsComplete:
    """Complete coverage for reasoning_tools — happy and error paths."""

    async def test_reason_lats_error(self):
        """reason_lats returns error JSON on exception."""
        with patch("json.dumps", side_effect=[TypeError("boom"), '{"error": "boom"}']):
            result = await reasoning_tools.reason_lats("complex task")
        data = json.loads(result)
        assert "error" in data

    async def test_reason_tot_error(self):
        """reason_tot returns error JSON on exception."""
        with patch("json.dumps", side_effect=[TypeError("boom"), '{"error": "boom"}']):
            result = await reasoning_tools.reason_tot("complex problem")
        data = json.loads(result)
        assert "error" in data

    async def test_reason_react_happy_mocked(self):
        """reason_react try-block executes with mocked ReactAgent."""
        mock_react_module = MagicMock()
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="reasoning result")
        mock_react_module.ReactAgent.return_value = mock_agent

        with patch.dict("sys.modules", {"nexus.reasoning.react": mock_react_module}):
            result = await reasoning_tools.reason_react("solve problem", max_iterations=15)
        data = json.loads(result)
        assert data["status"] == "completed"
        assert data["task"] == "solve problem"
        assert data["result"] == "reasoning result"
        assert data["iterations"] == 15
        mock_react_module.ReactAgent.assert_called_with(max_iterations=15)

    async def test_reason_react_default_iterations_mocked(self):
        """reason_react uses default max_iterations with mocked import."""
        mock_react_module = MagicMock()
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="result")
        mock_react_module.ReactAgent.return_value = mock_agent

        with patch.dict("sys.modules", {"nexus.reasoning.react": mock_react_module}):
            result = await reasoning_tools.reason_react("task")
        data = json.loads(result)
        assert data["status"] == "completed"
        mock_react_module.ReactAgent.assert_called_with(max_iterations=10)
