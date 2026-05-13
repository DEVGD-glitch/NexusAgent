"""
NEXUS Permissions — User-controlled permission system.

Two modes:
  - auto: Actions proceed freely EXCEPT for dangerous ones (always confirmed)
  - confirm: Every significant action requires user confirmation

Dangerous actions (ALWAYS confirmed even in auto mode):
  - File deletion
  - File overwrite in system directories
  - Code execution
  - Shell command execution
  - Writing outside the workspace
  - Sending data to external URLs
"""

from __future__ import annotations

import logging
import os
import platform
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class PermissionMode(str, Enum):
    AUTO = "auto"
    CONFIRM = "confirm"


class PermissionAction(str, Enum):
    """Actions that may require permission."""
    DELETE_FILE = "delete_file"
    WRITE_FILE_SYSTEM = "write_file_system"
    EXECUTE_CODE = "execute_code"
    EXECUTE_SHELL = "execute_shell"
    WRITE_OUTSIDE_WORKSPACE = "write_outside_workspace"
    NETWORK_REQUEST = "network_request"
    INSTALL_PACKAGE = "install_package"
    RESET_MEMORY = "reset_memory"
    DELETE_MEMORY = "delete_memory"


# Actions that ALWAYS require confirmation, even in auto mode
ALWAYS_CONFIRM = frozenset({
    PermissionAction.DELETE_FILE,
    PermissionAction.EXECUTE_CODE,
    PermissionAction.EXECUTE_SHELL,
    PermissionAction.INSTALL_PACKAGE,
    PermissionAction.RESET_MEMORY,
    PermissionAction.WRITE_FILE_SYSTEM,
    PermissionAction.WRITE_OUTSIDE_WORKSPACE,
})


class PermissionRequest(BaseModel):
    """A permission request sent to the user."""
    action: PermissionAction
    description: str
    target: str = ""
    risk_level: str = "medium"  # low, medium, high
    requires_confirmation: bool = True


class PermissionResult(BaseModel):
    """Result of a permission request."""
    granted: bool
    reason: str = ""


class PermissionManager:
    """
    Manages user permissions for NEXUS actions.

    Usage:
        pm = PermissionManager(mode="auto")
        request = pm.check_permission(PermissionAction.DELETE_FILE, "/path/to/file")
        if request.requires_confirmation:
            # Show toast to user and get confirmation
            ...
    """

    def __init__(self, mode: PermissionMode = PermissionMode.AUTO):
        self.mode = mode

    def check_permission(
        self,
        action: PermissionAction,
        target: str = "",
        description: str = "",
    ) -> PermissionRequest:
        """
        Check if an action requires user confirmation.

        Args:
            action: The action being performed.
            target: Target of the action (file path, URL, etc.).
            description: Human-readable description.

        Returns:
            PermissionRequest indicating whether confirmation is needed.
        """
        # Always confirm dangerous actions
        if action in ALWAYS_CONFIRM:
            risk = self._assess_risk(action, target)
            return PermissionRequest(
                action=action,
                description=description or self._describe_action(action, target),
                target=target,
                risk_level=risk,
                requires_confirmation=True,
            )

        # In confirm mode, everything needs confirmation
        if self.mode == PermissionMode.CONFIRM:
            return PermissionRequest(
                action=action,
                description=description or self._describe_action(action, target),
                target=target,
                risk_level="low",
                requires_confirmation=True,
            )

        # In auto mode, non-dangerous actions proceed freely
        return PermissionRequest(
            action=action,
            description=description or self._describe_action(action, target),
            target=target,
            risk_level="low",
            requires_confirmation=False,
        )

    def _assess_risk(self, action: PermissionAction, target: str) -> str:
        """Assess the risk level of an action."""
        high_risk_actions = {
            PermissionAction.DELETE_FILE,
            PermissionAction.EXECUTE_SHELL,
            PermissionAction.INSTALL_PACKAGE,
            PermissionAction.RESET_MEMORY,
        }

        if action in high_risk_actions:
            return "high"

        # Check if target is a system directory (using resolve() + relative_to() to prevent symlink bypass)
        if target:
            system_dirs = self._get_system_dirs()
            target_path = Path(target).resolve()
            for sys_dir in system_dirs:
                try:
                    real_sys = Path(sys_dir).resolve()
                    target_path.relative_to(real_sys)  # raises ValueError if not contained
                    return "high"
                except (ValueError, OSError):
                    pass

        return "medium"

    def _describe_action(self, action: PermissionAction, target: str) -> str:
        """Generate a human-readable description of the action."""
        descriptions = {
            PermissionAction.DELETE_FILE: f"Supprimer le fichier : {target}",
            PermissionAction.WRITE_FILE_SYSTEM: f"Écrire dans un dossier système : {target}",
            PermissionAction.EXECUTE_CODE: f"Exécuter du code",
            PermissionAction.EXECUTE_SHELL: f"Exécuter une commande shell",
            PermissionAction.WRITE_OUTSIDE_WORKSPACE: f"Écrire en dehors du workspace : {target}",
            PermissionAction.NETWORK_REQUEST: f"Envoyer des données vers : {target}",
            PermissionAction.INSTALL_PACKAGE: f"Installer un package Python",
            PermissionAction.RESET_MEMORY: f"Réinitialiser un namespace mémoire",
            PermissionAction.DELETE_MEMORY: f"Supprimer un document mémoire",
        }
        return descriptions.get(action, f"Action : {action.value}")

    @staticmethod
    def _get_system_dirs() -> list[str]:
        """Get system directories that should never be written to without confirmation."""
        if platform.system() == "Windows":
            return [
                os.environ.get("SystemRoot", r"C:\Windows"),
                r"C:\Program Files",
                r"C:\Program Files (x86)",
                r"C:\ProgramData",
            ]
        else:
            return ["/usr", "/etc", "/bin", "/sbin", "/var", "/sys", "/proc"]
