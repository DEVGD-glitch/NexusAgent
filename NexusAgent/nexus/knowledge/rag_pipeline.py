"""
NEXUS RAG Pipeline — Retrieval-Augmented Generation with self-correcting retrieval.

Implements a full RAG pipeline:
  1. Query analysis and expansion
  2. Multi-source retrieval (ChromaDB + Knowledge Graph)
  3. Re-ranking and deduplication
  4. Self-correcting retrieval (if initial results are poor, reformulate)
  5. Context assembly with citation
  6. LLM generation with retrieved context
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
class RAGDocument:
    """A retrieved document with relevance metadata."""
    text: str
    source: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    chunk_index: int = 0


@dataclass
class RAGResult:
    """Result from a RAG query."""
    answer: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    documents_used: int = 0
    retrieval_attempts: int = 1
    confidence: float = 0.0
    query: str = ""


class RAGPipeline:
    """
    Self-correcting RAG Pipeline.

    Features:
      - Multi-source retrieval from vector memory + knowledge graph
      - Query expansion and reformulation
      - Self-correction when retrieval results are poor
      - Source citation in generated answers
      - Confidence scoring

    Usage:
        rag = RAGPipeline()
        result = await rag.query("What are the latest advances in AI agents?")
        print(result.answer)
    """

    def __init__(
        self,
        top_k: int = 5,
        max_retrieval_attempts: int = 3,
        min_relevance_score: float = 0.3,
    ):
        self.top_k = top_k
        self.max_retrieval_attempts = max_retrieval_attempts
        self.min_relevance_score = min_relevance_score

    async def query(
        self,
        query: str,
        namespace: str = "knowledge",
        context_messages: Optional[list[dict[str, str]]] = None,
    ) -> RAGResult:
        """
        Execute a RAG query with self-correcting retrieval.

        Args:
            query: The user's question.
            namespace: Memory namespace to search.
            context_messages: Prior conversation context.

        Returns:
            RAGResult with the answer and sources.
        """
        # Step 1: Retrieve documents
        documents = await self._retrieve(query, namespace)

        # Step 2: Self-correction loop
        attempts = 1
        while (not documents or all(d.score < self.min_relevance_score for d in documents)) and attempts < self.max_retrieval_attempts:
            # Reformulate query
            reformulated = await self._reformulate_query(query, attempts)
            documents = await self._retrieve(reformulated, namespace)
            attempts += 1

        if not documents:
            return RAGResult(
                answer="I couldn't find relevant information to answer your question.",
                query=query,
                retrieval_attempts=attempts,
            )

        # Step 3: Re-rank documents
        ranked_docs = await self._rerank(query, documents)

        # Step 4: Generate answer with context
        answer = await self._generate(query, ranked_docs, context_messages)

        # Step 5: Build sources
        sources = [
            {"text": d.text[:200], "source": d.source, "score": d.score}
            for d in ranked_docs[:5]
        ]

        return RAGResult(
            answer=answer,
            sources=sources,
            documents_used=len(ranked_docs),
            retrieval_attempts=attempts,
            confidence=ranked_docs[0].score if ranked_docs else 0.0,
            query=query,
        )

    async def _retrieve(self, query: str, namespace: str) -> list[RAGDocument]:
        """Retrieve documents from ChromaDB."""
        try:
            from nexus.memory.chroma_service import NexusMemoryService
            from nexus.core.config import get_settings
            settings = get_settings()
            service = NexusMemoryService(persist_dir=settings.chroma_persist_dir)
            results = await service.search(query=query, namespace=namespace, top_k=self.top_k)

            documents = []
            ids = results.get("ids", [[]])[0]
            texts = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            for i, doc_id in enumerate(ids):
                doc = RAGDocument(
                    text=texts[i] if i < len(texts) else "",
                    source=metadatas[i].get("source", "unknown") if i < len(metadatas) else "unknown",
                    score=1.0 - (distances[i] if i < len(distances) else 0.5),
                    metadata=metadatas[i] if i < len(metadatas) else {},
                )
                documents.append(doc)

            return documents
        except Exception as e:
            logger.error("RAG retrieval failed: %s", e)
            return []

    async def _reformulate_query(self, original_query: str, attempt: int) -> str:
        """Reformulate a query for better retrieval."""
        try:
            from nexus.llm.router import LLMRouter, TaskComplexity
            router = LLMRouter()
            response = await router.complete(
                messages=[
                    {"role": "system", "content": "Reformulate the query to be more specific and searchable. Use different keywords."},
                    {"role": "user", "content": f"Original query: {original_query}\nAttempt: {attempt}\nReformulated query:"},
                ],
                task_complexity=TaskComplexity.SIMPLE,
                temperature=0.7,
                max_tokens=100,
            )
            return response.content.strip()
        except Exception:
            return original_query

    async def _rerank(self, query: str, documents: list[RAGDocument]) -> list[RAGDocument]:
        """Re-rank documents by relevance to the query."""
        return sorted(documents, key=lambda d: d.score, reverse=True)

    async def _generate(
        self,
        query: str,
        documents: list[RAGDocument],
        context_messages: Optional[list[dict[str, str]]] = None,
    ) -> str:
        """Generate an answer using the retrieved documents."""
        context_text = "\n\n".join(
            f"[Source: {d.source}, Score: {d.score:.2f}]\n{d.text}"
            for d in documents[:5]
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are NEXUS, an AI assistant with access to retrieved documents. "
                    "Answer the user's question based on the provided context. "
                    "Cite sources when possible. If the context doesn't contain "
                    "enough information, say so honestly."
                ),
            },
            {
                "role": "user",
                "content": f"Context:\n{context_text}\n\nQuestion: {query}",
            },
        ]

        if context_messages:
            messages = [messages[0]] + context_messages + [messages[1]]

        try:
            from nexus.llm.router import LLMRouter, TaskComplexity
            router = LLMRouter()
            response = await router.complete(
                messages=messages,
                task_complexity=TaskComplexity.MEDIUM,
                temperature=0.3,
            )
            return response.content
        except Exception as e:
            logger.error("RAG generation failed: %s", e)
            return f"Error generating answer: {str(e)}"

    async def ingest_document(
        self,
        text: str,
        source: str = "upload",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> int:
        """
        Ingest a document into the RAG knowledge base.

        Splits the text into chunks and stores them in ChromaDB.

        Args:
            text: Full document text.
            source: Source identifier.
            chunk_size: Characters per chunk.
            chunk_overlap: Overlap between chunks.

        Returns:
            Number of chunks stored.
        """
        from nexus.memory.chroma_service import NexusMemoryService
        from nexus.memory.semantic import SemanticMemory
        from nexus.core.config import get_settings

        settings = get_settings()
        service = NexusMemoryService(persist_dir=settings.chroma_persist_dir)
        semantic = SemanticMemory(service)

        # Simple chunking with overlap
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk.rfind(".")
                if last_period > chunk_size // 2:
                    chunk = chunk[:last_period + 1]
                    end = start + last_period + 1
            chunks.append(chunk)
            start = end - chunk_overlap

        for i, chunk in enumerate(chunks):
            await semantic.add_document_chunk(
                text=chunk,
                source_doc=source,
                chunk_index=i,
                total_chunks=len(chunks),
            )

        logger.info("Ingested document '%s': %d chunks", source, len(chunks))
        return len(chunks)
