"""
NEXUS Memory Service — ChromaDB-backed vector memory with 6 namespaces.

This is the central memory service for NEXUS, combining the best of:
  - GenericAgent's 5-tier memory (L0-L5)
  - APEX's 6-layer hybrid memory with Knowledge Graph
  - Hermes Agent's skill crystallization storage

Namespaces:
  - conversations : Chat history and session context (L5 Session Archive)
  - episodes      : Episodic memory — chronological experience journal (L2)
  - knowledge     : Semantic memory — distilled, searchable facts (L3)
  - skills        : Procedural memory — crystallized skills/SOPs (L3)
  - identity      : Identity memory — user profile, preferences, persona (L0)
  - code          : Code knowledge graph — indexed codebase knowledge

All operations are async-compatible and use ChromaDB's PersistentClient.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from nexus.core.config import get_settings
from nexus.core.exceptions import (
    MemoryNamespaceError,
    MemorySearchError,
    MemoryStoreError,
)

logger = logging.getLogger(__name__)

# ── Connection Pooling ────────────────────────────────────────────

_client_cache: dict[str, chromadb.ClientAPI] = {}
_cache_lock = asyncio.Lock()


def _get_cached_client(persist_dir: str) -> chromadb.ClientAPI:
    """
    Get or create a cached ChromaDB client for the given persist_dir.
    Avoids recreating clients on every MCP tool call.
    Falls back to ephemeral in-memory client on persistent storage errors.
    """
    global _client_cache

    if persist_dir not in _client_cache:
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        try:
            _client_cache[persist_dir] = chromadb.PersistentClient(
                path=persist_dir,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                ),
            )
            # Force a quick operation to verify the client works
            _client_cache[persist_dir].heartbeat()
            logger.debug("Created new ChromaDB persistent client for: %s", persist_dir)
        except Exception as exc:
            logger.warning("ChromaDB persistent client failed (%s), falling back to ephemeral client", exc)
            _client_cache[persist_dir] = chromadb.EphemeralClient(
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                ),
            )
            logger.debug("Created fallback ChromaDB ephemeral client")

    return _client_cache[persist_dir]


# Valid namespace identifiers
VALID_NAMESPACES = frozenset([
    "conversations",
    "episodes",
    "knowledge",
    "skills",
    "identity",
    "code",
])

# Metadata fields that are automatically added to every stored document
AUTO_METADATA_FIELDS = frozenset([
    "created_at",
    "updated_at",
    "namespace",
    "doc_hash",
    "source",
])


class NexusMemoryService:
    """
    Central vector memory service for NEXUS.

    Uses ChromaDB PersistentClient with namespace-isolated collections.
    Each namespace maps to a ChromaDB collection with its own embedding space.

    Usage:
        service = NexusMemoryService()
        await service.store("Important fact about AI", namespace="knowledge")
        results = await service.search("AI facts", namespace="knowledge", top_k=5)
    """

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        client: Optional[chromadb.ClientAPI] = None,
    ):
        """
        Initialize the memory service.

        Args:
            persist_dir: Directory for ChromaDB persistence. Defaults to config value.
            client: Optional pre-configured ChromaDB client (useful for testing).
        """
        settings = get_settings()
        self.persist_dir = persist_dir or settings.chroma_persist_dir

        if client is not None:
            self.client = client
        else:
            # Use cached client to avoid recreating on every call
            self.client = _get_cached_client(self.persist_dir)

        self._collections: dict[str, chromadb.Collection] = {}
        self._lock = asyncio.Lock()

    def _get_collection(self, namespace: str) -> chromadb.Collection:
        """
        Get or create a ChromaDB collection for the given namespace.

        Args:
            namespace: One of VALID_NAMESPACES.

        Returns:
            The ChromaDB collection for that namespace.

        Raises:
            MemoryNamespaceError: If namespace is not valid.
        """
        if namespace not in VALID_NAMESPACES:
            raise MemoryNamespaceError(
                namespace=namespace,
                valid_namespaces=sorted(VALID_NAMESPACES),
            )

        if namespace not in self._collections:
            self._collections[namespace] = self.client.get_or_create_collection(
                name=f"nexus_{namespace}",
                metadata={
                    "hnsw:space": "cosine",
                    "description": f"NEXUS {namespace} memory namespace",
                },
            )
            logger.debug("Created/loaded collection for namespace: %s", namespace)

        return self._collections[namespace]

    @staticmethod
    def _compute_hash(text: str) -> str:
        """Compute SHA-256 hash of text for deduplication."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    async def store(
        self,
        text: str,
        metadata: Optional[dict[str, Any]] = None,
        namespace: str = "knowledge",
        doc_id: Optional[str] = None,
    ) -> str:
        """
        Store a document in the specified namespace.

        Args:
            text: The document text to store.
            metadata: Optional metadata dict. Auto-fields (created_at, namespace, doc_hash)
                      are added automatically and should not be provided.
            namespace: Target namespace (default: "knowledge").
            doc_id: Optional document ID. Auto-generated UUID if not provided.

        Returns:
            The document ID.

        Raises:
            MemoryStoreError: If the store operation fails.
            MemoryNamespaceError: If the namespace is invalid.
        """
        try:
            collection = self._get_collection(namespace)
        except MemoryNamespaceError:
            raise
        except Exception as exc:
            raise MemoryStoreError(namespace, str(exc)) from exc

        now = datetime.now(timezone.utc).isoformat()
        doc_hash = self._compute_hash(text)

        effective_metadata = {
            "created_at": now,
            "updated_at": now,
            "namespace": namespace,
            "doc_hash": doc_hash,
            "source": metadata.get("source", "user") if metadata else "user",
        }

        if metadata:
            for key, value in metadata.items():
                if key not in AUTO_METADATA_FIELDS:
                    effective_metadata[key] = str(value)

        document_id = doc_id or f"{namespace}_{uuid.uuid4().hex[:12]}"

        try:
            async with self._lock:
                collection.add(
                    documents=[text],
                    metadatas=[effective_metadata],
                    ids=[document_id],
                )
            logger.info(
                "Stored document %s in namespace '%s' (hash=%s)",
                document_id, namespace, doc_hash,
            )
            return document_id
        except chromadb.errors.IDAlreadyExistsError:
            logger.warning("Document %s already exists in '%s', updating instead", document_id, namespace)
            async with self._lock:
                effective_metadata["updated_at"] = now
                collection.update(
                    documents=[text],
                    metadatas=[effective_metadata],
                    ids=[document_id],
                )
            return document_id
        except Exception as exc:
            raise MemoryStoreError(namespace, str(exc)) from exc

    async def search(
        self,
        query: str,
        top_k: int = 5,
        namespace: str = "knowledge",
        where: Optional[dict[str, Any]] = None,
        include: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Search for documents in the specified namespace.

        Args:
            query: The search query text.
            top_k: Number of results to return (default: 5).
            namespace: Target namespace.
            where: Optional ChromaDB where filter (metadata filtering).
            include: Fields to include in results (default: documents, metadatas, distances).

        Returns:
            Dict with keys: ids, documents, metadatas, distances.

        Raises:
            MemorySearchError: If the search operation fails.
            MemoryNamespaceError: If the namespace is invalid.
        """
        try:
            collection = self._get_collection(namespace)
        except MemoryNamespaceError:
            raise
        except Exception as exc:
            raise MemorySearchError(namespace, str(exc)) from exc

        if include is None:
            include = ["documents", "metadatas", "distances"]

        try:
            total = collection.count()
            n_results = min(top_k, total) if total > 0 else 1
            query_params: dict[str, Any] = {
                "query_texts": [query],
                "n_results": n_results,
                "include": include,
            }
            if where is not None:
                query_params["where"] = where

            results = collection.query(**query_params)

            logger.info(
                "Search in '%s' for '%s' returned %d results",
                namespace, query[:50], len(results.get("ids", [[]])[0]),
            )
            return results
        except Exception as exc:
            raise MemorySearchError(namespace, str(exc)) from exc

    async def update(
        self,
        doc_id: str,
        text: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        namespace: str = "knowledge",
    ) -> bool:
        """
        Update an existing document.

        Args:
            doc_id: The document ID to update.
            text: New text (if provided).
            metadata: New/updated metadata fields.
            namespace: Target namespace.

        Returns:
            True if update succeeded.

        Raises:
            MemoryStoreError: If the update fails.
        """
        try:
            collection = self._get_collection(namespace)
        except MemoryNamespaceError:
            raise
        except Exception as exc:
            raise MemoryStoreError(namespace, str(exc)) from exc

        update_params: dict[str, Any] = {"ids": [doc_id]}
        if text is not None:
            update_params["documents"] = [text]
            update_params["metadatas"] = [{
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "doc_hash": self._compute_hash(text),
                **(metadata or {}),
            }]
        elif metadata is not None:
            existing = collection.get(ids=[doc_id], include=["metadatas"])
            if existing["metadatas"]:
                merged = {**existing["metadatas"][0], **metadata}
                merged["updated_at"] = datetime.now(timezone.utc).isoformat()
                update_params["metadatas"] = [merged]
            else:
                update_params["metadatas"] = [metadata]

        try:
            async with self._lock:
                collection.update(**update_params)
            logger.info("Updated document %s in namespace '%s'", doc_id, namespace)
            return True
        except Exception as exc:
            raise MemoryStoreError(namespace, str(exc)) from exc

    async def delete(
        self,
        doc_id: str,
        namespace: str = "knowledge",
    ) -> bool:
        """
        Delete a document from the specified namespace.

        Args:
            doc_id: The document ID to delete.
            namespace: Target namespace.

        Returns:
            True if deletion succeeded.

        Raises:
            MemoryStoreError: If the delete operation fails.
        """
        try:
            collection = self._get_collection(namespace)
        except MemoryNamespaceError:
            raise
        except Exception as exc:
            raise MemoryStoreError(namespace, str(exc)) from exc

        try:
            async with self._lock:
                collection.delete(ids=[doc_id])
            logger.info("Deleted document %s from namespace '%s'", doc_id, namespace)
            return True
        except Exception as exc:
            raise MemoryStoreError(namespace, str(exc)) from exc

    async def count(self, namespace: str = "knowledge") -> int:
        """Return the number of documents in a namespace."""
        try:
            collection = self._get_collection(namespace)
            return collection.count()
        except Exception as exc:
            raise MemorySearchError(namespace, str(exc)) from exc

    async def list_documents(
        self,
        namespace: str = "knowledge",
        limit: int = 100,
        where: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        List documents in a namespace (without query embedding).

        Args:
            namespace: Target namespace.
            limit: Maximum number of documents to return.
            where: Optional metadata filter.

        Returns:
            Dict with ids, documents, metadatas.
        """
        try:
            collection = self._get_collection(namespace)
        except MemoryNamespaceError:
            raise

        params: dict[str, Any] = {
            "limit": limit,
            "include": ["documents", "metadatas"],
        }
        if where is not None:
            params["where"] = where

        return collection.get(**params)

    async def reset_namespace(self, namespace: str) -> bool:
        """
        Delete all documents in a namespace.

        Args:
            namespace: Target namespace.

        Returns:
            True if reset succeeded.
        """
        try:
            collection = self._get_collection(namespace)
            all_ids = collection.get(include=[])["ids"]
            if all_ids:
                collection.delete(ids=all_ids)
            logger.warning("Reset namespace '%s' — deleted %d documents", namespace, len(all_ids))
            return True
        except Exception as exc:
            raise MemoryStoreError(namespace, str(exc)) from exc
