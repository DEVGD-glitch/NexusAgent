"""Tests for the Modes System."""

import pytest
from nexus.modes.modes import AgentMode, ModeConfig, SAFE_CONFIG, BALANCED_CONFIG, AUTONOMOUS_CONFIG, SANDBOX_CONFIG
from nexus.modes.engine import ModeEngine


class TestAgentMode:
    def test_all_modes(self):
        assert AgentMode.SAFE.value == "safe"
        assert AgentMode.BALANCED.value == "balanced"
        assert AgentMode.AUTONOMOUS.value == "auto"
        assert AgentMode.SANDBOX.value == "sandbox"

    def test_mode_count(self):
        assert len(AgentMode) == 4


class TestModeConfig:
    def test_safe_config(self):
        assert SAFE_CONFIG.require_confirmation is True
        assert SAFE_CONFIG.allow_code_exec is False
        assert SAFE_CONFIG.allow_browser is False
        assert SAFE_CONFIG.allow_agent_spawn is False
        assert SAFE_CONFIG.allow_file_delete is False

    def test_balanced_config(self):
        assert BALANCED_CONFIG.require_confirmation is False
        assert BALANCED_CONFIG.allow_code_exec is True
        assert BALANCED_CONFIG.allow_agent_spawn is False

    def test_autonomous_config(self):
        assert AUTONOMOUS_CONFIG.require_confirmation is False
        assert AUTONOMOUS_CONFIG.allow_code_exec is True
        assert AUTONOMOUS_CONFIG.allow_agent_spawn is True
        assert AUTONOMOUS_CONFIG.allow_browser is True

    def test_sandbox_config(self):
        assert SANDBOX_CONFIG.require_confirmation is True
        assert SANDBOX_CONFIG.allow_network is False
        assert SANDBOX_CONFIG.allow_file_delete is False
        assert SANDBOX_CONFIG.allow_agent_spawn is False

    def test_config_has_name(self):
        assert SAFE_CONFIG.name == AgentMode.SAFE
        assert BALANCED_CONFIG.name == AgentMode.BALANCED


class TestModeEngine:
    def setup_method(self):
        self.engine = ModeEngine()

    def test_default_mode(self):
        current = self.engine.get_current_mode()
        assert current == AgentMode.BALANCED

    def test_set_mode(self):
        self.engine.set_mode(AgentMode.SAFE)
        assert self.engine.get_current_mode() == AgentMode.SAFE

    def test_set_mode_autonomous(self):
        self.engine.set_mode(AgentMode.AUTONOMOUS)
        assert self.engine.get_current_mode() == AgentMode.AUTONOMOUS

    def test_require_approval_safe(self):
        self.engine.set_mode(AgentMode.SAFE)
        assert self.engine.require_approval_for("execute_code") is True

    def test_require_approval_autonomous(self):
        self.engine.set_mode(AgentMode.AUTONOMOUS)
        assert self.engine.require_approval_for("execute_code") is False

    def test_list_modes(self):
        modes = self.engine.list_modes()
        assert len(modes) == 4
        assert all(isinstance(m, dict) for m in modes)

    def test_get_status(self):
        status = self.engine.get_status()
        assert "current_mode" in status
        assert "config" in status
