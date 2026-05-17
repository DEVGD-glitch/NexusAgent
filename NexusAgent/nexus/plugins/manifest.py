"""
NEXUS Plugin Manifest — Data models and base class for all plugins.

Defines the contract every NEXUS plugin must follow:
  - PluginManifest: metadata and capability declaration
  - PluginBase: abstract interface every plugin implements
  - Enums for scope, permission, and status
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PluginScope(str, Enum):
    """The scope at which a plugin operates within NEXUS."""

    GLOBAL = "global"
    """Plugin is available across the entire NEXUS instance."""

    WORKSPACE = "workspace"
    """Plugin is scoped to a specific workspace/project."""

    SESSION = "session"
    """Plugin is scoped to a single conversation session."""

    AGENT = "agent"
    """Plugin is tied to a specific agent type."""


class PluginPermission(str, Enum):
    """Permissions a plugin can request. Each grants access to a specific capability."""

    FILESYSTEM_READ = "filesystem_read"
    """Read files from the local filesystem."""

    FILESYSTEM_WRITE = "filesystem_write"
    """Create, modify, or delete files on the local filesystem."""

    NETWORK = "network"
    """Make outbound HTTP/network requests."""

    SHELL = "shell"
    """Execute shell commands on the host system."""

    BROWSER = "browser"
    """Control browser automation sessions."""

    CLIPBOARD = "clipboard"
    """Read or write the system clipboard."""

    MICROPHONE = "microphone"
    """Access microphone input."""

    CAMERA = "camera"
    """Access camera input."""

    ADMIN = "admin"
    """Elevated privileges — grants all other permissions implicitly."""


class PluginStatus(str, Enum):
    """The lifecycle status of a plugin."""

    INSTALLED = "installed"
    """Plugin is present on disk but not yet registered."""

    ENABLED = "enabled"
    """Plugin is registered, loaded, initialized, and actively running."""

    DISABLED = "disabled"
    """Plugin is registered but not loaded / initialized."""

    ERROR = "error"
    """Plugin failed to load or encountered a runtime error."""


class PluginManifest(BaseModel):
    """Metadata and capability declaration for a NEXUS plugin.

    This file is read from ``plugin.json`` or ``plugin.yaml`` inside the
    plugin directory. It tells the engine what the plugin provides and
    what permissions it requires.
    """

    id: str
    """Unique identifier for this plugin (e.g. ``nexus-tools-web-search``)."""

    name: str
    """Human-readable plugin name (e.g. ``Web Search Tools``)."""

    version: str
    """Semantic version string (e.g. ``1.2.0``)."""

    author: str = "NEXUS Team"
    """Author or organization that created the plugin."""

    description: str = ""
    """Short description of what the plugin does."""

    hooks: list[str] = []
    """List of lifecycle / event hook identifiers this plugin listens for."""

    tools: list[str] = []
    """List of tool names this plugin exposes to the agent."""

    mcps: list[str] = []
    """List of MCP (Model Context Protocol) tool names this plugin provides."""

    permissions: list[PluginPermission] = []
    """List of :class:`PluginPermission` values the plugin requires."""

    scopes: list[PluginScope] = []
    """List of :class:`PluginScope` values this plugin is valid for."""

    ui_components: list[str] = Field(default_factory=list, alias="ui")
    """List of UI component identifiers this plugin contributes."""

    dependencies: list[str] = []
    """List of other plugin IDs this plugin depends on."""

    entry_point: str = ""
    """Python import path in ``module:ClassName`` format (e.g. ``web_search.plugin:WebSearchPlugin``)."""

    model_config = {"populate_by_name": True}


class PluginBase(ABC):
    """Abstract base class that every NEXUS plugin must subclass.

    Subclasses **must** define :meth:`initialize` and :meth:`shutdown`.
    The :attr:`manifest` attribute is injected by the engine after
    instantiation so it does not need to be set in ``__init__``.
    """

    manifest: PluginManifest
    """The :class:`PluginManifest` that describes this plugin. Set by the engine."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the plugin after it has been loaded.

        This is where plugins should set up connections, load resources,
        register hooks, or perform any startup tasks.

        Raises:
            PluginError: If the plugin cannot initialize successfully.
        """

    @abstractmethod
    async def shutdown(self) -> None:
        """Shut down the plugin gracefully.

        This is where plugins should release resources, close connections,
        flush data, and unregister hooks. It **must not** raise exceptions
        that would block the engine shutdown sequence.
        """
