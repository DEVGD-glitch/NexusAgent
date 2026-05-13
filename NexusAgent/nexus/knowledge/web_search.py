"""
NEXUS Web Search — Multi-source web search aggregation.

Supports multiple search backends:
  - z-ai-web-dev-sdk (primary)
  - SerpAPI
  - Brave Search
  - DuckDuckGo (fallback, no API key needed)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single web search result."""
    title: str
    url: str
    snippet: str
    source_engine: str = ""
    rank: int = 0
    date: str = ""


class MultiSourceWebSearch:
    """
    Multi-source web search aggregator.

    Tries search backends in order of availability and merges
    results with deduplication.

    Usage:
        search = MultiSourceWebSearch()
        results = await search.search("AI agents 2024", num_results=10)
    """

    def __init__(self):
        self.settings = get_settings()

    async def search(
        self,
        query: str,
        num_results: int = 10,
        engines: Optional[list[str]] = None,
    ) -> list[SearchResult]:
        """
        Search the web using multiple backends.

        Args:
            query: Search query.
            num_results: Desired number of results.
            engines: Specific engines to use (default: try all).

        Returns:
            Deduplicated, merged search results.
        """
        all_results: list[SearchResult] = []
        seen_urls = set()

        # Try each engine
        engine_list = engines or ["zai_sdk", "serpapi", "brave", "duckduckgo"]

        for engine in engine_list:
            try:
                if engine == "zai_sdk":
                    results = await self._search_zai_sdk(query, num_results)
                elif engine == "serpapi":
                    results = await self._search_serpapi(query, num_results)
                elif engine == "brave":
                    results = await self._search_brave(query, num_results)
                elif engine == "duckduckgo":
                    results = await self._search_duckduckgo(query, num_results)
                else:
                    continue

                for r in results:
                    if r.url not in seen_urls:
                        seen_urls.add(r.url)
                        all_results.append(r)

            except Exception as e:
                logger.debug("Search engine %s failed: %s", engine, e)
                continue

            if len(all_results) >= num_results:
                break

        return all_results[:num_results]

    async def _search_zai_sdk(self, query: str, num_results: int) -> list[SearchResult]:
        """Search using z-ai-web-dev-sdk."""
        try:
            import z_ai_web_dev_sdk as zai_sdk
            zai = await zai_sdk.ZAI.create()
            search_result = await zai.functions.invoke("web_search", {"query": query, "num": num_results})

            results = []
            for item in search_result:
                results.append(SearchResult(
                    title=item.get("name", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                    source_engine="zai_sdk",
                    rank=item.get("rank", 0),
                    date=item.get("date", ""),
                ))
            return results
        except (ImportError, AttributeError, Exception) as e:
            logger.debug("ZAI SDK search failed: %s", e)
            return []

    async def _search_serpapi(self, query: str, num_results: int) -> list[SearchResult]:
        """Search using SerpAPI."""
        api_key = self.settings.serpapi_key
        if not api_key:
            return []

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://serpapi.com/search",
                params={"q": query, "api_key": api_key, "num": num_results},
            )
            if response.status_code != 200:
                return []

            data = response.json()
            results = []
            for item in data.get("organic_results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    source_engine="serpapi",
                ))
            return results

    async def _search_brave(self, query: str, num_results: int) -> list[SearchResult]:
        """Search using Brave Search API."""
        api_key = self.settings.brave_search_key
        if not api_key:
            return []

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": num_results},
                headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
            )
            if response.status_code != 200:
                return []

            data = response.json()
            results = []
            for item in data.get("web", {}).get("results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("description", ""),
                    source_engine="brave",
                ))
            return results

    async def _search_duckduckgo(self, query: str, num_results: int) -> list[SearchResult]:
        """Search using DuckDuckGo (no API key needed, HTML scraping fallback)."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0 (compatible; NEXUS/1.0)"},
                )
                if response.status_code != 200:
                    return []

                # Simple HTML parsing for DDG results
                import re
                results = []
                # Extract result blocks
                result_blocks = re.findall(
                    r'<a rel="nofollow" class="result__a" href="([^"]+)">(.*?)</a>.*?'
                    r'<a class="result__snippet".*?>(.*?)</a>',
                    response.text, re.DOTALL
                )
                for url, title, snippet in result_blocks[:num_results]:
                    clean_title = re.sub(r'<[^>]+>', '', title).strip()
                    clean_snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                    results.append(SearchResult(
                        title=clean_title,
                        url=url,
                        snippet=clean_snippet,
                        source_engine="duckduckgo",
                    ))
                return results
        except Exception as e:
            logger.debug("DuckDuckGo search failed: %s", e)
            return []
