"""
NEXUS Local Tools — Thread-safe singleton registry.

Manages the lifecycle of local-only tools: registration, lookup,
enable/disable, and async execution with timeout enforcement.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Optional

from nexus.tools.base import Tool, ToolCategory, ToolHandler

logger = logging.getLogger(__name__)


# ── Registry Exceptions ──────────────────────────────────────────────


class ToolRegistryError(Exception):
    """Base exception for registry operations."""


class ToolNotFoundError(ToolRegistryError):
    """Raised when a tool name is not registered."""


class ToolDisabledError(ToolRegistryError):
    """Raised when attempting to execute a disabled tool."""


class ToolExecutionError(ToolRegistryError):
    """Raised when a tool handler raises during execution."""


class ToolTimeoutError(ToolRegistryError):
    """Raised when a tool execution exceeds its configured timeout."""


# ── Singleton Registry ──────────────────────────────────────────────


class ToolRegistry:
    """Thread-safe singleton registry for local tools.

    Usage::

        registry = ToolRegistry.get_instance()
        registry.register(my_tool)
        result = await registry.execute("my_tool", **kwargs)
    """

    _instance: Optional["ToolRegistry"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        if not getattr(self, "_initialised", False):
            self._tools: dict[str, Tool] = {}
            self._rw_lock = threading.Lock()
            self._initialised = True
            logger.info("ToolRegistry initialised")

    # ── Singleton access ─────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "ToolRegistry":
        """Return the singleton registry (create if necessary)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── Registration ──────────────────────────────────────────────

    def register(self, tool: Tool) -> None:
        """Register a tool. Re-registration overwrites silently."""
        with self._rw_lock:
            self._tools[tool.name] = tool
            logger.info(
                "Tool registered: %s (category=%s, timeout=%ds)",
                tool.name,
                tool.category.value,
                tool.timeout_seconds,
            )

    def unregister(self, name: str) -> None:
        """Remove a tool from the registry.

        Raises ToolNotFoundError if the name does not exist.
        """
        with self._rw_lock:
            if name not in self._tools:
                raise ToolNotFoundError(f"Tool '{name}' is not registered")
            del self._tools[name]
            logger.info("Tool unregistered: %s", name)

    # ── Lookup ────────────────────────────────────────────────────

    def get(self, name: str) -> Optional[Tool]:
        """Return a tool by name, or None."""
        with self._rw_lock:
            return self._tools.get(name)

    def list_tools(self, category: Optional[ToolCategory] = None) -> list[Tool]:
        """Return all tools, optionally filtered by category."""
        with self._rw_lock:
            tools = list(self._tools.values())
        if category is not None:
            tools = [t for t in tools if t.category == category]
        return tools

    def get_enabled(self) -> list[Tool]:
        """Return only enabled tools."""
        with self._rw_lock:
            return [t for t in self._tools.values() if t.enabled]

    # ── Enable / Disable ─────────────────────────────────────────

    def enable(self, name: str) -> None:
        """Enable a tool by name.

        Raises ToolNotFoundError if the name does not exist.
        """
        with self._rw_lock:
            tool = self._tools.get(name)
            if tool is None:
                raise ToolNotFoundError(f"Tool '{name}' is not registered")
            tool.enabled = True
            logger.info("Tool enabled: %s", name)

    def disable(self, name: str) -> None:
        """Disable a tool by name.

        Raises ToolNotFoundError if the name does not exist.
        """
        with self._rw_lock:
            tool = self._tools.get(name)
            if tool is None:
                raise ToolNotFoundError(f"Tool '{name}' is not registered")
            tool.enabled = False
            logger.info("Tool disabled: %s", name)

    # ── Execution ─────────────────────────────────────────────────

    async def execute(self, name: str, **kwargs: Any) -> str:
        """Execute a registered tool with timeout enforcement.

        Steps:
          1. Lookup the tool (raises ToolNotFoundError)
          2. Check it is enabled (raises ToolDisabledError)
          3. Run the handler with asyncio.wait_for timeout
          4. Wrap any exception in ToolExecutionError

        Returns the handler's string result.
        """
        tool = self.get(name)
        if tool is None:
            raise ToolNotFoundError(f"Tool '{name}' is not registered")
        if not tool.enabled:
            raise ToolDisabledError(f"Tool '{name}' is currently disabled")

        logger.debug("Executing tool: %s (timeout=%ds)", name, tool.timeout_seconds)

        try:
            result = await asyncio.wait_for(
                tool.handler(**kwargs),
                timeout=tool.timeout_seconds,
            )
            return result
        except asyncio.TimeoutError:
            raise ToolTimeoutError(
                f"Tool '{name}' timed out after {tool.timeout_seconds}s"
            )
        except ToolRegistryError:
            raise
        except Exception as exc:
            raise ToolExecutionError(
                f"Tool '{name}' execution failed: {exc}"
            ) from exc

    # ── Bulk import ───────────────────────────────────────────────

    def import_from_mcp_tools(self) -> int:
        """Auto-discover and register all tools from nexus.mcp_tools.

        Walks the ``get_all_tools()`` list in the mcp_tools package
        and wraps each async function as a local Tool.

        Category assignment is inferred from the module name.
        Returns the number of tools registered.
        """
        from nexus.mcp_tools import get_all_tools

        CATEGORY_MAP = {
            "memory_tools": ToolCategory.SYSTEM,
            "knowledge_tools": ToolCategory.SYSTEM,
            "llm_tools": ToolCategory.SYSTEM,
            "agent_tools": ToolCategory.SYSTEM,
            "code_tools": ToolCategory.CODE,
            "file_tools": ToolCategory.FILE,
            "web_tools": ToolCategory.SYSTEM,
            "reasoning_tools": ToolCategory.SYSTEM,
            "orchestration_tools": ToolCategory.SYSTEM,
            "system_tools": ToolCategory.SYSTEM,
            "bonus_tools": ToolCategory.SYSTEM,
            "avatar_tools": ToolCategory.SYSTEM,
        }

        count = 0
        for name, handler in get_all_tools():
            # Determine category
            category = ToolCategory.SYSTEM
            for mod_name, cat in CATEGORY_MAP.items():
                if mod_name.replace("_tools", "") in name:
                    category = cat
                    break

            tool = Tool(
                name=name,
                description=handler.__doc__ or f"Local wrapper for {name}",
                category=category,
                handler=handler,
                timeout_seconds=60,
                tags=["auto-imported", "mcp_tools"],
            )
            self.register(tool)
            count += 1

        logger.info("Imported %d tools from nexus.mcp_tools", count)
        return count

    def import_sovereign_tools(self) -> int:
        """Register sovereign agent tools: git, terminal, browser, filesystem."""
        import json
        from nexus.tools.git_tools import (
            git_status, git_diff, git_log, git_commit,
            git_branch, git_checkout, git_create_branch,
        )
        from nexus.tools.terminal import terminal_exec
        from nexus.tools.browser import fetch_page
        from nexus.tools.filesystem import read_file, write_file, list_directory, search_files

        tools_to_register = [
            # Git tools
            ("git_status", ToolCategory.GIT, git_status, "Get git status of repository"),
            ("git_diff", ToolCategory.GIT, git_diff, "Get git diff"),
            ("git_log", ToolCategory.GIT, git_log, "Get recent git commits"),
            ("git_commit", ToolCategory.GIT, git_commit, "Stage and commit changes"),
            ("git_branch", ToolCategory.GIT, git_branch, "List branches"),
            ("git_checkout", ToolCategory.GIT, git_checkout, "Switch to a branch"),
            ("git_create_branch", ToolCategory.GIT, git_create_branch, "Create new branch"),
            # Terminal
            ("terminal_exec", ToolCategory.SHELL, terminal_exec, "Execute terminal command with sandboxing"),
            # Browser
            ("fetch_page", ToolCategory.SYSTEM, fetch_page, "Fetch web page content"),
            # Filesystem
            ("read_file", ToolCategory.FILE, read_file, "Read file with path traversal protection"),
            ("write_file", ToolCategory.FILE, write_file, "Write file with path traversal protection"),
            ("list_directory", ToolCategory.FILE, list_directory, "List directory contents"),
            ("search_files", ToolCategory.FILE, search_files, "Search files by pattern"),
        ]

        count = 0
        for name, category, handler, description in tools_to_register:
            # Wrap sync functions as async
            async def async_wrapper(func=handler, **kwargs):
                result = func(**kwargs)
                if isinstance(result, dict):
                    return json.dumps(result, ensure_ascii=False)
                return str(result)

            tool = Tool(
                name=name,
                description=description,
                category=category,
                handler=async_wrapper,
                timeout_seconds=60,
                tags=["sovereign", "production"],
            )
            self.register(tool)
            count += 1

        logger.info("Registered %d sovereign tools", count)
        return count

    # ── Stats ─────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return aggregate statistics about registered tools."""
        with self._rw_lock:
            total = len(self._tools)
            by_category: dict[str, int] = {}
            enabled_count = 0
            for t in self._tools.values():
                by_category[t.category.value] = by_category.get(t.category.value, 0) + 1
                if t.enabled:
                    enabled_count += 1
        return {
            "total": total,
            "enabled": enabled_count,
            "disabled": total - enabled_count,
            "by_category": by_category,
        }


# ── Module-level convenience ────────────────────────────────────────


def get_tool_registry() -> ToolRegistry:
    """Return the singleton ToolRegistry."""
    return ToolRegistry.get_instance()
