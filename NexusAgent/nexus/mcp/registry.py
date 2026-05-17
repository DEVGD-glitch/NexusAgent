"""
NEXUS MCP Marketplace — Thread-safe singleton registry.

Manages the lifecycle of installed MCP servers: register, lookup,
enable/disable, cost tracking, and built-in discovery.
"""

from __future__ import annotations

import asyncio
import logging
import shlex
import shutil
import subprocess  # nosec: intentional for controlled child process launch
import threading
from typing import Any, Optional

from nexus.mcp.models import MCPDefinition, MCPStatus, MCPTrustLevel

logger = logging.getLogger(__name__)


# ── Registry Exceptions ──────────────────────────────────────────────


class MCPRegistryError(Exception):
    """Base exception for MCP registry operations."""


class MCPNotFoundError(MCPRegistryError):
    """Raised when an MCP id is not registered."""


class MCPInstallError(MCPRegistryError):
    """Raised when installation of an MCP server fails."""


# ── Singleton Registry ──────────────────────────────────────────────


class MCPRegistry:
    """Thread-safe singleton registry for external MCP servers.

    Usage::

        registry = MCPRegistry.get_instance()
        registry.register(mcp_def)
        mcp = registry.get("web-search")
    """

    _instance: Optional["MCPRegistry"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        if not getattr(self, "_initialised", False):
            self._mcps: dict[str, MCPDefinition] = {}
            self._rw_lock = threading.Lock()
            self._initialised = True
            logger.info("MCPRegistry initialised")

    # ── Singleton access ─────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "MCPRegistry":
        """Return the singleton registry (create if necessary)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── Registration ──────────────────────────────────────────────

    def register(self, mcp: MCPDefinition) -> None:
        """Register an MCP definition. Overwrites if id exists."""
        with self._rw_lock:
            mcp.updated_at = asyncio.get_event_loop().time() if self._has_loop() else mcp.updated_at  # type: ignore[attr-defined]
            self._mcps[mcp.id] = mcp
            logger.info(
                "MCP registered: %s (version=%s, trust=%s, status=%s)",
                mcp.id,
                mcp.version,
                mcp.trust_level.value,
                mcp.status.value,
            )

    def unregister(self, mcp_id: str) -> None:
        """Remove an MCP from the registry.

        Raises MCPNotFoundError if the id does not exist.
        """
        with self._rw_lock:
            if mcp_id not in self._mcps:
                raise MCPNotFoundError(f"MCP '{mcp_id}' is not registered")
            del self._mcps[mcp_id]
            logger.info("MCP unregistered: %s", mcp_id)

    # ── Lookup ────────────────────────────────────────────────────

    def get(self, mcp_id: str) -> Optional[MCPDefinition]:
        """Return an MCP by id, or None."""
        with self._rw_lock:
            return self._mcps.get(mcp_id)

    def list_mcp(self, status: Optional[MCPStatus] = None) -> list[MCPDefinition]:
        """Return all MCPs, optionally filtered by status."""
        with self._rw_lock:
            mcps = list(self._mcps.values())
        if status is not None:
            mcps = [m for m in mcps if m.status == status]
        return mcps

    def get_enabled(self) -> list[MCPDefinition]:
        """Return only enabled MCPs (status == ENABLED)."""
        return self.list_mcp(status=MCPStatus.ENABLED)

    # ── Enable / Disable ─────────────────────────────────────────

    def enable(self, mcp_id: str) -> None:
        """Set an MCP's status to ENABLED.

        Raises MCPNotFoundError if the id does not exist.
        """
        with self._rw_lock:
            mcp = self._mcps.get(mcp_id)
            if mcp is None:
                raise MCPNotFoundError(f"MCP '{mcp_id}' is not registered")
            mcp.status = MCPStatus.ENABLED
            mcp.updated_at = self._now()
            logger.info("MCP enabled: %s", mcp_id)

    def disable(self, mcp_id: str) -> None:
        """Set an MCP's status to DISABLED.

        Raises MCPNotFoundError if the id does not exist.
        """
        with self._rw_lock:
            mcp = self._mcps.get(mcp_id)
            if mcp is None:
                raise MCPNotFoundError(f"MCP '{mcp_id}' is not registered")
            mcp.status = MCPStatus.DISABLED
            mcp.updated_at = self._now()
            logger.info("MCP disabled: %s", mcp_id)

    # ── Token Cost ────────────────────────────────────────────────

    def get_token_cost(self, mcp_id: str) -> float:
        """Return the estimated token cost for an MCP.

        Raises MCPNotFoundError if the id does not exist.
        """
        mcp = self.get(mcp_id)
        if mcp is None:
            raise MCPNotFoundError(f"MCP '{mcp_id}' is not registered")
        return mcp.token_cost_estimate

    def set_token_cost(self, mcp_id: str, cost: float) -> None:
        """Update the estimated token cost for an MCP."""
        with self._rw_lock:
            mcp = self._mcps.get(mcp_id)
            if mcp is None:
                raise MCPNotFoundError(f"MCP '{mcp_id}' is not registered")
            mcp.token_cost_estimate = max(0.0, cost)

    # ── Install helpers ───────────────────────────────────────────

    def install_from_url(self, url: str) -> MCPDefinition:
        """Install an MCP server from a remote URL.

        This is a **declarative** stub — the actual protocol for
        fetching and configuring remote MCPs is delegated to
        ``MCPMarketplace.install()``.  Here we simply create a
        placeholder definition with status=INSTALLED.

        Raises MCPInstallError if the URL is malformed.
        """
        import re

        # Basic URL validation
        if not re.match(r"^https?://", url):
            raise MCPInstallError(f"Invalid MCP source URL: {url}")

        # Extract a reasonable id from the URL
        mcp_id = re.sub(r"[^a-zA-Z0-9_-]", "_", url.split("/")[-1].split("?")[0])
        if not mcp_id:
            mcp_id = f"mcp_{hash(url) % 10**6}"

        mcp = MCPDefinition(
            id=mcp_id,
            name=mcp_id.replace("_", " ").title(),
            description=f"MCP server installed from {url}",
            command="",
            status=MCPStatus.INSTALLED,
            trust_level=MCPTrustLevel.UNKNOWN,
            install_source="url",
            repository=url,
        )
        self.register(mcp)
        logger.info("MCP installed from URL: %s (id=%s)", url, mcp_id)
        return mcp

    def discover_builtins(self) -> list[MCPDefinition]:
        """Return the list of known built-in MCP definitions.

        These are well-known, pre-configured MCP servers that ship
        with NEXUS.  They are automatically registered on first call.
        """
        builtins = _BUILTIN_MCP_DEFINITIONS()
        for b in builtins:
            if b.id not in self._mcps:
                self.register(b)
        return builtins

    # ── Utility ───────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return aggregate statistics about registered MCPs."""
        with self._rw_lock:
            total = len(self._mcps)
            by_status: dict[str, int] = {}
            by_trust: dict[str, int] = {}
            for m in self._mcps.values():
                by_status[m.status.value] = by_status.get(m.status.value, 0) + 1
                by_trust[m.trust_level.value] = by_trust.get(m.trust_level.value, 0) + 1
        return {
            "total": total,
            "by_status": by_status,
            "by_trust": by_trust,
        }

    # ── Internal helpers ──────────────────────────────────────────

    @staticmethod
    def _now() -> float:
        try:
            return asyncio.get_event_loop().time()
        except RuntimeError:
            import time
            return time.time()

    @staticmethod
    def _has_loop() -> bool:
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            return False


# ── Module-level convenience ────────────────────────────────────────


def get_mcp_registry() -> MCPRegistry:
    """Return the singleton MCPRegistry."""
    return MCPRegistry.get_instance()


# ═════════════════════════════════════════════════════════════════════
# Built-in MCP definitions
# ═════════════════════════════════════════════════════════════════════


def _BUILTIN_MCP_DEFINITIONS() -> list[MCPDefinition]:
    """Factory for well-known built-in MCP servers.

    Each entry represents an external service that NEXUS can delegate
    to.  Users must install the required packages / API keys separately.
    """
    return [
        MCPDefinition(
            id="web-search",
            name="Web Search",
            description="Real-time web search via SerpAPI / Brave / Tavily",
            version="1.0.0",
            author="NEXUS Team",
            repository="https://github.com/nexus/mcp-web-search",
            command="python",
            args=["-m", "nexus.mcp_servers.web_search"],
            env={"SEARCH_PROVIDER": "tavily"},
            status=MCPStatus.ENABLED,
            trust_level=MCPTrustLevel.HIGH,
            token_cost_estimate=0.002,
            permissions=["network"],
            install_source="builtin",
            tags=["search", "web", "builtin"],
        ),
        MCPDefinition(
            id="web-scrape",
            name="Web Scraper",
            description="Extract clean markdown from any web page",
            version="1.0.0",
            author="NEXUS Team",
            repository="https://github.com/nexus/mcp-web-scrape",
            command="python",
            args=["-m", "nexus.mcp_servers.web_scrape"],
            env={},
            status=MCPStatus.ENABLED,
            trust_level=MCPTrustLevel.HIGH,
            token_cost_estimate=0.001,
            permissions=["network"],
            install_source="builtin",
            tags=["scrape", "web", "builtin"],
        ),
        MCPDefinition(
            id="github",
            name="GitHub API",
            description="Interact with GitHub: repos, issues, PRs, gists",
            version="1.0.0",
            author="NEXUS Team",
            repository="https://github.com/nexus/mcp-github",
            command="python",
            args=["-m", "nexus.mcp_servers.github"],
            env={"GITHUB_TOKEN": ""},
            status=MCPStatus.DISABLED,
            trust_level=MCPTrustLevel.HIGH,
            token_cost_estimate=0.005,
            permissions=["network"],
            install_source="builtin",
            tags=["github", "dev", "builtin"],
        ),
        MCPDefinition(
            id="slack",
            name="Slack",
            description="Read and send messages in Slack workspaces",
            version="1.0.0",
            author="NEXUS Team",
            repository="https://github.com/nexus/mcp-slack",
            command="python",
            args=["-m", "nexus.mcp_servers.slack"],
            env={"SLACK_BOT_TOKEN": "", "SLACK_APP_TOKEN": ""},
            status=MCPStatus.DISABLED,
            trust_level=MCPTrustLevel.MEDIUM,
            token_cost_estimate=0.003,
            permissions=["network"],
            install_source="builtin",
            tags=["slack", "communication", "builtin"],
        ),
        MCPDefinition(
            id="jira",
            name="Jira",
            description="Create and query Jira issues, sprints, projects",
            version="1.0.0",
            author="NEXUS Team",
            repository="https://github.com/nexus/mcp-jira",
            command="python",
            args=["-m", "nexus.mcp_servers.jira"],
            env={"JIRA_URL": "", "JIRA_API_TOKEN": ""},
            status=MCPStatus.DISABLED,
            trust_level=MCPTrustLevel.MEDIUM,
            token_cost_estimate=0.003,
            permissions=["network"],
            install_source="builtin",
            tags=["jira", "project-management", "builtin"],
        ),
        MCPDefinition(
            id="notion",
            name="Notion",
            description="Read and write Notion pages, databases, comments",
            version="1.0.0",
            author="NEXUS Team",
            repository="https://github.com/nexus/mcp-notion",
            command="python",
            args=["-m", "nexus.mcp_servers.notion"],
            env={"NOTION_TOKEN": ""},
            status=MCPStatus.DISABLED,
            trust_level=MCPTrustLevel.MEDIUM,
            token_cost_estimate=0.003,
            permissions=["network"],
            install_source="builtin",
            tags=["notion", "knowledge", "builtin"],
        ),
        MCPDefinition(
            id="discord",
            name="Discord",
            description="Send and read messages in Discord channels",
            version="1.0.0",
            author="NEXUS Team",
            repository="https://github.com/nexus/mcp-discord",
            command="python",
            args=["-m", "nexus.mcp_servers.discord"],
            env={"DISCORD_BOT_TOKEN": ""},
            status=MCPStatus.DISABLED,
            trust_level=MCPTrustLevel.MEDIUM,
            token_cost_estimate=0.002,
            permissions=["network"],
            install_source="builtin",
            tags=["discord", "communication", "builtin"],
        ),
        MCPDefinition(
            id="filesystem",
            name="Filesystem",
            description="Read, write, search local files (sandboxed path)",
            version="1.0.0",
            author="NEXUS Team",
            repository="https://github.com/nexus/mcp-filesystem",
            command="python",
            args=["-m", "nexus.mcp_servers.filesystem"],
            env={"ALLOWED_DIRS": "./nexus_data"},
            status=MCPStatus.ENABLED,
            trust_level=MCPTrustLevel.HIGH,
            token_cost_estimate=0.0005,
            permissions=["filesystem:read", "filesystem:write"],
            install_source="builtin",
            tags=["filesystem", "builtin"],
        ),
        MCPDefinition(
            id="memory",
            name="Memory Store",
            description="Vector memory via ChromaDB — search, store, delete",
            version="1.0.0",
            author="NEXUS Team",
            repository="https://github.com/nexus/mcp-memory",
            command="python",
            args=["-m", "nexus.mcp_servers.memory"],
            env={},
            status=MCPStatus.ENABLED,
            trust_level=MCPTrustLevel.VERIFIED,
            token_cost_estimate=0.0005,
            permissions=[],
            install_source="builtin",
            tags=["memory", "vector", "builtin"],
        ),
    ]
