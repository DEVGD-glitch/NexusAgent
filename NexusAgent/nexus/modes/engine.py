"""
NEXUS Mode Engine — Thread-safe singleton that manages agent operational mode.

Provides runtime switching between modes, tool-level permission checks,
confirmation requirements, and emits ``mode_changed`` events via the
NEXUS event broadcaster so subscribers (frontend, audit, hooks) can react.

Usage:
    from nexus.modes import get_mode_engine, AgentMode

    engine = get_mode_engine()

    # Check if a tool is allowed in the current mode
    allowed, reason = engine.check_tool_allowed("execute_code")

    # Check if a tool requires human approval
    needs_approval = engine.require_approval_for("delete_file")

    # Switch modes at runtime
    config = engine.set_mode(AgentMode.SAFE)
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from nexus.modes.modes import AgentMode, ModeConfig, get_config_for_mode, _MODE_CONFIG_MAP

logger = logging.getLogger(__name__)


class ModeEngine:
    """Thread-safe singleton that manages the current agent operational mode.

    The engine holds the current ``AgentMode`` and its associated
    ``ModeConfig``, and provides permission-checking methods that the
    tool executor and orchestrator consult before running any action.

    Safe to call from any thread — internal state is protected by a
    ``threading.Lock``.
    """

    def __init__(self, initial_mode: AgentMode = AgentMode.BALANCED) -> None:
        """Initialise the mode engine.

        Args:
            initial_mode: The mode to start in (default ``BALANCED``).
        """
        self._lock = threading.Lock()
        self._current_mode: AgentMode = initial_mode
        self._config: ModeConfig = get_config_for_mode(initial_mode)

        logger.info(
            "[ModeEngine] Initialised with mode=%s config=%s",
            initial_mode.value,
            self._config.description,
        )

    # ── Public query methods ──────────────────────────────────────────

    def get_current_mode(self) -> AgentMode:
        """Return the current :class:`AgentMode` enum value.

        Thread-safe (read under lock).
        """
        with self._lock:
            return self._current_mode

    def get_config(self) -> ModeConfig:
        """Return the :class:`ModeConfig` for the **current** mode.

        Thread-safe (read under lock).
        """
        with self._lock:
            return self._config

    def get_config_for(self, mode: AgentMode) -> ModeConfig:
        """Return the :class:`ModeConfig` for *any* mode without changing it.

        Thread-safe (read-only; no lock needed for the lookup itself).
        """
        return get_config_for_mode(mode)

    # ── Mode switching ────────────────────────────────────────────────

    def set_mode(self, mode: AgentMode) -> ModeConfig:
        """Switch the agent to a new operational mode.

        Steps:
          1. Validate that *mode* is a known ``AgentMode``.
          2. Look up the predefined ``ModeConfig``.
          3. Atomically swap the current mode and config under lock.
          4. Log the change.
          5. Emit a ``mode_changed`` event via the NEXUS broadcaster.

        Args:
            mode: The target mode to switch to.

        Returns:
            The new :class:`ModeConfig` now active.

        Raises:
            ValueError: If *mode* is not a valid ``AgentMode``.
        """
        if not isinstance(mode, AgentMode):
            raise ValueError(
                f"Invalid mode '{mode}'. Must be one of {[m.value for m in AgentMode]}"
            )

        try:
            new_config = get_config_for_mode(mode)
        except KeyError:
            raise ValueError(
                f"Unknown mode '{mode.value}'. Must be one of {[m.value for m in AgentMode]}"
            )

        old_mode: AgentMode | None = None

        with self._lock:
            old_mode = self._current_mode
            self._current_mode = mode
            self._config = new_config

        logger.info(
            "[ModeEngine] Mode changed: %s → %s  (%s)",
            old_mode.value if old_mode else "N/A",
            mode.value,
            new_config.description,
        )

        # Emit event asynchronously via the event broadcaster
        self._emit_mode_changed(old_mode, mode, new_config)

        return new_config

    # ── Permission checks ─────────────────────────────────────────────

    def require_approval_for(self, tool_name: str) -> bool:
        """Check whether *tool_name* requires human approval in the current mode.

        Returns ``True`` if the tool's name matches any entry in
        ``require_human_approval``, or if ``require_human_approval``
        contains the wildcard ``"*"`` (meaning ALL tools need approval).

        Thread-safe (read under lock).
        """
        with self._lock:
            approval_list = self._config.require_human_approval

        if "*" in approval_list:
            return True
        return tool_name in approval_list

    def check_tool_allowed(self, tool_name: str) -> tuple[bool, str]:
        """Determine whether *tool_name* is permitted in the current mode.

        Evaluates restrictions on network access, file writes, file
        deletes, code execution, browser automation, and agent spawning
        based on the tool name.

        Args:
            tool_name: The short name of the tool (e.g. ``"execute_code"``,
                ``"delete_file"``, ``"browser_navigate"``).

        Returns:
            A tuple of ``(allowed: bool, reason: str)``.  If allowed,
            reason is an empty string; otherwise it describes the
            restriction that was violated.
        """
        with self._lock:
            config = self._config

        # Map tool name patterns to config attributes and descriptive labels
        restrictions: list[tuple[tuple[str, ...], str, bool]] = [
            # (tool_name_prefixes, config_attr, allowed_value)
            (("network", "http", "https", "fetch", "curl", "wget", "requests"), "allow_network", config.allow_network),
            (("write_file", "create_file", "write", "mkdir", "create_directory"), "allow_file_write", config.allow_file_write),
            (("delete", "remove", "rm", "unlink", "delete_file", "delete_dir"), "allow_file_delete", config.allow_file_delete),
            (("execute", "run", "exec", "shell", "python", "bash", "code"), "allow_code_exec", config.allow_code_exec),
            (("browser", "chrome", "playwright", "puppeteer", "navigate", "screenshot"), "allow_browser", config.allow_browser),
            (("spawn", "agent_spawn", "sub_agent", "fork"), "allow_agent_spawn", config.allow_agent_spawn),
        ]

        for prefixes, attr_name, is_allowed in restrictions:
            if tool_name.startswith(prefixes):
                if not is_allowed:
                    return (
                        False,
                        f"Tool '{tool_name}' requires '{attr_name}=True', "
                        f"but current mode '{config.name.value}' has it disabled. "
                        f"Switch to a higher-permission mode (balanced or auto).",
                    )

        return (True, "")

    def list_modes(self) -> list[dict[str, Any]]:
        """Return a list of all available modes with their config and an
        ``is_current`` flag.

        Thread-safe (read under lock for the current-mode comparison).
        """
        with self._lock:
            current_mode = self._current_mode

        result = []
        for mode in AgentMode:
            cfg = get_config_for_mode(mode)
            entry = cfg.to_dict()
            entry["is_current"] = mode == current_mode
            result.append(entry)

        return result

    # ── Internal helpers ──────────────────────────────────────────────

    @staticmethod
    def _emit_mode_changed(
        old_mode: AgentMode | None,
        new_mode: AgentMode,
        config: ModeConfig,
    ) -> None:
        """Emit a ``mode_changed`` event via the global event broadcaster.

        This is a best-effort fire-and-forget call.  If the broadcaster
        is not available (e.g. during early startup), the event is
        silently dropped.
        """
        try:
            from nexus.core.events import get_broadcaster

            broadcaster = get_broadcaster()
            broadcaster.broadcast_sync(
                "mode_changed",
                {
                    "old_mode": old_mode.value if old_mode else None,
                    "new_mode": new_mode.value,
                    "description": config.description,
                    "config": config.to_dict(),
                },
            )
        except Exception:
            logger.debug("[ModeEngine] Failed to emit mode_changed event", exc_info=True)

    # ── Status introspection ──────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """Return a snapshot of engine status for monitoring and health checks."""
        with self._lock:
            return {
                "current_mode": self._current_mode.value,
                "description": self._config.description,
                "config": self._config.to_dict(),
                "available_modes": [m.value for m in AgentMode],
            }


# ═══════════════════════════════════════════════════════════════════
# Global singleton accessor
# ═══════════════════════════════════════════════════════════════════

_engine: ModeEngine | None = None
_engine_lock: threading.Lock = threading.Lock()


def get_mode_engine(initial_mode: AgentMode = AgentMode.BALANCED) -> ModeEngine:
    """Return the global ``ModeEngine`` singleton.

    The engine is created on first call with the given *initial_mode*.
    Subsequent calls ignore *initial_mode* and return the already-
    created instance.

    Thread-safe: creation and access are serialised via ``_engine_lock``.

    Args:
        initial_mode: Only used when the singleton is first created.
            Ignored on subsequent calls.

    Returns:
        The shared ``ModeEngine`` instance.
    """
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:  # Double-checked locking
                _engine = ModeEngine(initial_mode=initial_mode)
                logger.info(
                    "[ModeEngine] Singleton created with mode=%s",
                    initial_mode.value,
                )
    return _engine
