"""
NEXUS Agent Modes — Enums, configuration dataclasses, and predefined profiles.

Defines the four operational modes that govern agent behaviour:
  - SAFE:      Maximum safety — confirms every action
  - BALANCED:  Semi-automatic with safety guardrails (default)
  - AUTONOMOUS: Advanced autonomous operation
  - SANDBOX:   Fully isolated, no network or file writes

Each mode carries a ModeConfig that controls tool permissions,
concurrency limits, confirmation requirements, and audit verbosity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentMode(str, Enum):
    """Enum of all operational modes for the NEXUS agent.

    Each value maps to a predefined ModeConfig that controls the
    agent's autonomy level and capability restrictions.
    """

    SAFE = "safe"
    """Confirm every action — maximum safety, no code execution."""

    BALANCED = "balanced"
    """Semi-automatic with safety guardrails (default)."""

    AUTONOMOUS = "auto"
    """Advanced autonomy — spawns agents, executes code freely."""

    SANDBOX = "sandbox"
    """Fully isolated — no network, no file writes, no deletes."""


@dataclass
class ModeConfig:
    """Configuration profile for an agent operational mode.

    Controls tool permissions, concurrency, confirmation requirements,
    and audit verbosity.  Predefined instances are exported from this
    module for the four standard modes.

    Attributes:
        name: The mode this config belongs to.
        description: Human-readable description.
        require_confirmation: If True, every tool call requires user
            confirmation before execution.
        require_human_approval: List of tool names that must be approved
            before execution.  ``["*"]`` means ALL tools.
        max_concurrent_tools: Maximum number of tools that can execute
            in parallel.
        allow_network: Whether outbound network requests are permitted.
        allow_file_write: Whether file / directory creation is permitted.
        allow_file_delete: Whether file / directory deletion is permitted.
        allow_code_exec: Whether arbitrary code execution is permitted.
        allow_browser: Whether browser automation is permitted.
        allow_agent_spawn: Whether spawning sub-agents is permitted.
        log_level: Python log level for this mode.
        audit_level: Audit trail verbosity level.
        max_tokens_per_call: Maximum LLM tokens per inference call.
        timeout_seconds: Maximum wall-clock time for any single operation.
    """

    name: AgentMode
    description: str
    require_confirmation: bool = True
    require_human_approval: list[str] = field(default_factory=list)
    max_concurrent_tools: int = 1
    allow_network: bool = True
    allow_file_write: bool = True
    allow_file_delete: bool = False
    allow_code_exec: bool = True
    allow_browser: bool = False
    allow_agent_spawn: bool = False
    log_level: str = "INFO"
    audit_level: str = "INFO"
    max_tokens_per_call: int = 4096
    timeout_seconds: int = 120

    def to_dict(self) -> dict[str, Any]:
        """Return config as a plain dict (JSON-serialisable)."""
        return {
            "name": self.name.value,
            "description": self.description,
            "require_confirmation": self.require_confirmation,
            "require_human_approval": list(self.require_human_approval),
            "max_concurrent_tools": self.max_concurrent_tools,
            "allow_network": self.allow_network,
            "allow_file_write": self.allow_file_write,
            "allow_file_delete": self.allow_file_delete,
            "allow_code_exec": self.allow_code_exec,
            "allow_browser": self.allow_browser,
            "allow_agent_spawn": self.allow_agent_spawn,
            "log_level": self.log_level,
            "audit_level": self.audit_level,
            "max_tokens_per_call": self.max_tokens_per_call,
            "timeout_seconds": self.timeout_seconds,
        }


# ═══════════════════════════════════════════════════════════════════
# Predefined mode configurations
# ═══════════════════════════════════════════════════════════════════

SAFE_CONFIG = ModeConfig(
    name=AgentMode.SAFE,
    description="Maximum safety — confirms every action before execution. "
    "No code execution, no browser, no agent spawning.",
    require_confirmation=True,
    require_human_approval=["*"],
    max_concurrent_tools=1,
    allow_file_delete=False,
    allow_code_exec=False,
    allow_browser=False,
    allow_agent_spawn=False,
    log_level="DEBUG",
    audit_level="DEBUG",
)

BALANCED_CONFIG = ModeConfig(
    name=AgentMode.BALANCED,
    description="Semi-automatic with safety guardrails. "
    "Requires approval for destructive operations (delete, code exec, deploy, agent spawn).",
    require_confirmation=False,
    require_human_approval=[
        "delete_file",
        "execute_code",
        "deploy",
        "spawn_agent",
    ],
    max_concurrent_tools=3,
    allow_file_delete=True,
    allow_code_exec=True,
    allow_browser=True,
    allow_agent_spawn=False,
)

AUTONOMOUS_CONFIG = ModeConfig(
    name=AgentMode.AUTONOMOUS,
    description="Advanced autonomous operation. "
    "Full capabilities with only deployment requiring human approval.",
    require_confirmation=False,
    require_human_approval=["deploy"],
    max_concurrent_tools=10,
    allow_file_delete=True,
    allow_code_exec=True,
    allow_browser=True,
    allow_agent_spawn=True,
)

SANDBOX_CONFIG = ModeConfig(
    name=AgentMode.SANDBOX,
    description="Fully isolated environment. "
    "No network access, no file writes or deletes. Code execution permitted but contained. "
    "Extended timeout for safe exploration.",
    require_confirmation=True,
    require_human_approval=["*"],
    max_concurrent_tools=1,
    allow_network=False,
    allow_file_write=False,
    allow_file_delete=False,
    allow_code_exec=True,
    allow_browser=False,
    allow_agent_spawn=False,
    timeout_seconds=300,
)

# Lookup mapping mode enum → config
_MODE_CONFIG_MAP: dict[AgentMode, ModeConfig] = {
    AgentMode.SAFE: SAFE_CONFIG,
    AgentMode.BALANCED: BALANCED_CONFIG,
    AgentMode.AUTONOMOUS: AUTONOMOUS_CONFIG,
    AgentMode.SANDBOX: SANDBOX_CONFIG,
}


def get_config_for_mode(mode: AgentMode) -> ModeConfig:
    """Return the predefined ``ModeConfig`` for the given ``AgentMode``.

    Raises ``KeyError`` if the mode is unknown (should never happen with
    the enum).
    """
    return _MODE_CONFIG_MAP[mode]
