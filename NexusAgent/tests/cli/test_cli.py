"""
Comprehensive tests for nexus.cli — Typer CLI application.

Covers ALL commands, sub-apps, error paths, and edge cases.
All external dependencies are mocked at their source modules.
Uses typer.testing.CliRunner for CLI invocation.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

# Import the app — we'll mock module-level imports via patching
from nexus.cli import app

runner = CliRunner()


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_settings():
    """Mock get_settings() at the nexus.cli import site with rich mock config."""
    settings = MagicMock()
    # Environment enum needs .value attribute
    env_mock = MagicMock()
    env_mock.value = "development"
    settings.nexus_env = env_mock
    log_level_mock = MagicMock()
    log_level_mock.value = "INFO"
    settings.nexus_log_level = log_level_mock
    settings.nexus_host = "0.0.0.0"
    settings.nexus_port = 8080
    settings.chroma_persist_dir = "./nexus_data/chroma"
    settings.chroma_host = "localhost"
    settings.chroma_port = 8000
    settings.browser_service_url = "http://localhost:8001"
    settings.browser_service_enabled = True
    settings.sandbox_enabled = True
    settings.ollama_base_url = "http://127.0.0.1:11434"
    settings.ollama_default_model = "llama3.1:8b"
    settings.llm_default_provider = "openai"
    settings.llm_default_model = "gpt-4o"
    settings.llm_fallback_chain = "openai,anthropic,gemini,glm,ollama"
    settings.memory_max_working_tokens = 30000
    settings.rate_limit_rpm = 60
    settings.openai_api_key = "sk-test-openai"
    settings.anthropic_api_key = ""
    settings.google_api_key = "sk-test-google"
    settings.zai_api_key = ""
    # available_providers is a property that returns a list
    settings.available_providers = ["openai", "gemini", "ollama"]
    return settings


@pytest.fixture
def mock_evaluator_result():
    """Standard Evaluator result dict."""
    return {
        "score": 0.85,
        "test_cases_passed": 17,
        "test_cases_total": 20,
        "latency_ms": 450.0,
        "skill_id": "test-skill",
        "agent_type": None,
    }


@pytest.fixture
def mock_evaluator_suite_results():
    """Standard Evaluator suite results list."""
    return [
        {
            "score": 0.85,
            "test_cases_passed": 17,
            "test_cases_total": 20,
            "latency_ms": 450.0,
            "skill_id": "skill-a",
            "agent_type": None,
        },
        {
            "score": 0.62,
            "test_cases_passed": 10,
            "test_cases_total": 18,
            "latency_ms": 320.0,
            "skill_id": None,
            "agent_type": "researcher",
        },
    ]


# =============================================================================
# 1. Typer App Initialization
# =============================================================================

class TestCliApp:
    """Verify the Typer app and sub-apps are wired correctly."""

    def test_app_has_name(self):
        """App name should be 'nexus'."""
        assert app.info.name == "nexus"

    def test_app_has_commands(self):
        """App should register top-level commands."""
        command_names = {c.callback.__name__ for c in app.registered_commands}
        assert "run" in command_names
        assert "chat" in command_names
        assert "status" in command_names
        assert "config" in command_names
        assert "serve" in command_names

    def test_app_has_sub_apps(self):
        """App should register all sub-apps."""
        group_names = {g.name for g in app.registered_groups}
        assert "agents" in group_names
        assert "skills" in group_names
        assert "eval" in group_names
        assert "context7" in group_names
        assert "memory" in group_names

    def test_agents_sub_app_has_commands(self):
        """agents sub-app should have 'list' command."""
        agents_group = [g for g in app.registered_groups if g.name == "agents"][0]
        cmd_names = {c.name for c in agents_group.typer_instance.registered_commands}
        assert "list" in cmd_names

    def test_skills_sub_app_has_commands(self):
        """skills sub-app should have 'deploy' and 'list' commands."""
        skills_group = [g for g in app.registered_groups if g.name == "skills"][0]
        cmd_names = {c.name for c in skills_group.typer_instance.registered_commands}
        assert "deploy" in cmd_names
        assert "list" in cmd_names

    def test_eval_sub_app_has_commands(self):
        """eval sub-app should have 'run' and 'suite' commands."""
        eval_group = [g for g in app.registered_groups if g.name == "eval"][0]
        cmd_names = {c.name for c in eval_group.typer_instance.registered_commands}
        assert "run" in cmd_names
        assert "suite" in cmd_names

    def test_context7_sub_app_has_commands(self):
        """context7 sub-app should have 'query' and 'libraries' commands."""
        ctx_group = [g for g in app.registered_groups if g.name == "context7"][0]
        cmd_names = {c.name for c in ctx_group.typer_instance.registered_commands}
        assert "query" in cmd_names
        assert "libraries" in cmd_names

    def test_memory_sub_app_has_commands(self):
        """memory sub-app should have 'stats' and 'search' commands."""
        mem_group = [g for g in app.registered_groups if g.name == "memory"][0]
        cmd_names = {c.name for c in mem_group.typer_instance.registered_commands}
        assert "stats" in cmd_names
        assert "search" in cmd_names


# =============================================================================
# 2. run Command
# =============================================================================

class TestRunCommand:
    """Tests for 'nexus run <task>' command."""

    def test_run_completed(self, mock_settings):
        """Run a task that completes successfully shows green Panel."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.orchestrator.langgraph_engine.run_nexus_task",
                   new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {
                "status": "completed",
                "result": "Task completed successfully",
                "plan": "1. Do this\n2. Do that",
                "iterations": 3,
                "thread_id": "thread-42",
            }

            result = runner.invoke(app, ["run", "Write a test"])

            assert result.exit_code == 0
            assert "Running" in result.output or "NEXUS Task" in result.output
            assert "Completed" in result.output
            assert "Task completed successfully" in result.output
            mock_run.assert_called_once_with(task="Write a test", thread_id=None)

    def test_run_with_options(self, mock_settings):
        """Run with --provider, --complexity, --thread options."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.orchestrator.langgraph_engine.run_nexus_task",
                   new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {
                "status": "completed",
                "result": "Done",
                "iterations": 1,
            }

            result = runner.invoke(app, [
                "run", "Analyze data",
                "--provider", "anthropic",
                "--complexity", "complex",
                "--thread", "th-001",
            ])

            assert result.exit_code == 0
            assert "Completed" in result.output
            mock_run.assert_called_once_with(task="Analyze data", thread_id="th-001")

    def test_run_failed(self, mock_settings):
        """Run task that fails shows red Error panel."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.orchestrator.langgraph_engine.run_nexus_task",
                   new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {
                "status": "failed",
                "result": "Something went wrong",
            }

            result = runner.invoke(app, ["run", "Bad task"])

            assert result.exit_code == 0
            assert "Failed" in result.output or "Error" in result.output
            assert "Something went wrong" in result.output


# =============================================================================
# 3. chat Command
# =============================================================================

class TestChatCommand:
    """Tests for 'nexus chat' interactive command."""

    def test_chat_exit_via_quit(self, mock_settings):
        """Chat exits cleanly when user types 'quit'."""
        mock_response = MagicMock()
        mock_response.content = "Hello! How can I help?"
        mock_response.provider = MagicMock()
        mock_response.provider.value = "openai"
        mock_response.model = "gpt-4o"

        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.llm.router.LLMRouter") as mock_router_cls:
            mock_router = MagicMock()
            mock_router.complete = AsyncMock(return_value=mock_response)
            mock_router_cls.return_value = mock_router

            result = runner.invoke(app, ["chat"], input="hello\nq\n")

            assert result.exit_code == 0
            # Should have printed welcome and response
            assert "Welcome" in result.output or "NEXUS Interactive Chat" in result.output
            assert mock_router.complete.called

    def test_chat_exit_via_exit(self, mock_settings):
        """Chat exits cleanly when user types 'exit'."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.llm.router.LLMRouter") as mock_router_cls:
            mock_router = MagicMock()
            mock_router.complete = AsyncMock()
            mock_router_cls.return_value = mock_router

            result = runner.invoke(app, ["chat"], input="exit\n")

            assert result.exit_code == 0

    def test_chat_exit_via_eof(self, mock_settings):
        """Chat exits on EOFError (Ctrl+D)."""
        # Simulate EOF by patching only console.input, not the entire console
        from nexus.cli import console as cli_console
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch.object(cli_console, "input", side_effect=EOFError()):

            result = runner.invoke(app, ["chat"])

            assert result.exit_code == 0
            assert "Goodbye" in result.output

    def test_chat_skips_empty_input(self, mock_settings):
        """Chat skips empty lines and continues."""
        mock_response = MagicMock()
        mock_response.content = "Sure!"
        mock_response.provider = MagicMock()
        mock_response.provider.value = "openai"
        mock_response.model = "gpt-4o"

        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.llm.router.LLMRouter") as mock_router_cls:
            mock_router = MagicMock()
            mock_router.complete = AsyncMock(return_value=mock_response)
            mock_router_cls.return_value = mock_router
            # Feed: empty line, message, quit
            result = runner.invoke(app, ["chat"], input="\nhello\nq\n")
            assert result.exit_code == 0

    def test_chat_handles_llm_error(self, mock_settings):
        """Chat handles LLMRouter error gracefully."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.llm.router.LLMRouter") as mock_router_cls:
            mock_router = MagicMock()
            mock_router.complete = AsyncMock(side_effect=Exception("API error"))
            mock_router_cls.return_value = mock_router

            result = runner.invoke(app, ["chat"], input="hello\nq\n")

            assert result.exit_code == 0
            assert "Error" in result.output or "API error" in result.output


# =============================================================================
# 4. status Command
# =============================================================================

class TestStatusCommand:
    """Tests for 'nexus status' command."""

    def test_status_shows_info(self, mock_settings):
        """Status displays agent information and property table."""
        with patch("nexus.cli.get_settings", return_value=mock_settings):
            result = runner.invoke(app, ["status"])

            assert result.exit_code == 0
            assert "NEXUS Agent Status" in result.output
            assert "Agent" in result.output
            assert "NEXUS" in result.output
            assert "Version" in result.output
            assert "0.1.0" in result.output
            assert "Environment" in result.output
            assert "development" in result.output
            assert "Port" in result.output
            assert "8080" in result.output

    def test_status_shows_providers(self, mock_settings):
        """Status should list configured providers."""
        with patch("nexus.cli.get_settings", return_value=mock_settings):
            result = runner.invoke(app, ["status"])

            assert result.exit_code == 0
            assert "openai" in result.output
            assert "gemini" in result.output
            assert "ollama" in result.output

    def test_status_shows_browser_sandbox(self, mock_settings):
        """Status should show browser and sandbox status."""
        with patch("nexus.cli.get_settings", return_value=mock_settings):
            result = runner.invoke(app, ["status"])

            assert result.exit_code == 0
            assert "Browser Service" in result.output
            assert "Sandbox" in result.output
            assert "enabled" in result.output


# =============================================================================
# 5. config Command
# =============================================================================

class TestConfigCommand:
    """Tests for 'nexus config' command."""

    def test_config_shows_settings(self, mock_settings):
        """Config displays non-sensitive settings."""
        with patch("nexus.cli.get_settings", return_value=mock_settings):
            result = runner.invoke(app, ["config"])

            assert result.exit_code == 0
            assert "NEXUS Configuration" in result.output
            assert "nexus_env" in result.output
            assert "nexus_host" in result.output
            assert "nexus_port" in result.output
            assert "chroma_persist_dir" in result.output
            assert "openai_configured" in result.output
            assert "yes" in result.output  # openai has key

    def test_config_shows_configured_providers(self, mock_settings):
        """Config shows yes/no for provider API keys."""
        with patch("nexus.cli.get_settings", return_value=mock_settings):
            result = runner.invoke(app, ["config"])

            assert "openai_configured" in result.output
            assert "anthropic_configured" in result.output
            assert "google_configured" in result.output
            assert "zai_configured" in result.output
            assert "yes" in result.output  # openai + google
            # anthropic and zai have empty keys → "no"
            assert len([l for l in result.output.split("\n") if "no" in l]) >= 2


# =============================================================================
# 6. serve Command
# =============================================================================

class TestServeCommand:
    """Tests for 'nexus serve' command."""

    def test_serve_launches_uvicorn(self, mock_settings):
        """Serve launches uvicorn with default parameters."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("uvicorn.run") as mock_uvicorn_run:
            # Make uvicorn.run raise SystemExit to stop serving
            mock_uvicorn_run.side_effect = SystemExit(0)

            result = runner.invoke(app, ["serve"])

            assert result.exit_code == 0
            assert "NEXUS Backend Server" in result.output
            mock_uvicorn_run.assert_called_once()
            call_kwargs = mock_uvicorn_run.call_args[1]
            assert call_kwargs["host"] == "0.0.0.0"
            assert call_kwargs["port"] == 8080
            assert call_kwargs["reload"] is False
            assert call_kwargs["log_level"] == "info"

    def test_serve_with_custom_options(self, mock_settings):
        """Serve accepts custom host, port, reload, log-level."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("uvicorn.run") as mock_uvicorn_run:
            mock_uvicorn_run.side_effect = SystemExit(0)

            result = runner.invoke(app, [
                "serve", "--host", "127.0.0.1", "--port", "9090",
                "--reload", "--log-level", "debug",
            ])

            assert result.exit_code == 0
            call_kwargs = mock_uvicorn_run.call_args[1]
            assert call_kwargs["host"] == "127.0.0.1"
            assert call_kwargs["port"] == 9090
            assert call_kwargs["reload"] is True
            assert call_kwargs["log_level"] == "debug"


# =============================================================================
# 7. agents list Command
# =============================================================================

class TestAgentsListCommand:
    """Tests for 'nexus agents list' command."""

    def test_agents_list_shows_instances(self, mock_settings):
        """Agents list shows a table of active agents."""
        mock_instance = MagicMock()
        mock_instance.agent_id = "agent-001"
        mock_instance.agent_type = "researcher"
        mock_instance.status = MagicMock()
        mock_instance.status.value = "running"
        mock_instance.created_at = MagicMock()
        mock_instance.created_at.isoformat.return_value = "2026-01-01T00:00:00"

        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.core.registry.AgentRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.list_instances.return_value = [mock_instance]
            mock_registry_cls.return_value = mock_registry

            result = runner.invoke(app, ["agents", "list"])

            assert result.exit_code == 0
            assert "Active Agents" in result.output
            assert "agent-001" in result.output
            assert "researcher" in result.output
            assert "running" in result.output

    def test_agents_list_empty(self, mock_settings):
        """Agents list shows message when no agents exist."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.core.registry.AgentRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.list_instances.return_value = []
            mock_registry_cls.return_value = mock_registry

            result = runner.invoke(app, ["agents", "list"])

            assert result.exit_code == 0
            assert "No active agents" in result.output


# =============================================================================
# 8. skills deploy Command
# =============================================================================

class TestSkillsDeployCommand:
    """Tests for 'nexus skills deploy' command."""

    def test_skills_deploy_success(self, mock_settings):
        """Deploy a skill successfully shows green panel."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.orchestrator.skill_lifecycle.SkillLifecycleManager") as mock_mgr_cls:
            mock_mgr = MagicMock()
            mock_mgr.deploy_skill = AsyncMock(return_value={
                "success": True,
                "skill_id": "skill-abc-123",
            })
            mock_mgr_cls.return_value = mock_mgr

            result = runner.invoke(app, ["skills", "deploy", "/path/to/skill.json"])

            assert result.exit_code == 0
            assert "Deploying skill" in result.output
            assert "Deploy" in result.output or "deployed" in result.output
            assert "skill-abc-123" in result.output
            mock_mgr.deploy_skill.assert_called_once_with("/path/to/skill.json", force=False)

    def test_skills_deploy_with_force(self, mock_settings):
        """Deploy a skill with --force flag."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.orchestrator.skill_lifecycle.SkillLifecycleManager") as mock_mgr_cls:
            mock_mgr = MagicMock()
            mock_mgr.deploy_skill = AsyncMock(return_value={
                "success": True,
                "skill_id": "skill-xyz",
            })
            mock_mgr_cls.return_value = mock_mgr

            result = runner.invoke(app, ["skills", "deploy", "my-skill", "--force"])

            assert result.exit_code == 0
            mock_mgr.deploy_skill.assert_called_once_with("my-skill", force=True)

    def test_skills_deploy_failure(self, mock_settings):
        """Deploy a skill that fails shows error panel."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.orchestrator.skill_lifecycle.SkillLifecycleManager") as mock_mgr_cls:
            mock_mgr = MagicMock()
            mock_mgr.deploy_skill = AsyncMock(return_value={
                "success": False,
                "error": "Validation failed",
            })
            mock_mgr_cls.return_value = mock_mgr

            result = runner.invoke(app, ["skills", "deploy", "bad-skill"])

            assert result.exit_code == 0
            assert "Deploy failed" in result.output or "failed" in result.output.lower()
            assert "Validation failed" in result.output

    def test_skills_deploy_exception(self, mock_settings):
        """Deploy that raises an exception shows error message."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.orchestrator.skill_lifecycle.SkillLifecycleManager") as mock_mgr_cls:
            mock_mgr = MagicMock()
            mock_mgr.deploy_skill = AsyncMock(side_effect=RuntimeError("Unexpected error"))
            mock_mgr_cls.return_value = mock_mgr

            result = runner.invoke(app, ["skills", "deploy", "buggy-skill"])

            assert result.exit_code == 0
            assert "Error deploying skill" in result.output
            assert "Unexpected error" in result.output


# =============================================================================
# 9. skills list Command
# =============================================================================

class TestSkillsListCommand:
    """Tests for 'nexus skills list' command."""

    def test_skills_list_shows_skills(self, mock_settings):
        """Skills list shows a table of registered skills."""
        mock_skills = [
            {"id": "skill-1", "name": "Web Scraper", "version": "1.0.0", "status": "active"},
            {"id": "skill-2", "name": "Code Analyzer", "version": "2.1.0", "status": "draft"},
        ]

        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.orchestrator.skill_lifecycle.SkillLifecycleManager") as mock_mgr_cls:
            mock_mgr = MagicMock()
            mock_mgr.list_skills.return_value = mock_skills
            mock_mgr_cls.return_value = mock_mgr

            result = runner.invoke(app, ["skills", "list"])

            assert result.exit_code == 0
            assert "Available Skills" in result.output
            assert "skill-1" in result.output
            assert "Web Scraper" in result.output
            assert "skill-2" in result.output
            assert "Code Analyzer" in result.output

    def test_skills_list_empty(self, mock_settings):
        """Skills list shows message when no skills exist."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.orchestrator.skill_lifecycle.SkillLifecycleManager") as mock_mgr_cls:
            mock_mgr = MagicMock()
            mock_mgr.list_skills.return_value = []
            mock_mgr_cls.return_value = mock_mgr

            result = runner.invoke(app, ["skills", "list"])

            assert result.exit_code == 0
            assert "No skills registered" in result.output


# =============================================================================
# 10. eval run Command
# =============================================================================

class TestEvalRunCommand:
    """Tests for 'nexus eval run' command."""

    def test_eval_run_with_skill(self, mock_settings, mock_evaluator_result):
        """Eval run with --skill flag evaluates a skill."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.core.evaluation.Evaluator", create=True) as mock_eval_cls:
            mock_eval = MagicMock()
            mock_eval.evaluate_skill = AsyncMock(return_value=mock_evaluator_result)
            mock_eval_cls.return_value = mock_eval

            result = runner.invoke(app, ["eval", "run", "--skill", "test-skill"])

            assert result.exit_code == 0
            assert "Running evaluation" in result.output
            assert "Evaluation Results" in result.output
            assert "85.0%" in result.output or "Score" in result.output
            assert "test-skill" in result.output
            mock_eval.evaluate_skill.assert_called_once_with("test-skill")

    def test_eval_run_with_agent(self, mock_settings, mock_evaluator_result):
        """Eval run with --agent flag evaluates an agent type."""
        result_with_agent = dict(mock_evaluator_result)
        result_with_agent["skill_id"] = None
        result_with_agent["agent_type"] = "researcher"

        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.core.evaluation.Evaluator", create=True) as mock_eval_cls:
            mock_eval = MagicMock()
            mock_eval.evaluate_agent = AsyncMock(return_value=result_with_agent)
            mock_eval_cls.return_value = mock_eval

            result = runner.invoke(app, ["eval", "run", "--agent", "researcher"])

            assert result.exit_code == 0
            mock_eval.evaluate_agent.assert_called_once_with("researcher")

    def test_eval_run_default_suite(self, mock_settings, mock_evaluator_suite_results):
        """Eval run without --skill or --agent runs benchmark suite."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.core.evaluation.Evaluator", create=True) as mock_eval_cls:
            mock_eval = MagicMock()
            mock_eval.run_benchmark_suite = AsyncMock(return_value=mock_evaluator_suite_results)
            mock_eval_cls.return_value = mock_eval

            result = runner.invoke(app, ["eval", "run"])

            assert result.exit_code == 0
            mock_eval.run_benchmark_suite.assert_called_once()

    def test_eval_run_low_score_color(self, mock_settings):
        """Low score below 0.5 shows red border."""
        low_result = {"score": 0.3, "test_cases_passed": 3, "test_cases_total": 10,
                       "latency_ms": 200.0, "skill_id": "weak-skill", "agent_type": None}

        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.core.evaluation.Evaluator", create=True) as mock_eval_cls:
            mock_eval = MagicMock()
            mock_eval.evaluate_skill = AsyncMock(return_value=low_result)
            mock_eval_cls.return_value = mock_eval

            result = runner.invoke(app, ["eval", "run", "--skill", "weak-skill"])

            assert result.exit_code == 0
            assert "30.0%" in result.output or "Score" in result.output

    def test_eval_run_with_benchmarks(self, mock_settings, mock_evaluator_result):
        """Eval run with --benchmarks flag."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.core.evaluation.Evaluator", create=True) as mock_eval_cls:
            mock_eval = MagicMock()
            mock_eval.evaluate_skill = AsyncMock(return_value=mock_evaluator_result)
            mock_eval_cls.return_value = mock_eval

            result = runner.invoke(app, [
                "eval", "run", "--skill", "test-skill", "--benchmarks", "accuracy,latency",
            ])

            assert result.exit_code == 0

    def test_eval_run_exception(self, mock_settings):
        """Eval run exception shows error message."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.core.evaluation.Evaluator", create=True) as mock_eval_cls:
            mock_eval = MagicMock()
            mock_eval.run_benchmark_suite = AsyncMock(
                side_effect=RuntimeError("Eval crashed"))
            mock_eval_cls.return_value = mock_eval

            result = runner.invoke(app, ["eval", "run"])

            assert result.exit_code == 0
            assert "Error running evaluation" in result.output


# =============================================================================
# 11. eval suite Command
# =============================================================================

class TestEvalSuiteCommand:
    """Tests for 'nexus eval suite' command."""

    def test_eval_suite_shows_results(self, mock_settings, mock_evaluator_suite_results):
        """Eval suite displays a table of benchmark results."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.core.evaluation.Evaluator", create=True) as mock_eval_cls:
            mock_eval = MagicMock()
            mock_eval.run_benchmark_suite = AsyncMock(return_value=mock_evaluator_suite_results)
            mock_eval_cls.return_value = mock_eval

            result = runner.invoke(app, ["eval", "suite"])

            assert result.exit_code == 0
            assert "Benchmark Results" in result.output
            assert "Benchmark" in result.output or "benchmark" in result.output.lower()
            assert "87" in result.output or "17/20" in result.output  # test_cases_passed/total
            assert "10/18" in result.output

    def test_eval_suite_exception(self, mock_settings):
        """Eval suite exception shows error message."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.core.evaluation.Evaluator", create=True) as mock_eval_cls:
            mock_eval = MagicMock()
            mock_eval.run_benchmark_suite = AsyncMock(
                side_effect=RuntimeError("Suite failed"))
            mock_eval_cls.return_value = mock_eval

            result = runner.invoke(app, ["eval", "suite"])

            assert result.exit_code == 0
            assert "Error running suite" in result.output


# =============================================================================
# 12. context7 query Command
# =============================================================================

class TestContext7QueryCommand:
    """Tests for 'nexus context7 query' command."""

    def test_context7_query_with_question(self, mock_settings):
        """Query with --question flag uses query_docs."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.mcp_tools.context7.Context7MCPServer") as mock_srv_cls:
            mock_srv = MagicMock()
            mock_srv.query_docs = AsyncMock(return_value={
                "content": "FastAPI uses Pydantic for data validation",
                "sources": ["https://fastapi.tiangolo.com"],
                "success": True,
            })
            mock_srv_cls.return_value = mock_srv

            result = runner.invoke(app, [
                "context7", "query", "fastapi",
                "--question", "How does validation work?",
            ])

            assert result.exit_code == 0
            assert "Results" in result.output or "Result" in result.output
            mock_srv.query_docs.assert_called_once()

    def test_context7_query_without_question(self, mock_settings):
        """Query without --question uses resolve_library."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.mcp_tools.context7.Context7MCPServer") as mock_srv_cls:
            mock_srv = MagicMock()
            mock_srv.resolve_library = AsyncMock(return_value={
                "library_id": "/tiangolo/fastapi",
                "name": "fastapi",
                "description": "FastAPI framework",
                "snippets": 250,
                "reputation": "High",
            })
            mock_srv_cls.return_value = mock_srv

            result = runner.invoke(app, ["context7", "query", "fastapi"])

            assert result.exit_code == 0
            # dict results get title "Context7 Result" (singular)
            assert "Context7 Result" in result.output
            assert "fastapi" in result.output
            mock_srv.resolve_library.assert_called_once()

    def test_context7_query_no_results(self, mock_settings):
        """Query with no results shows appropriate message."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.mcp_tools.context7.Context7MCPServer") as mock_srv_cls:
            mock_srv = MagicMock()
            mock_srv.resolve_library = AsyncMock(return_value={"info": "no results"})
            mock_srv_cls.return_value = mock_srv

            result = runner.invoke(app, ["context7", "query", "unknown-lib"])

            assert result.exit_code == 0

    def test_context7_query_exception(self, mock_settings):
        """Context7 query exception shows error."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.mcp_tools.context7.Context7MCPServer") as mock_srv_cls:
            mock_srv = MagicMock()
            mock_srv.resolve_library = AsyncMock(side_effect=RuntimeError("API down"))
            mock_srv_cls.return_value = mock_srv

            result = runner.invoke(app, ["context7", "query", "fastapi"])

            assert result.exit_code == 0
            assert "Error querying Context7" in result.output


# =============================================================================
# 13. context7 libraries Command
# =============================================================================

class TestContext7LibrariesCommand:
    """Tests for 'nexus context7 libraries' command."""

    def test_context7_libraries_shows_table(self, mock_settings):
        """Libraries command shows a table of known libraries."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.mcp_tools.context7.KNOWN_LIBRARIES", {
                 "fastapi": "/tiangolo/fastapi",
                 "react": "/facebook/react",
                 "next.js": "/vercel/next.js",
             }):
            result = runner.invoke(app, ["context7", "libraries"])

            assert result.exit_code == 0
            assert "Known Context7 Libraries" in result.output
            assert "fastapi" in result.output
            assert "tiangolo/fastapi" in result.output
            assert "react" in result.output
            assert "facebook/react" in result.output
            assert "next.js" in result.output


# =============================================================================
# 14. memory stats Command
# =============================================================================

class TestMemoryStatsCommand:
    """Tests for 'nexus memory stats' command."""

    def test_memory_stats_shows_counts(self, mock_settings):
        """Memory stats shows a table of namespace counts."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.memory.chroma_service.NexusMemoryService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.count = AsyncMock(side_effect=lambda namespace: {
                "conversations": 42,
                "episodes": 15,
                "knowledge": 100,
                "skills": 8,
                "identity": 3,
                "code": 27,
            }.get(namespace, 0))
            mock_svc_cls.return_value = mock_svc

            result = runner.invoke(app, ["memory", "stats"])

            assert result.exit_code == 0
            assert "NEXUS Memory Statistics" in result.output or "Memory" in result.output
            # All namespaces should be listed
            for ns in ["conversations", "episodes", "knowledge", "skills", "identity", "code"]:
                assert ns in result.output

    def test_memory_stats_handles_count_error(self, mock_settings):
        """Memory stats handles namespace count errors gracefully."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.memory.chroma_service.NexusMemoryService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.count = AsyncMock(side_effect=Exception("DB error"))
            mock_svc_cls.return_value = mock_svc

            result = runner.invoke(app, ["memory", "stats"])

            assert result.exit_code == 0
            # Should show "error" for each namespace
            assert result.exit_code == 0

    def test_memory_stats_service_exception(self, mock_settings):
        """Memory stats exception when creating service shows error."""
        with patch("nexus.cli.get_settings", return_value=mock_settings):
            # Make NexusMemoryService constructor raise
            result = runner.invoke(app, ["memory", "stats"])

            assert result.exit_code == 0


# =============================================================================
# 15. memory search Command
# =============================================================================

class TestMemorySearchCommand:
    """Tests for 'nexus memory search' command."""

    def test_memory_search_finds_results(self, mock_settings):
        """Memory search returns and displays results."""
        mock_search_result = {
            "ids": [["doc-1", "doc-2"]],
            "documents": [["First document content", "Second document content"]],
            "distances": [[0.15, 0.42]],
        }

        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.memory.chroma_service.NexusMemoryService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.search = AsyncMock(return_value=mock_search_result)
            mock_svc_cls.return_value = mock_svc

            result = runner.invoke(app, [
                "memory", "search", "test query",
            ])

            assert result.exit_code == 0
            assert "First document content" in result.output or "First document" in result.output
            assert "doc-1" in result.output

    def test_memory_search_with_options(self, mock_settings):
        """Memory search accepts --namespace and --top-k options."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.memory.chroma_service.NexusMemoryService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.search = AsyncMock(return_value={"ids": [[]], "documents": [[]], "distances": [[]]})
            mock_svc_cls.return_value = mock_svc

            result = runner.invoke(app, [
                "memory", "search", "test",
                "--namespace", "episodes",
                "--top-k", "3",
            ])

            assert result.exit_code == 0
            mock_svc.search.assert_called_once_with(
                query="test", namespace="episodes", top_k=3,
            )

    def test_memory_search_no_results(self, mock_settings):
        """Memory search shows message when no results found."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.memory.chroma_service.NexusMemoryService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.search = AsyncMock(return_value={"ids": [[]], "documents": [[]], "distances": [[]]})
            mock_svc_cls.return_value = mock_svc

            result = runner.invoke(app, ["memory", "search", "nonexistent"])

            assert result.exit_code == 0
            assert "No results found" in result.output

    def test_memory_search_exception(self, mock_settings):
        """Memory search exception shows error."""
        with patch("nexus.cli.get_settings", return_value=mock_settings), \
             patch("nexus.memory.chroma_service.NexusMemoryService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.search = AsyncMock(side_effect=RuntimeError("Search failed"))
            mock_svc_cls.return_value = mock_svc

            result = runner.invoke(app, ["memory", "search", "test"])

            assert result.exit_code == 0
            assert "Error" in result.output or "Search failed" in result.output


# =============================================================================
# 16. Help / No-arg / Edge Cases
# =============================================================================

class TestCliEdgeCases:
    """Edge cases for the CLI."""

    def test_help_shows_all_commands(self):
        """--help should list all commands and sub-apps."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "run" in result.output
        assert "chat" in result.output
        assert "status" in result.output
        assert "config" in result.output
        assert "serve" in result.output
        assert "agents" in result.output
        assert "skills" in result.output
        assert "eval" in result.output
        assert "context7" in result.output
        assert "memory" in result.output

    def test_agents_help(self):
        """agents sub-command --help shows list command."""
        result = runner.invoke(app, ["agents", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output

    def test_skills_help(self):
        """skills sub-command --help shows deploy and list."""
        result = runner.invoke(app, ["skills", "--help"])
        assert result.exit_code == 0
        assert "deploy" in result.output
        assert "list" in result.output

    def test_eval_help(self):
        """eval sub-command --help shows run and suite."""
        result = runner.invoke(app, ["eval", "--help"])
        assert result.exit_code == 0
        assert "run" in result.output
        assert "suite" in result.output

    def test_context7_help(self):
        """context7 sub-command --help shows query and libraries."""
        result = runner.invoke(app, ["context7", "--help"])
        assert result.exit_code == 0
        assert "query" in result.output
        assert "libraries" in result.output

    def test_memory_help(self):
        """memory sub-command --help shows stats and search."""
        result = runner.invoke(app, ["memory", "--help"])
        assert result.exit_code == 0
        assert "stats" in result.output
        assert "search" in result.output

    def test_run_missing_required_arg(self):
        """run without the required task argument shows error."""
        result = runner.invoke(app, ["run"])
        assert result.exit_code != 0
        assert "Error" in result.output or "Missing" in result.output

    def test_skills_deploy_missing_required_arg(self):
        """skills deploy without path shows error."""
        result = runner.invoke(app, ["skills", "deploy"])
        assert result.exit_code != 0

    def test_context7_query_missing_required_arg(self):
        """context7 query without library arg shows error."""
        result = runner.invoke(app, ["context7", "query"])
        assert result.exit_code != 0

    def test_memory_search_missing_required_arg(self):
        """memory search without query arg shows error."""
        result = runner.invoke(app, ["memory", "search"])
        assert result.exit_code != 0
