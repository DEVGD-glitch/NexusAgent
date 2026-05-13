"""
L4 Procedural Memory — Skill crystallization and reusable SOPs.

Stores crystallized skills (Standard Operating Procedures) that are
automatically extracted from successful task trajectories. Inspired by
Hermes Agent's skill crystallization and GenericAgent's SOP system.

Skills are versioned, testable, and composable. Each skill captures:
  - The task pattern it solves
  - The sequence of tool calls and reasoning steps
  - Success criteria and validation logic
  - Usage statistics and quality metrics
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from nexus.memory.chroma_service import NexusMemoryService

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """A crystallized procedural skill."""
    name: str
    description: str
    pattern: str  # Natural language description of the execution pattern
    steps: list[dict[str, Any]]  # Ordered list of {action, tool, params, condition}
    success_criteria: str  # How to determine if skill execution succeeded
    version: int = 1
    domain: str = "general"
    tags: list[str] = field(default_factory=list)
    usage_count: int = 0
    success_rate: float = 0.0
    quality_score: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_text(self) -> str:
        """Convert skill to searchable text for ChromaDB."""
        steps_text = "\n".join(
            f"  {i+1}. {step.get('action', 'unknown')} via {step.get('tool', 'unknown')}"
            for i, step in enumerate(self.steps)
        )
        return (
            f"Skill: {self.name}\n"
            f"Description: {self.description}\n"
            f"Pattern: {self.pattern}\n"
            f"Steps:\n{steps_text}\n"
            f"Success criteria: {self.success_criteria}\n"
            f"Domain: {self.domain}\n"
            f"Tags: {', '.join(self.tags)}\n"
            f"Quality: {self.quality_score:.2f} | Usage: {self.usage_count} | "
            f"Success rate: {self.success_rate:.1%}"
        )

    def to_metadata(self) -> dict[str, Any]:
        """Convert skill to ChromaDB-compatible metadata."""
        return {
            "name": self.name,
            "version": str(self.version),
            "domain": self.domain,
            "usage_count": str(self.usage_count),
            "success_rate": str(self.success_rate),
            "quality_score": str(self.quality_score),
            "steps_count": str(len(self.steps)),
            "tags": ",".join(self.tags),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source": "skill_crystallization",
        }


class ProceduralMemory:
    """
    L4 Procedural Memory — manages crystallized skills and SOPs.

    Skills are automatically created from successful task completions
    and can be retrieved by similarity to a new task description.

    Usage:
        procedural = ProceduralMemory(memory_service)
        await procedural.crystallize(Skill(
            name="web_search_and_summarize",
            description="Search the web and summarize results",
            pattern="query -> search -> extract -> summarize",
            steps=[
                {"action": "decompose_query", "tool": "reasoning"},
                {"action": "web_search", "tool": "web_search"},
                {"action": "summarize", "tool": "llm"},
            ],
            success_criteria="Summary contains key findings from search results",
            domain="research",
        ))
        matching = await procedural.find_relevant("I need to research AI agents")
    """

    def __init__(self, memory_service: NexusMemoryService):
        self.memory = memory_service

    async def crystallize(self, skill: Skill) -> str:
        """
        Crystallize a new skill into procedural memory.

        If a skill with the same name already exists, increment version
        and update it.

        Args:
            skill: The Skill to crystallize.

        Returns:
            Document ID of the stored skill.
        """
        existing = await self.get_skill_by_name(skill.name)
        if existing:
            skill.version = int(existing.get("metadata", {}).get("version", "0")) + 1
            skill.usage_count = int(existing.get("metadata", {}).get("usage_count", "0"))
            skill.success_rate = float(existing.get("metadata", {}).get("success_rate", "0"))
            doc_id = existing["id"]
            await self.memory.update(
                doc_id=doc_id,
                text=skill.to_text(),
                metadata=skill.to_metadata(),
                namespace="skills",
            )
            logger.info("Updated skill '%s' to version %d", skill.name, skill.version)
            return doc_id

        doc_id = await self.memory.store(
            text=skill.to_text(),
            metadata=skill.to_metadata(),
            namespace="skills",
        )
        logger.info("Crystallized new skill '%s' (v%d)", skill.name, skill.version)
        return doc_id

    async def find_relevant(
        self,
        task_description: str,
        top_k: int = 3,
        min_quality: float = 0.3,
    ) -> list[dict[str, Any]]:
        """
        Find skills relevant to a task description.

        Args:
            task_description: Description of the task to solve.
            top_k: Number of skills to return.
            min_quality: Minimum quality score filter.

        Returns:
            List of matching skills sorted by relevance.
        """
        results = await self.memory.search(
            query=task_description,
            namespace="skills",
            top_k=top_k * 2,  # Over-fetch to filter by quality
        )

        skills = []
        for i, doc_id in enumerate(results.get("ids", [[]])[0]):
            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            quality = float(meta.get("quality_score", "0"))
            if quality < min_quality:
                continue
            skills.append({
                "id": doc_id,
                "text": results["documents"][0][i] if results.get("documents") else "",
                "metadata": meta,
                "distance": results["distances"][0][i] if results.get("distances") else 0.0,
                "quality_score": quality,
            })
        return skills[:top_k]

    async def get_skill_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """
        Get a skill by its exact name.

        Args:
            name: Skill name.

        Returns:
            Skill dict or None if not found.
        """
        results = await self.memory.search(
            query=f"Skill: {name}",
            namespace="skills",
            top_k=5,
        )

        for i, doc_id in enumerate(results.get("ids", [[]])[0]):
            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            if meta.get("name") == name:
                return {
                    "id": doc_id,
                    "text": results["documents"][0][i] if results.get("documents") else "",
                    "metadata": meta,
                }
        return None

    async def record_usage(
        self,
        skill_name: str,
        success: bool,
    ) -> bool:
        """
        Record a usage event for a skill, updating its statistics.

        Args:
            skill_name: Name of the skill used.
            success: Whether the usage was successful.

        Returns:
            True if the skill was found and updated.
        """
        skill_data = await self.get_skill_by_name(skill_name)
        if not skill_data:
            logger.warning("Tried to record usage for unknown skill: %s", skill_name)
            return False

        meta = skill_data["metadata"]
        usage_count = int(meta.get("usage_count", "0")) + 1
        success_rate = float(meta.get("success_rate", "0"))
        prev_usage = int(meta.get("usage_count", "1"))
        prev_successes = int(round(success_rate * prev_usage))
        new_successes = prev_successes + (1 if success else 0)
        new_rate = new_successes / usage_count

        await self.memory.update(
            doc_id=skill_data["id"],
            metadata={
                "usage_count": str(usage_count),
                "success_rate": str(new_rate),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            namespace="skills",
        )
        logger.info("Recorded usage of skill '%s': success=%s rate=%.2f", skill_name, success, new_rate)
        return True

    async def get_stats(self) -> dict[str, Any]:
        """Get procedural memory statistics."""
        total = await self.memory.count(namespace="skills")
        return {
            "total_skills": total,
            "namespace": "skills",
        }
