"""
NEXUS Memory Compactor — Intelligent memory compression and quality management.

Features:
  - Automatic compression of long conversations
  - Detection of contradictions in stored knowledge
  - Targeted forgetting of stale/low-access entries
  - Memory quality scoring
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CompressionResult:
    """Result of a memory compression operation."""
    original_count: int
    compressed_count: int
    tokens_saved: int
    contradictions_found: int = 0


class MemoryCompactor:
    """
    Manages memory quality through compression, deduplication,
    contradiction detection, and targeted forgetting.

    Usage:
        compactor = MemoryCompactor(memory_service)
        result = await compactor.compress_namespace("conversations")
    """

    def __init__(self, memory_service: Any = None):
        self._service = memory_service

    def set_service(self, service: Any) -> None:
        """Set the memory service reference."""
        self._service = service

    async def compress_namespace(
        self,
        namespace: str,
        max_entries: int = 100,
        min_age_hours: float = 24.0,
    ) -> CompressionResult:
        """
        Compress a memory namespace by summarizing old entries.

        Args:
            namespace: The namespace to compress.
            max_entries: Maximum entries before triggering compression.
            min_age_hours: Minimum age of entries before they can be compressed.

        Returns:
            CompressionResult with stats.
        """
        if not self._service:
            return CompressionResult(0, 0, 0)

        try:
            # Get current count
            count = await self._service.count(namespace=namespace)
            if count <= max_entries:
                return CompressionResult(count, count, 0)

            # Get all documents
            docs = await self._service.list_documents(namespace=namespace, limit=count)
            ids = docs.get("ids", [])
            documents = docs.get("documents", [])
            metadatas = docs.get("metadatas", [])

            if not ids:
                return CompressionResult(0, 0, 0)

            # Find old entries to compress
            now = time.time()
            cutoff = now - (min_age_hours * 3600)
            old_entries = []

            for i, (doc_id, doc, meta) in enumerate(zip(ids, documents, metadatas)):
                created = meta.get("created_at", "") if meta else ""
                access_count = int(meta.get("access_count", 0)) if meta else 0

                # Check age
                try:
                    from datetime import datetime
                    if created:
                        created_time = datetime.fromisoformat(created).timestamp()
                        if created_time > cutoff:
                            continue  # Too recent
                except (ValueError, TypeError):
                    pass

                old_entries.append((doc_id, doc, access_count))

            if not old_entries:
                return CompressionResult(count, count, 0)

            # Sort by access count (least accessed first)
            old_entries.sort(key=lambda x: x[2])

            # Compress: merge multiple old entries into a summary
            entries_to_compress = old_entries[:len(old_entries) // 2]
            if entries_to_compress:
                combined_text = "\n---\n".join(doc for _, doc, _ in entries_to_compress)

                # Create compressed summary
                summary = self._create_summary(combined_text, namespace)

                # Store the compressed version
                await self._service.store(
                    text=summary,
                    metadata={
                        "source": "compactor",
                        "compressed_from": len(entries_to_compress),
                        "compression_time": time.time(),
                    },
                    namespace=namespace,
                )

                # Delete the original entries
                for doc_id, _, _ in entries_to_compress:
                    await self._service.delete(doc_id=doc_id, namespace=namespace)

                new_count = await self._service.count(namespace=namespace)
                tokens_saved = sum(len(doc.split()) for _, doc, _ in entries_to_compress) - len(summary.split())

                logger.info(
                    "Compressed %d entries in '%s' (saved ~%d tokens)",
                    len(entries_to_compress), namespace, tokens_saved,
                )

                return CompressionResult(
                    original_count=count,
                    compressed_count=new_count,
                    tokens_saved=tokens_saved,
                )

            return CompressionResult(count, count, 0)

        except Exception as exc:
            logger.error("Compression failed for '%s': %s", namespace, exc)
            return CompressionResult(0, 0, 0)

    async def detect_contradictions(
        self,
        namespace: str = "knowledge",
    ) -> list[dict[str, Any]]:
        """
        Detect potential contradictions in stored knowledge.

        Returns:
            List of contradiction pairs found.
        """
        # This is a simplified implementation
        # A production version would use LLM-based contradiction detection
        contradictions = []

        try:
            if not self._service:
                return contradictions

            docs = await self._service.list_documents(namespace=namespace, limit=200)
            documents = docs.get("documents", [])

            # Simple heuristic: look for negation patterns
            negation_words = ["not", "never", "no", "false", "incorrect", "wrong", "pas", "non", "jamais"]

            for i, doc1 in enumerate(documents):
                for j, doc2 in enumerate(documents):
                    if i >= j:
                        continue

                    # Check if documents share similar topic but have negation differences
                    doc1_lower = doc1.lower()
                    doc2_lower = doc2.lower()

                    # Simple similarity check (word overlap)
                    words1 = set(doc1_lower.split())
                    words2 = set(doc2_lower.split())
                    overlap = words1 & words2

                    if len(overlap) > 5:
                        # Check for negation in one but not the other
                        has_neg1 = any(w in doc1_lower for w in negation_words)
                        has_neg2 = any(w in doc2_lower for w in negation_words)

                        if has_neg1 != has_neg2:
                            contradictions.append({
                                "doc1": doc1[:200],
                                "doc2": doc2[:200],
                                "overlap_words": len(overlap),
                                "type": "negation_mismatch",
                            })

        except Exception as exc:
            logger.error("Contradiction detection failed: %s", exc)

        return contradictions

    def _create_summary(self, text: str, namespace: str) -> str:
        """Create a compressed summary of text."""
        # Simple compression: take key sentences
        sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 20]

        if not sentences:
            return text[:1000]

        # Take first N sentences (most important in chronological order)
        max_sentences = min(10, len(sentences))
        summary = ". ".join(sentences[:max_sentences])

        # Add metadata
        summary = f"[Compressed {len(sentences)} entries from {namespace}]\n\n{summary}"

        return summary

    async def run_maintenance(self) -> dict[str, Any]:
        """
        Run full maintenance cycle on all namespaces.

        Returns:
            Summary of maintenance operations.
        """
        results = {}
        total_saved = 0

        for ns in ["conversations", "episodes", "knowledge", "skills", "identity", "code"]:
            try:
                result = await self.compress_namespace(ns)
                results[ns] = {
                    "original": result.original_count,
                    "compressed": result.compressed_count,
                    "tokens_saved": result.tokens_saved,
                    "contradictions": result.contradictions_found,
                }
                total_saved += result.tokens_saved
            except Exception as exc:
                results[ns] = {"error": str(exc)}

        # Check for contradictions in knowledge namespace
        contradictions = await self.detect_contradictions("knowledge")
        results["contradictions_found"] = len(contradictions)

        logger.info("Memory maintenance complete. Total tokens saved: %d", total_saved)
        return results
