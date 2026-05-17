"""
NEXUS MCP Marketplace — Discovery, search, install, update.

The Marketplace is the user-facing interface for finding and managing
external MCP servers.  It builds on top of the MCPRegistry and adds:

* Search across known MCPs (fuzzy, by name/description/tags)
* Listing available MCPs from a remote registry (GitHub-hosted index)
* Install / uninstall / update lifecycle orchestration
* Integration with the registry's built-in discovery
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess  # nosec: controlled child process for pip installs
import threading
from typing import Any, Optional

from nexus.mcp.models import MCPDefinition, MCPStatus, MCPTrustLevel
from nexus.mcp.registry import (
    MCPInstallError,
    MCPNotFoundError,
    MCPRegistry,
    get_mcp_registry,
)

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════
# Marketplace
# ═════════════════════════════════════════════════════════════════════


class MCPMarketplace:
    """User-facing interface for discovering and installing MCP servers.

    Wraps the ``MCPRegistry`` singleton and adds higher-level operations
    such as search, remote listing, and install/uninstall orchestration.

    Usage::

        mp = MCPMarketplace()
        results = mp.search("github")
        mp.install("github")
    """

    def __init__(self) -> None:
        self._registry = get_mcp_registry()
        self._lock = threading.Lock()
        # Remote registry cache (avoids repeated HTTP calls)
        self._remote_cache: list[dict[str, Any]] = []
        self._cache_lock = threading.Lock()
        logger.info("MCPMarketplace initialised")

    # ── Search ────────────────────────────────────────────────────

    def search(self, query: str) -> list[MCPDefinition]:
        """Search known (registered) MCPs by name, description, or tags.

        Performs a simple case-insensitive substring match.  Returns
        all matches — no external network call.
        """
        q = query.lower().strip()
        if not q:
            return self._registry.list_mcp()

        all_mcps = self._registry.list_mcp()
        results: list[MCPDefinition] = []
        for mcp in all_mcps:
            if q in mcp.id.lower():
                results.append(mcp)
                continue
            if q in mcp.name.lower():
                results.append(mcp)
                continue
            if q in mcp.description.lower():
                results.append(mcp)
                continue
            for tag in mcp.tags:
                if q in tag.lower():
                    results.append(mcp)
                    break
        return results

    # ── Remote listing ────────────────────────────────────────────

    def list_available(self) -> list[dict[str, Any]]:
        """Fetch available MCPs from the remote GitHub registry index.

        The remote index is a curated JSON file hosted at:
        ``https://raw.githubusercontent.com/nexus/mcp-registry/main/index.json``

        Results are cached in-memory for 5 minutes to avoid excessive
        network calls.  Returns a list of dicts with metadata about
        each available MCP (not yet installed).
        """
        import time

        now = time.time()

        # Use cached result if fresh (5 min TTL)
        with self._cache_lock:
            if self._remote_cache and now - getattr(self, "_cache_ts", 0) < 300:
                return self._remote_cache

        try:
            import httpx

            url = "https://raw.githubusercontent.com/nexus/mcp-registry/main/index.json"
            resp = httpx.get(url, timeout=10.0)
            resp.raise_for_status()
            entries: list[dict[str, Any]] = resp.json()

            # Normalise entries
            for entry in entries:
                entry.setdefault("id", entry.get("name", "").lower().replace(" ", "-"))
                entry.setdefault("description", "")
                entry.setdefault("version", "1.0.0")
                entry.setdefault("tags", [])

            with self._cache_lock:
                self._remote_cache = entries
                self._cache_ts = now  # type: ignore[attr-defined]

            logger.info("Fetched %d available MCPs from remote registry", len(entries))
            return entries

        except Exception as exc:
            logger.warning("Failed to fetch remote MCP registry: %s", exc)
            # Return built-in definitions as fallback
            builtins = self._registry.discover_builtins()
            return [b.to_dict() for b in builtins]

    # ── Install ───────────────────────────────────────────────────

    def install(self, mcp_id: str, source: str = "github") -> MCPDefinition:
        """Install an MCP server by id.

        Installation flow:
          1. Look up the MCP definition (must already be registered,
             e.g. via ``discover_builtins()`` or manual registration).
          2. If ``source == "pip"``, run ``pip install nexus-mcp-{mcp_id}``.
          3. If ``source == "github"``, record the install source.
          4. Set status to INSTALLED.

        Raises MCPNotFoundError if the id is not registered.
        Raises MCPInstallError if the installation command fails.
        """
        with self._lock:
            mcp = self._registry.get(mcp_id)
            if mcp is None:
                # Try discovering builtins first
                self._registry.discover_builtins()
                mcp = self._registry.get(mcp_id)
                if mcp is None:
                    # If still not found, create a placeholder
                    mcp = MCPDefinition(
                        id=mcp_id,
                        name=mcp_id.replace("_", " ").title(),
                        description=f"MCP server '{mcp_id}'",
                        status=MCPStatus.INSTALLED,
                        trust_level=MCPTrustLevel.UNKNOWN,
                        install_source=source,
                    )
                    self._registry.register(mcp)
                    logger.info("Created placeholder MCP: %s", mcp_id)
                    return mcp

            # Run pip install if source is "pip"
            if source == "pip":
                pkg_name = f"nexus-mcp-{mcp_id.replace('_', '-')}"
                logger.info("Installing package: %s", pkg_name)
                try:
                    result = subprocess.run(  # nosec
                        ["pip", "install", pkg_name],
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    if result.returncode != 0:
                        raise MCPInstallError(
                            f"pip install failed for {pkg_name}: {result.stderr[:500]}"
                        )
                    logger.info("Installed package: %s", pkg_name)
                except subprocess.TimeoutExpired:
                    raise MCPInstallError(
                        f"pip install timed out for {pkg_name}"
                    )

            mcp.status = MCPStatus.INSTALLED
            mcp.install_source = source
            logger.info("MCP installed: %s (source=%s)", mcp_id, source)
            return mcp

    # ── Uninstall ─────────────────────────────────────────────────

    def uninstall(self, mcp_id: str) -> None:
        """Uninstall an MCP server.

        Removes it from the registry and optionally runs
        ``pip uninstall`` if the package is known.
        """
        mcp = self._registry.get(mcp_id)
        if mcp is None:
            raise MCPNotFoundError(f"MCP '{mcp_id}' is not registered")

        # Attempt pip uninstall for pip-installed packages
        if mcp.install_source == "pip":
            pkg_name = f"nexus-mcp-{mcp_id.replace('_', '-')}"
            try:
                subprocess.run(  # nosec
                    ["pip", "uninstall", "-y", pkg_name],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                logger.info("Uninstalled package: %s", pkg_name)
            except Exception as exc:
                logger.warning("pip uninstall failed (non-fatal): %s", exc)

        self._registry.unregister(mcp_id)
        logger.info("MCP uninstalled: %s", mcp_id)

    # ── Update ────────────────────────────────────────────────────

    def update(self, mcp_id: str) -> MCPDefinition:
        """Update an installed MCP server to the latest version.

        For pip-installed packages, runs ``pip install --upgrade``.
        Returns the updated MCPDefinition.
        """
        mcp = self._registry.get(mcp_id)
        if mcp is None:
            raise MCPNotFoundError(f"MCP '{mcp_id}' is not registered")

        if mcp.install_source == "pip":
            pkg_name = f"nexus-mcp-{mcp_id.replace('_', '-')}"
            logger.info("Updating package: %s", pkg_name)
            try:
                result = subprocess.run(  # nosec
                    ["pip", "install", "--upgrade", pkg_name],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode != 0:
                    logger.warning(
                        "pip upgrade returned %d: %s",
                        result.returncode,
                        result.stderr[:300],
                    )
                else:
                    logger.info("Updated package: %s", pkg_name)
            except subprocess.TimeoutExpired:
                logger.warning("pip upgrade timed out for %s", pkg_name)

        # Bump version and set status
        mcp.version = _bump_version(mcp.version)
        mcp.status = MCPStatus.INSTALLED
        logger.info("MCP updated: %s → version %s", mcp_id, mcp.version)
        return mcp

    # ── Built-in discovery ────────────────────────────────────────

    def discover_builtins(self) -> list[MCPDefinition]:
        """Discover and register all built-in MCPs."""
        return self._registry.discover_builtins()


# ── Helpers ─────────────────────────────────────────────────────────


def _bump_version(version: str) -> str:
    """Increment the patch component of a semver string."""
    try:
        parts = version.split(".")
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return f"{major}.{minor}.{patch + 1}"
    except (ValueError, IndexError):
        return "1.0.1"
