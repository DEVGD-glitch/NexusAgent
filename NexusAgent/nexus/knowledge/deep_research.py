"""
NEXUS Deep Research — Multi-document synthesis and comprehensive research.

Implements a deep research capability that:
  1. Decomposes a research question into sub-queries
  2. Searches multiple sources (web + local memory)
  3. Synthesizes findings across documents
  4. Produces a structured research report with citations
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ResearchSource:
    """A source found during research."""
    title: str
    url: str = ""
    snippet: str = ""
    relevance: float = 0.0
    source_type: str = "web"  # web, memory, document


@dataclass
class ResearchReport:
    """A structured research report."""
    topic: str
    summary: str
    key_findings: list[str] = field(default_factory=list)
    sources: list[ResearchSource] = field(default_factory=list)
    sections: list[dict[str, str]] = field(default_factory=list)
    confidence: float = 0.0
    depth: str = "medium"


class DeepResearch:
    """
    Deep Research engine for comprehensive multi-source research.

    Usage:
        research = DeepResearch()
        report = await research.investigate(
            topic="Latest advances in AI agent architectures",
            depth="deep",
        )
    """

    def __init__(self, max_sub_queries: int = 5, max_sources_per_query: int = 5):
        self.max_sub_queries = max_sub_queries
        self.max_sources_per_query = max_sources_per_query

    async def investigate(
        self,
        topic: str,
        depth: str = "medium",  # quick, medium, deep
    ) -> ResearchReport:
        """
        Conduct deep research on a topic.

        Args:
            topic: Research topic/question.
            depth: Research depth (quick=1 iteration, medium=2, deep=3+).

        Returns:
            ResearchReport with findings and sources.
        """
        depth_map = {"quick": 1, "medium": 2, "deep": 3}
        max_iterations = depth_map.get(depth, 2)

        # Step 1: Decompose into sub-queries
        sub_queries = await self._decompose_query(topic)
        all_sources: list[ResearchSource] = []
        all_findings: list[str] = []

        # Step 2: Search for each sub-query
        for iteration in range(max_iterations):
            for query in sub_queries[:self.max_sub_queries]:
                sources = await self._search_sources(query)
                all_sources.extend(sources)

                # Extract findings from sources
                for source in sources[:3]:
                    finding = await self._extract_finding(query, source)
                    if finding:
                        all_findings.append(finding)

            # Refine sub-queries for next iteration based on findings
            if iteration < max_iterations - 1 and all_findings:
                sub_queries = await self._refine_queries(topic, all_findings)

        # Deduplicate sources
        seen_urls = set()
        unique_sources = []
        for s in all_sources:
            key = s.url or s.snippet[:50]
            if key not in seen_urls:
                seen_urls.add(key)
                unique_sources.append(s)

        # Step 3: Synthesize report
        report = await self._synthesize(topic, all_findings, unique_sources, depth)
        return report

    async def _decompose_query(self, topic: str) -> list[str]:
        """Decompose a research topic into searchable sub-queries."""
        try:
            from nexus.llm.router import LLMRouter, TaskComplexity
            router = LLMRouter()
            response = await router.complete(
                messages=[
                    {"role": "system", "content": "Break down this research topic into 3-5 specific searchable sub-questions. Output as a numbered list."},
                    {"role": "user", "content": topic},
                ],
                task_complexity=TaskComplexity.MEDIUM,
                temperature=0.5,
                max_tokens=300,
            )

            queries = []
            for line in response.content.strip().split("\n"):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-")):
                    clean = line.lstrip("0123456789.-) ").strip()
                    if clean:
                        queries.append(clean)
            return queries or [topic]
        except Exception:
            return [topic]

    async def _search_sources(self, query: str) -> list[ResearchSource]:
        """Search multiple sources for a query."""
        sources = []

        # Search local memory first
        try:
            from nexus.memory.chroma_service import NexusMemoryService
            from nexus.core.config import get_settings
            settings = get_settings()
            service = NexusMemoryService(persist_dir=settings.chroma_persist_dir)
            results = await service.search(query=query, namespace="knowledge", top_k=3)
            for i, doc_id in enumerate(results.get("ids", [[]])[0]):
                text = results["documents"][0][i] if results.get("documents") else ""
                meta = results["metadatas"][0][i] if results.get("metadatas") else {}
                sources.append(ResearchSource(
                    title=meta.get("source", "local_memory"),
                    snippet=text[:300],
                    relevance=1.0 - (results["distances"][0][i] if results.get("distances") else 0.5),
                    source_type="memory",
                ))
        except Exception:
            pass

        # Search web if available
        try:
            from nexus.knowledge.web_search import MultiSourceWebSearch
            search = MultiSourceWebSearch()
            results = await search.search(query=query, num_results=self.max_sources_per_query)
            for item in results:
                sources.append(ResearchSource(
                    title=item.title,
                    url=item.url,
                    snippet=item.snippet,
                    source_type="web",
                ))
        except Exception:
            pass

        return sources

    async def _extract_finding(self, query: str, source: ResearchSource) -> Optional[str]:
        """Extract a key finding from a source."""
        if not source.snippet:
            return None
        return f"[{source.title}] {source.snippet[:200]}"

    async def _refine_queries(self, topic: str, findings: list[str]) -> list[str]:
        """Generate refined sub-queries based on current findings."""
        try:
            from nexus.llm.router import LLMRouter, TaskComplexity
            router = LLMRouter()
            findings_text = "\n".join(f"- {f}" for f in findings[:5])
            response = await router.complete(
                messages=[
                    {"role": "system", "content": "Based on initial findings, generate 3 follow-up research questions."},
                    {"role": "user", "content": f"Topic: {topic}\n\nFindings so far:\n{findings_text}\n\nFollow-up questions:"},
                ],
                task_complexity=TaskComplexity.SIMPLE,
                temperature=0.6,
                max_tokens=200,
            )
            queries = []
            for line in response.content.strip().split("\n"):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-")):
                    clean = line.lstrip("0123456789.-) ").strip()
                    if clean:
                        queries.append(clean)
            return queries or [topic]
        except Exception:
            return [topic]

    async def _synthesize(
        self,
        topic: str,
        findings: list[str],
        sources: list[ResearchSource],
        depth: str,
    ) -> ResearchReport:
        """Synthesize findings into a structured report."""
        try:
            from nexus.llm.router import LLMRouter, TaskComplexity
            router = LLMRouter()

            findings_text = "\n".join(f"- {f}" for f in findings[:15])
            sources_text = "\n".join(f"- {s.title}: {s.snippet[:100]}" for s in sources[:10])

            prompt = (
                f"Synthesize the following research into a structured report.\n\n"
                f"Topic: {topic}\n\n"
                f"Key Findings:\n{findings_text}\n\n"
                f"Sources:\n{sources_text}\n\n"
                f"Provide:\n"
                f"1. A concise summary (2-3 paragraphs)\n"
                f"2. Key findings (numbered list)\n"
                f"3. Confidence level (high/medium/low)\n\n"
                f"Format as JSON with keys: summary, key_findings, confidence"
            )

            response = await router.complete(
                messages=[{"role": "user", "content": prompt}],
                task_complexity=TaskComplexity.MEDIUM,
                temperature=0.3,
                max_tokens=1024,
            )

            try:
                # Extract JSON from response
                content = response.content
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                data = json.loads(content.strip())
                return ResearchReport(
                    topic=topic,
                    summary=data.get("summary", ""),
                    key_findings=data.get("key_findings", []),
                    sources=sources,
                    confidence=1.0 if data.get("confidence") == "high" else 0.5 if data.get("confidence") == "medium" else 0.25,
                    depth=depth,
                )
            except (json.JSONDecodeError, KeyError):
                return ResearchReport(
                    topic=topic,
                    summary=response.content[:1000],
                    key_findings=findings[:5],
                    sources=sources,
                    depth=depth,
                )
        except Exception as e:
            logger.error("Research synthesis failed: %s", e)
            return ResearchReport(
                topic=topic,
                summary=f"Research failed: {str(e)}",
                key_findings=findings[:3],
                sources=sources,
                depth=depth,
            )
