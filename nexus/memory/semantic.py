"""
L3 Semantic Memory — Distilled, searchable knowledge facts.

Stores structured knowledge that has been distilled from experiences,
documents, and research. This is the RAG-accessible knowledge base
where verified facts, concepts, and relationships live.

Inspired by GenericAgent's global facts layer and ChromaDB's
native document search capabilities.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from nexus.memory.chroma_service import NexusMemoryService

logger = logging.getLogger(__name__)


class SemanticMemory:
    """
    L3 Semantic Memory — stores and retrieves knowledge facts.

    Knowledge is stored as text documents with rich metadata in
    the 'knowledge' ChromaDB namespace. Each fact has a source,
    confidence level, and optional tags.

    Usage:
        semantic = SemanticMemory(memory_service)
        await semantic.add_fact(
            text="Python 3.12 was released in October 2023",
            source="python.org",
            confidence=0.95,
            tags=["python", "release"],
        )
        results = await semantic.query("latest Python release")
    """

    def __init__(self, memory_service: NexusMemoryService):
        self.memory = memory_service

    async def add_fact(
        self,
        text: str,
        source: str = "unknown",
        confidence: float = 1.0,
        tags: Optional[list[str]] = None,
        fact_id: Optional[str] = None,
    ) -> str:
        """
        Add a knowledge fact to semantic memory.

        Args:
            text: The fact text.
            source: Origin of this fact (URL, document name, etc.).
            confidence: Confidence score 0.0-1.0.
            tags: Optional categorization tags.
            fact_id: Optional ID for deduplication.

        Returns:
            Document ID.
        """
        metadata = {
            "source": source,
            "confidence": str(confidence),
            "type": "fact",
            "tags": ",".join(tags) if tags else "",
        }
        doc_id = await self.memory.store(
            text=text,
            metadata=metadata,
            namespace="knowledge",
            doc_id=fact_id,
        )
        logger.info("Added fact to semantic memory: %s (source=%s)", text[:50], source)
        return doc_id

    async def add_document_chunk(
        self,
        text: str,
        source_doc: str,
        chunk_index: int,
        total_chunks: int,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Add a chunk of an ingested document.

        This is used by the RAG pipeline to store document chunks
        with their source information for citation.

        Args:
            text: Chunk text.
            source_doc: Name/URL of the source document.
            chunk_index: Index of this chunk in the document.
            total_chunks: Total number of chunks in the document.
            metadata: Additional metadata.

        Returns:
            Document ID.
        """
        chunk_metadata = {
            "source": source_doc,
            "type": "document_chunk",
            "chunk_index": str(chunk_index),
            "total_chunks": str(total_chunks),
            **(metadata or {}),
        }
        doc_id = await self.memory.store(
            text=text,
            metadata=chunk_metadata,
            namespace="knowledge",
        )
        return doc_id

    async def query(
        self,
        query: str,
        top_k: int = 5,
        source_filter: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> list[dict[str, Any]]:
        """
        Query semantic memory for relevant facts.

        Args:
            query: Natural language query.
            top_k: Number of results.
            source_filter: Only return facts from this source.
            min_confidence: Minimum confidence threshold.

        Returns:
            List of matching facts with text, metadata, and distance.
        """
        where = {}
        if source_filter:
            where["source"] = source_filter

        results = await self.memory.search(
            query=query,
            namespace="knowledge",
            top_k=top_k,
            where=where if where else None,
        )

        facts = []
        for i, doc_id in enumerate(results.get("ids", [[]])[0]):
            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            confidence = float(meta.get("confidence", "1.0"))
            if confidence < min_confidence:
                continue
            facts.append({
                "id": doc_id,
                "text": results["documents"][0][i] if results.get("documents") else "",
                "metadata": meta,
                "distance": results["distances"][0][i] if results.get("distances") else 0.0,
                "confidence": confidence,
            })
        return facts

    async def remove_fact(self, fact_id: str) -> bool:
        """Remove a fact from semantic memory."""
        return await self.memory.delete(fact_id, namespace="knowledge")

    async def update_fact(
        self,
        fact_id: str,
        text: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Update an existing fact."""
        return await self.memory.update(fact_id, text=text, metadata=metadata, namespace="knowledge")

    async def get_stats(self) -> dict[str, Any]:
        """Get semantic memory statistics."""
        total = await self.memory.count(namespace="knowledge")
        return {
            "total_facts": total,
            "namespace": "knowledge",
        }
