"""
L2 Episodic Memory — Chronological experience journal.

Stores the agent's experiences as a timeline of events, each with
context, actions taken, and outcomes. Enables temporal recall
("what did I do last week?") and experience-based learning.

Inspired by GenericAgent's session archives and Hermes Agent's
diary system. Each episode is stored in ChromaDB namespace 'episodes'.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from nexus.memory.chroma_service import NexusMemoryService

logger = logging.getLogger(__name__)


@dataclass
class Episode:
    """A single episodic memory entry."""
    task: str
    actions: list[str]
    outcome: str
    success: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_seconds: float = 0.0
    tools_used: list[str] = field(default_factory=list)
    model_used: str = ""
    token_cost: float = 0.0
    tags: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        """Convert episode to searchable text representation."""
        status = "SUCCESS" if self.success else "FAILURE"
        lines = [
            f"Task: {self.task}",
            f"Outcome: {status} — {self.outcome}",
            f"Actions taken: {'; '.join(self.actions)}",
            f"Tools used: {', '.join(self.tools_used) or 'none'}",
            f"Duration: {self.duration_seconds:.1f}s",
        ]
        if self.tags:
            lines.append(f"Tags: {', '.join(self.tags)}")
        return "\n".join(lines)

    def to_metadata(self) -> dict[str, Any]:
        """Convert episode to ChromaDB-compatible metadata."""
        return {
            "success": str(self.success),
            "timestamp": self.timestamp,
            "duration_seconds": str(self.duration_seconds),
            "model_used": self.model_used,
            "token_cost": str(self.token_cost),
            "tools_count": str(len(self.tools_used)),
            "actions_count": str(len(self.actions)),
            "tags": ",".join(self.tags),
            "source": "episode",
        }


class EpisodicMemory:
    """
    L2 Episodic Memory — stores and retrieves chronological experiences.

    Each episode represents a completed (or failed) task execution with
    full context about what was attempted and what happened.

    Usage:
        episodic = EpisodicMemory(memory_service)
        await episodic.record(Episode(
            task="Search for AI papers",
            actions=["web_search", "summarize"],
            outcome="Found 5 relevant papers",
            success=True,
            tools_used=["web_search"],
        ))
        recent = await episodic.recall_recent(limit=5)
    """

    def __init__(self, memory_service: NexusMemoryService):
        self.memory = memory_service

    async def record(self, episode: Episode) -> str:
        """
        Record a new episodic memory.

        Args:
            episode: The Episode to record.

        Returns:
            Document ID of the stored episode.
        """
        doc_id = await self.memory.store(
            text=episode.to_text(),
            metadata=episode.to_metadata(),
            namespace="episodes",
        )
        logger.info(
            "Recorded episode: task='%s' success=%s id=%s",
            episode.task[:50], episode.success, doc_id,
        )
        return doc_id

    async def recall_recent(
        self,
        limit: int = 10,
        where: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Recall recent episodes, ordered by recency.

        Args:
            limit: Maximum number of episodes to return.
            where: Optional metadata filter.

        Returns:
            List of episode dicts with id, text, and metadata.
        """
        results = await self.memory.list_documents(
            namespace="episodes",
            limit=limit,
            where=where,
        )
        episodes = []
        for i, doc_id in enumerate(results.get("ids", [])):
            episodes.append({
                "id": doc_id,
                "text": results["documents"][i] if results.get("documents") else "",
                "metadata": results["metadatas"][i] if results.get("metadatas") else {},
            })
        return episodes

    async def recall_similar(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Recall episodes similar to a given query.

        Args:
            query: Description of the type of episode to find.
            top_k: Number of results.

        Returns:
            List of matching episodes.
        """
        results = await self.memory.search(
            query=query,
            namespace="episodes",
            top_k=top_k,
        )
        episodes = []
        for i, doc_id in enumerate(results.get("ids", [[]])[0]):
            episodes.append({
                "id": doc_id,
                "text": results["documents"][0][i] if results.get("documents") else "",
                "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                "distance": results["distances"][0][i] if results.get("distances") else 0.0,
            })
        return episodes

    async def recall_successful(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Recall only successful episodes similar to a query.

        Useful for skill crystallization — we only want to learn
        from successful trajectories.
        """
        results = await self.memory.search(
            query=query,
            namespace="episodes",
            top_k=top_k * 2,  # Over-fetch to filter
            where={"success": "True"},
        )
        episodes = []
        for i, doc_id in enumerate(results.get("ids", [[]])[0]):
            episodes.append({
                "id": doc_id,
                "text": results["documents"][0][i] if results.get("documents") else "",
                "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                "distance": results["distances"][0][i] if results.get("distances") else 0.0,
            })
        return episodes[:top_k]

    async def get_stats(self) -> dict[str, Any]:
        """Get episodic memory statistics."""
        total = await self.memory.count(namespace="episodes")
        return {
            "total_episodes": total,
            "namespace": "episodes",
        }
