"""
Context7 MCP Integration — Real-time library documentation lookup.

Provides tools for resolving library IDs and querying official documentation
in real-time via the Context7 MCP API.

Based on Context7 patterns:
  - resolve-library-id: Identify the correct library by name/query
  - query-docs: Retrieve relevant documentation with code examples

Usage:
    from nexus.mcp_tools.context7 import Context7Tool

    tool = Context7Tool()
    library_id = await tool.resolve_library("fastapi", "FastAPI routing middleware")
    docs = await tool.query_docs(library_id, "How to use WebSocket in FastAPI")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)

# Known popular libraries mapped to their Context7 IDs
KNOWN_LIBRARIES: dict[str, str] = {
    "fastapi": "/tiangolo/fastapi",
    "next.js": "/vercel/next.js",
    "nextjs": "/vercel/next.js",
    "react": "/facebook/react",
    "vue": "/vuejs/core",
    "express": "/expressjs/express",
    "prisma": "/prisma/prisma",
    "django": "/django/django",
    "flask": "/pallets/flask",
    "typescript": "/microsoft/typescript",
    "pydantic": "/pydantic/pydantic",
    "langgraph": "/langchain/langgraph",
    "crewai": "/crewai/crewai",
    "playwright": "/microsoft/playwright",
    "supabase": "/supabase/supabase",
    "cloudflare": "/cloudflare/cloudflare-docs",
    "anthropic": "/anthropics/claude-code",
}


@dataclass
class Context7Library:
    """A library resolved from Context7."""
    library_id: str
    name: str
    description: str
    code_snippets: int = 0
    source_reputation: str = "Unknown"
    benchmark_score: float = 0.0
    versions: list[str] = field(default_factory=list)


@dataclass
class Context7Result:
    """Result from a Context7 documentation query."""
    library_id: str
    query: str
    content: str
    sources: list[str] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


class Context7Tool:
    """
    Context7 MCP integration for real-time documentation lookup.

    Provides two main methods:
      - resolve_library: Find the correct Context7 library ID
      - query_docs: Get official documentation with code examples

    The tool uses the Context7 API to fetch up-to-date, version-specific
    documentation for libraries, frameworks, and SDKs.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Context7 tool.

        Args:
            api_key: Optional Context7 API key. If not provided,
                    reads from NEXUS_CONTEXT7_API_KEY environment variable.
        """
        settings = get_settings()
        self.api_key = api_key or settings.context7_api_key or ""
        self.base_url = "https://api.context7.ai/v1"

    async def resolve_library(
        self,
        library_name: str,
        query: str = "",
    ) -> Context7Library:
        """
        Resolve a library name to a Context7 library ID.

        Args:
            library_name: The official name of the library (e.g., "FastAPI", "Next.js").
            query: Additional context about what you want to do with the library.

        Returns:
            Context7Library with the resolved library ID and metadata.
        """
        if not self.api_key:
            logger.warning("Context7 API key not configured — using fallback mock")
            return self._mock_resolve(library_name, query)

        try:
            import aiohttp

            url = f"{self.base_url}/resolve"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            params = {"name": library_name, "query": query}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params, timeout=30) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return Context7Library(
                            library_id=data.get("library_id", f"/{library_name.lower().replace('.', '/')}"),
                            name=data.get("name", library_name),
                            description=data.get("description", ""),
                            code_snippets=data.get("code_snippets", 0),
                            source_reputation=data.get("source_reputation", "Unknown"),
                            benchmark_score=data.get("benchmark_score", 0.0),
                            versions=data.get("versions", []),
                        )
                    elif resp.status == 404:
                        return self._mock_resolve(library_name, query)
                    else:
                        logger.warning("Context7 resolve failed (%d) — using fallback", resp.status)
                        return self._mock_resolve(library_name, query)

        except ImportError:
            logger.warning("aiohttp not available — using fallback resolution")
            return self._mock_resolve(library_name, query)
        except Exception as e:
            logger.warning("Context7 resolve error: %s — using fallback", e)
            return self._mock_resolve(library_name, query)

    async def query_docs(
        self,
        library_id: str,
        query: str,
        max_tokens: int = 4000,
    ) -> Context7Result:
        """
        Query official documentation from Context7.

        Args:
            library_id: The Context7 library ID (e.g., "/vercel/next.js").
            query: The specific question about the library.
            max_tokens: Maximum response length.

        Returns:
            Context7Result with documentation content and sources.
        """
        if not self.api_key:
            logger.warning("Context7 API key not configured — returning mock docs")
            return self._mock_query(library_id, query)

        try:
            import aiohttp

            url = f"{self.base_url}/query"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            payload = {
                "library_id": library_id,
                "query": query,
                "max_tokens": max_tokens,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=60) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return Context7Result(
                            library_id=library_id,
                            query=query,
                            content=data.get("content", ""),
                            sources=data.get("sources", []),
                            success=True,
                        )
                    elif resp.status == 404:
                        return self._mock_query(library_id, query)
                    else:
                        logger.warning("Context7 query failed (%d) — using fallback", resp.status)
                        return self._mock_query(library_id, query)

        except ImportError:
            logger.warning("aiohttp not available — using fallback query")
            return self._mock_query(library_id, query)
        except Exception as e:
            logger.warning("Context7 query error: %s — using fallback", e)
            return self._mock_query(library_id, query)

    async def resolve_and_query(
        self,
        library_name: str,
        query: str,
    ) -> Context7Result:
        """
        Convenience method: resolve library and query docs in one call.

        Args:
            library_name: The library name.
            query: The documentation question.

        Returns:
            Context7Result with the documentation content.
        """
        library = await self.resolve_library(library_name, query)
        return await self.query_docs(library.library_id, query)

    def _mock_resolve(self, library_name: str, query: str) -> Context7Library:
        """Fallback when Context7 API is not available."""
        normalized = library_name.lower().replace("_", " ").replace(".", " ")
        library_id = KNOWN_LIBRARIES.get(normalized, f"/{library_name.lower().replace(' ', '-')}")

        return Context7Library(
            library_id=library_id,
            name=library_name,
            description=f"Library: {library_name} (mock fallback)",
            code_snippets=100,
            source_reputation="Medium",
            benchmark_score=75.0,
            versions=[],
        )

    def _mock_query(self, library_id: str, query: str) -> Context7Result:
        """Fallback when Context7 API is not available."""
        return Context7Result(
            library_id=library_id,
            query=query,
            content=(
                f"Context7 API not configured. Query: {query}\n"
                f"Library ID: {library_id}\n"
                "Configure NEXUS_CONTEXT7_API_KEY to enable real-time documentation lookup."
            ),
            sources=[f"https://api.context7.ai/v1/library/{library_id}"],
            success=True,
        )


class Context7MCPServer:
    """
    MCP server adapter for Context7 tools.

    Exposes Context7 as an MCP tool that agents can call
    to get real-time library documentation.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.tool = Context7Tool(api_key)

    async def resolve_library(self, library_name: str, query: str = "") -> dict[str, Any]:
        """MCP tool: resolve a library to its Context7 ID."""
        result = await self.tool.resolve_library(library_name, query)
        return {
            "library_id": result.library_id,
            "name": result.name,
            "description": result.description,
            "snippets": result.code_snippets,
            "reputation": result.source_reputation,
        }

    async def query_docs(self, library_id: str, query: str) -> dict[str, Any]:
        """MCP tool: query documentation from Context7."""
        result = await self.tool.query_docs(library_id, query)
        return {
            "content": result.content,
            "sources": result.sources,
            "success": result.success,
            "error": result.error,
        }

    async def search_and_resolve(
        self,
        library_name: str,
        query: str,
    ) -> dict[str, Any]:
        """MCP tool: convenience method combining resolve and query."""
        result = await self.tool.resolve_and_query(library_name, query)
        return {
            "library_id": result.library_id,
            "content": result.content,
            "sources": result.sources,
            "success": result.success,
        }

    def get_mcp_tools(self) -> list[dict[str, Any]]:
        """Return the list of MCP tools this server provides."""
        return [
            {
                "name": "context7_resolve",
                "description": "Resolve a library name to a Context7 library ID for documentation lookup",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "library_name": {"type": "string", "description": "Official library name (e.g., FastAPI, Next.js)"},
                        "query": {"type": "string", "description": "What you want to do with the library"},
                    },
                    "required": ["library_name"],
                },
            },
            {
                "name": "context7_query",
                "description": "Query official documentation from Context7 with up-to-date code examples",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "library_id": {"type": "string", "description": "Context7 library ID (e.g., /tiangoto/fastapi)"},
                        "query": {"type": "string", "description": "Specific question about the library"},
                    },
                    "required": ["library_id", "query"],
                },
            },
            {
                "name": "context7_search",
                "description": "Combined resolve and query: find library and get docs in one call",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "library_name": {"type": "string", "description": "Official library name"},
                        "query": {"type": "string", "description": "Documentation question"},
                    },
                    "required": ["library_name", "query"],
                },
            },
        ]
