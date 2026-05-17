"""
NEXUS Modes System — Agent operational modes and engine.

Controls agent autonomy level, safety guardrails, and capability
restrictions through four distinct modes:
  - SAFE:      Maximum safety — confirms every action
  - BALANCED:  Semi-automatic with safety guardrails (default)
  - AUTONOMOUS: Advanced autonomous operation
  - SANDBOX:   Fully isolated, no network or file writes

Usage:
    from nexus.modes import get_mode_engine, AgentMode

    engine = get_mode_engine()
    current = engine.get_current_mode()
    config = engine.get_config()
    allowed, reason = engine.check_tool_allowed("delete_file")
"""

from __future__ import annotations

from nexus.modes.modes import AgentMode, ModeConfig
from nexus.modes.modes import SAFE_CONFIG, BALANCED_CONFIG, AUTONOMOUS_CONFIG, SANDBOX_CONFIG
from nexus.modes.engine import ModeEngine, get_mode_engine

__all__ = [
    "ModeEngine",
    "AgentMode",
    "ModeConfig",
    "get_mode_engine",
    "SAFE_CONFIG",
    "BALANCED_CONFIG",
    "AUTONOMOUS_CONFIG",
    "SANDBOX_CONFIG",
]
