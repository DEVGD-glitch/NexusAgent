"""
NEXUS Plugin System — Hierarchical exceptions.

Every plugin operation raises specific exceptions that carry
structured context for debugging, audit, and user feedback.
"""

from __future__ import annotations

from typing import Any

from nexus.core.exceptions import NexusError


class PluginError(NexusError):
    """Base exception for all plugin system errors."""

    def __init__(
        self,
        message: str,
        plugin_id: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        _details = dict(details or {})
        if plugin_id:
            _details["plugin_id"] = plugin_id
        super().__init__(message, code="PLUGIN_ERROR", details=_details)


class PluginNotFoundError(PluginError):
    """Raised when a plugin is not found in the registry or on disk."""

    def __init__(self, plugin_id: str):
        super().__init__(
            message=f"Plugin not found: {plugin_id}",
            plugin_id=plugin_id,
        )
        self.code = "PLUGIN_NOT_FOUND"


class PluginLoadError(PluginError):
    """Raised when a plugin fails to load or import."""

    def __init__(self, plugin_id: str, reason: str):
        super().__init__(
            message=f"Failed to load plugin '{plugin_id}': {reason}",
            plugin_id=plugin_id,
            details={"reason": reason},
        )
        self.code = "PLUGIN_LOAD_ERROR"


class PluginManifestError(PluginError):
    """Raised when a plugin manifest is invalid, missing, or malformed."""

    def __init__(self, plugin_id: str | None, reason: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=f"Invalid plugin manifest: {reason}",
            plugin_id=plugin_id,
            details=details,
        )
        self.code = "PLUGIN_MANIFEST_ERROR"


class PluginPermissionDenied(PluginError):
    """Raised when a plugin attempts an action without the required permission."""

    def __init__(self, plugin_id: str, permission: str, action: str = ""):
        super().__init__(
            message=f"Plugin '{plugin_id}' missing required permission: {permission}",
            plugin_id=plugin_id,
            details={"permission": permission, "action": action},
        )
        self.code = "PLUGIN_PERMISSION_DENIED"


class PluginDependencyError(PluginError):
    """Raised when a plugin's dependencies are not satisfied."""

    def __init__(self, plugin_id: str, missing_deps: list[str]):
        super().__init__(
            message=f"Plugin '{plugin_id}' missing dependencies: {missing_deps}",
            plugin_id=plugin_id,
            details={"missing_dependencies": missing_deps},
        )
        self.code = "PLUGIN_DEPENDENCY_ERROR"


class PluginRateLimitError(PluginError):
    """Raised when a plugin exceeds its rate limit."""

    def __init__(self, plugin_id: str, action: str = ""):
        super().__init__(
            message=f"Rate limit exceeded for plugin '{plugin_id}'",
            plugin_id=plugin_id,
            details={"action": action},
        )
        self.code = "PLUGIN_RATE_LIMIT_EXCEEDED"
