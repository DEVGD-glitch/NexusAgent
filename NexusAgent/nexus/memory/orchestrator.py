"""
NEXUS Memory Orchestrator — Intelligent memory routing and coordination.

Routes tasks to the appropriate memory type based on context analysis:
  - Working: Immediate context, active conversation
  - Episodic: Events, experiences, completed tasks
  - Semantic: Facts, knowledge, learned concepts
  - Procedural: How-to, skills, processes
  - Identity: User preferences, self-knowledge

Usage:
    from nexus.memory.orchestrator import MemoryOrchestrator, MemoryContext

    orchestrator = MemoryOrchestrator()
    result = await orchestrator.store(task="debug_error", data="error trace...", context=ctx)
    retrieved = await orchestrator.recall(query="how did we solve that error?", context=ctx)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    """The 5 memory types in NEXUS architecture."""
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    IDENTITY = "identity"


@dataclass
class MemoryContext:
    """Context for memory operations."""
    task: str = ""
    task_type: str = "general"  # research, coding, planning, debugging, etc.
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    priority: float = 1.0  # Higher = more important
    ttl_seconds: Optional[int] = None  # None = permanent
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryResult:
    """Result from a memory operation."""
    memory_type: MemoryType
    content: Any
    relevance_score: float = 1.0
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class MemoryOrchestrator:
    """
    Intelligent memory router — decides which memory type to use.

    Uses keyword analysis and LLM-based context understanding to route
    memory operations to the appropriate memory system.

    Key features:
      - Automatic memory type detection from task context
      - Unified store/recall interface across all memory types
      - Memory coherence (cross-memory relationships)
      - Priority-based retention
    """

    def __init__(self, settings: Optional[Any] = None):
        self.settings = settings or get_settings()
        self._memory_svc = None
        self._llm_router = None
        self._working_sessions: dict[str, Any] = {}

    @property
    def memory_service(self):
        if self._memory_svc is None:
            from nexus.memory.chroma_service import NexusMemoryService
            self._memory_svc = NexusMemoryService(persist_dir=self.settings.chroma_persist_dir)
        return self._memory_svc

    def _detect_memory_type(self, context: MemoryContext) -> MemoryType:
        """
        Detect which memory type is most appropriate for this context.

        Uses keyword analysis with LLM fallback for ambiguous cases.
        """
        task = context.task.lower()
        task_type = context.task_type.lower()

        # Keyword-based routing
        episodic_keywords = ["happened", "yesterday", "last time", "before", "when", "experience",
                            "completed", "finished", "did", "worked on", "tried"]
        semantic_keywords = ["know", "learn", "fact", "information", "explain", "what is", "define",
                            "remember", "concept", "understand"]
        procedural_keywords = ["how to", "how do", "step", "process", "workflow", "procedure",
                              "method", "technique", "install", "configure", "setup"]
        identity_keywords = ["i prefer", "my name", "i like", "i want", "i need", "my goal",
                           "preference", "setting", "user", "profile"]
        working_keywords = ["now", "current", "right now", "this", "ongoing", "active", "context"]

        # Score each memory type
        scores = {MemoryType.WORKING: 0, MemoryType.EPISODIC: 0, MemoryType.SEMANTIC: 0,
                  MemoryType.PROCEDURAL: 0, MemoryType.IDENTITY: 0}

        for kw in episodic_keywords:
            if kw in task:
                scores[MemoryType.EPISODIC] += 2
        for kw in semantic_keywords:
            if kw in task:
                scores[MemoryType.SEMANTIC] += 2
        for kw in procedural_keywords:
            if kw in task:
                scores[MemoryType.PROCEDURAL] += 2
        for kw in identity_keywords:
            if kw in task:
                scores[MemoryType.IDENTITY] += 2
        for kw in working_keywords:
            if kw in task:
                scores[MemoryType.WORKING] += 2

        # Task type bias
        if task_type in ("research", "analysis", "exploration"):
            scores[MemoryType.SEMANTIC] += 3
        elif task_type in ("coding", "implementation", "debugging"):
            scores[MemoryType.PROCEDURAL] += 2
            scores[MemoryType.EPISODIC] += 1
        elif task_type in ("planning", "strategy"):
            scores[MemoryType.SEMANTIC] += 1
            scores[MemoryType.EPISODIC] += 2
        elif task_type == "conversation":
            scores[MemoryType.WORKING] += 2

        # Return highest scoring type
        return max(scores, key=scores.get)

    async def _detect_memory_type_llm(self, context: MemoryContext) -> MemoryType:
        """
        LLM-based memory type detection for ambiguous cases.

        Fallback when keyword analysis is inconclusive.
        """
        try:
            from nexus.llm.router import LLMRouter, TaskComplexity

            router = LLMRouter()
            prompt = (
                f"Classify this task into one of these memory types:\n"
                f"  - WORKING: immediate context, current conversation\n"
                f"  - EPISODIC: past events, completed tasks, experiences\n"
                f"  - SEMANTIC: facts, knowledge, learned concepts\n"
                f"  - PROCEDURAL: how-to, skills, step-by-step processes\n"
                f"  - IDENTITY: user preferences, self-knowledge\n\n"
                f"Task: {context.task}\n"
                f"Task type: {context.task_type}\n\n"
                f"Respond with only the memory type name (e.g., SEMANTIC)."
            )
            response = await router.complete(
                messages=[{"role": "user", "content": prompt}],
                task_complexity=TaskComplexity.SIMPLE,
                temperature=0.0,
                max_tokens=10,
            )
            result = response.content.strip().upper()
            for mt in MemoryType:
                if mt.value.upper() in result:
                    return mt
            return MemoryType.WORKING  # Default
        except Exception:
            return self._detect_memory_type(context)

    async def store(
        self,
        data: str,
        context: MemoryContext,
    ) -> str:
        """
        Store data in the appropriate memory type.

        Args:
            data: The content to store.
            context: Memory context for routing decision.

        Returns:
            Storage ID.
        """
        # Detect memory type
        if self._is_ambiguous(context.task):
            memory_type = await self._detect_memory_type_llm(context)
        else:
            memory_type = self._detect_memory_type(context)

        # Build namespace and metadata
        metadata = {
            "memory_type": memory_type.value,
            "task_type": context.task_type,
            "priority": context.priority,
            **context.metadata,
        }
        storage_id = f"{memory_type.value}_{id(data) % 100000:05d}"

        try:
            if memory_type == MemoryType.WORKING:
                from nexus.memory.working import WorkingMemory, MessageRole
                session_id = context.session_id or "default"
                if session_id not in self._working_sessions:
                    self._working_sessions[session_id] = WorkingMemory()
                wm = self._working_sessions[session_id]
                role_str = context.metadata.get("role", "assistant").upper()
                role = MessageRole(role_str) if role_str in ("SYSTEM", "USER", "ASSISTANT", "TOOL") else MessageRole.ASSISTANT
                wm.add(role=role, content=data, priority=context.priority)
                storage_id = f"working_{wm.total_tokens}"

            elif memory_type == MemoryType.EPISODIC:
                actual_id = await self.memory_service.store(
                    text=data,
                    metadata={**metadata, "task": context.task, "outcome": context.metadata.get("outcome", "")},
                    namespace="episodes",
                )
                storage_id = actual_id

            elif memory_type == MemoryType.SEMANTIC:
                actual_id = await self.memory_service.store(
                    text=data,
                    metadata=metadata,
                    namespace="knowledge",
                )
                storage_id = actual_id

            elif memory_type == MemoryType.PROCEDURAL:
                actual_id = await self.memory_service.store(
                    text=data,
                    metadata={**metadata, "trigger": context.task},
                    namespace="skills",
                )
                storage_id = actual_id

            elif memory_type == MemoryType.IDENTITY:
                actual_id = await self.memory_service.store(
                    text=data,
                    metadata={**metadata, "user_id": context.user_id or "default"},
                    namespace="identity",
                )
                storage_id = actual_id

            logger.info("Stored in %s memory: id=%s", memory_type.value, storage_id)
            return storage_id

        except Exception as e:
            logger.error("Failed to store in %s memory: %s", memory_type.value, e)
            # Fallback to semantic memory
            actual_id = await self.memory_service.store(
                text=data,
                metadata={**metadata, "fallback": "true"},
                namespace="semantic",
            )
            return actual_id

    async def recall(
        self,
        query: str,
        context: MemoryContext,
        n_results: int = 5,
    ) -> list[MemoryResult]:
        """
        Recall relevant memories across all types.

        Args:
            query: The query string.
            context: Memory context for routing.
            n_results: Number of results per memory type.

        Returns:
            List of MemoryResult sorted by relevance.
        """
        # Detect target memory types
        if self._is_ambiguous(query):
            target_types = list(MemoryType)  # Search all types
        else:
            primary_type = self._detect_memory_type(context)
            # Also check semantic for factual queries
            if primary_type == MemoryType.WORKING:
                target_types = [MemoryType.WORKING, MemoryType.SEMANTIC]
            else:
                target_types = [primary_type]

        results: list[MemoryResult] = []

        for mem_type in target_types:
            try:
                if mem_type == MemoryType.WORKING:
                    from nexus.memory.working import WorkingMemory
                    session_id = context.session_id or "default"
                    if session_id not in self._working_sessions:
                        self._working_sessions[session_id] = WorkingMemory()
                    wm = self._working_sessions[session_id]
                    for msg in wm.messages:
                        if query.lower() in msg.content.lower():
                            results.append(MemoryResult(
                                memory_type=mem_type,
                                content=msg.content,
                                relevance_score=0.8,
                            ))

                elif mem_type == MemoryType.EPISODIC:
                    raw = await self.memory_service.search(
                        query=query,
                        top_k=n_results,
                        namespace="episodes",
                    )
                    episode_results = self._parse_chroma_results(raw)
                    for ep in episode_results:
                        results.append(MemoryResult(
                            memory_type=mem_type,
                            content=ep.get("text", ""),
                            relevance_score=ep.get("relevance", 0.5),
                        ))

                elif mem_type == MemoryType.SEMANTIC:
                    raw = await self.memory_service.search(
                        query=query,
                        top_k=n_results,
                        namespace="semantic",
                    )
                    for r in self._parse_chroma_results(raw):
                        results.append(MemoryResult(
                            memory_type=mem_type,
                            content=r.get("text", ""),
                            relevance_score=r.get("relevance", 0.5),
                        ))

                elif mem_type == MemoryType.PROCEDURAL:
                    raw = await self.memory_service.search(
                        query=query,
                        top_k=n_results,
                        namespace="skills",
                    )
                    for p in self._parse_chroma_results(raw):
                        results.append(MemoryResult(
                            memory_type=mem_type,
                            content=p.get("text", ""),
                            relevance_score=p.get("relevance", 0.5),
                        ))

                elif mem_type == MemoryType.IDENTITY:
                    raw = await self.memory_service.search(
                        query=query,
                        top_k=n_results,
                        namespace="identity",
                    )
                    for i in self._parse_chroma_results(raw):
                        results.append(MemoryResult(
                            memory_type=mem_type,
                            content=i.get("text", ""),
                            relevance_score=i.get("relevance", 0.5),
                        ))

            except Exception as e:
                logger.warning("Recall failed for %s memory: %s", mem_type.value, e)

        # Sort by relevance
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[:n_results * len(target_types)]

    def _parse_chroma_results(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse ChromaDB query results into normalized dicts."""
        ids = raw.get("ids", [[]])[0]
        docs = raw.get("documents", [[]])[0]
        metas = raw.get("metadatas", [[]])[0]
        dists = raw.get("distances", [[]])[0]

        results = []
        for i, doc_id in enumerate(ids):
            distance = dists[i] if i < len(dists) else 0.5
            relevance = max(0.0, 1.0 - distance / 2.0) if distance else 0.5
            results.append({
                "id": doc_id,
                "text": docs[i] if i < len(docs) else "",
                "metadata": metas[i] if i < len(metas) else {},
                "relevance": relevance,
            })
        return results

    def _is_ambiguous(self, text: str) -> bool:
        """Check if text is too short or too vague for keyword analysis."""
        words = text.lower().split()
        if len(words) < 3:
            return True
        vague = {"something", "stuff", "things", "it", "that", "this"}
        if all(w in vague for w in words):
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Get memory orchestrator statistics."""
        return {
            "memory_types": [mt.value for mt in MemoryType],
            "active_types": len(MemoryType),
        }
