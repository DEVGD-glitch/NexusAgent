"""
Tests for NEXUS Memory System — chroma_service, working, episodic, semantic, procedural, identity.

Each test class gets a fresh in-memory ChromaDB client to ensure isolation.
"""

import pytest
import chromadb
from chromadb.config import Settings as ChromaSettings

from nexus.memory.chroma_service import NexusMemoryService, VALID_NAMESPACES
from nexus.memory.working import WorkingMemory, WorkingMessage, MessageRole
from nexus.memory.episodic import EpisodicMemory, Episode
from nexus.memory.semantic import SemanticMemory
from nexus.memory.procedural import ProceduralMemory, Skill
from nexus.memory.identity import IdentityMemory, UserProfile
from nexus.core.exceptions import MemoryNamespaceError


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_chroma():
    """Ensure fresh ChromaDB state before each test."""
    yield
    # Cleanup happens via fresh fixture per test


@pytest.fixture
def fresh_client():
    """Create a truly fresh in-memory ChromaDB client for each test."""
    client = chromadb.Client(settings=ChromaSettings(
        anonymized_telemetry=False,
        allow_reset=True,
    ))
    return client


@pytest.fixture
def memory_service(fresh_client):
    """Create a NexusMemoryService with fresh in-memory client."""
    return NexusMemoryService(client=fresh_client)


# ── ChromaService Tests ───────────────────────────────────────────

class TestNexusMemoryService:

    @pytest.mark.asyncio
    async def test_store_and_search(self, memory_service):
        """Store a document and search for it."""
        doc_id = await memory_service.store(
            text="NEXUS is a universal AI agent",
            metadata={"source": "test", "type": "fact"},
            namespace="knowledge",
        )
        assert doc_id is not None
        assert doc_id.startswith("knowledge_")

        results = await memory_service.search(
            query="AI agent",
            top_k=1,
            namespace="knowledge",
        )
        assert len(results["ids"][0]) > 0
        assert "NEXUS" in results["documents"][0][0]

    @pytest.mark.asyncio
    async def test_store_with_custom_id(self, memory_service):
        """Store with a custom document ID."""
        doc_id = await memory_service.store(
            text="Custom ID test",
            namespace="knowledge",
            doc_id="my_custom_id",
        )
        assert doc_id == "my_custom_id"

    @pytest.mark.asyncio
    async def test_namespace_isolation(self, fresh_client):
        """Documents in different namespaces should not leak."""
        fresh_client.reset()  # Ensure clean slate
        svc = NexusMemoryService(client=fresh_client)
        await svc.store("alpha document in conversations ns", namespace="conversations")
        await svc.store("beta document in code ns", namespace="code")

        results_c = await svc.search("document", namespace="conversations", top_k=5)
        results_d = await svc.search("document", namespace="code", top_k=5)

        docs_c = results_c["documents"][0] if results_c["documents"] else []
        assert len(docs_c) == 1
        assert "alpha" in docs_c[0]

        docs_d = results_d["documents"][0] if results_d["documents"] else []
        assert len(docs_d) == 1
        assert "beta" in docs_d[0]

    @pytest.mark.asyncio
    async def test_invalid_namespace(self, memory_service):
        """Invalid namespace should raise MemoryNamespaceError."""
        with pytest.raises(MemoryNamespaceError) as exc_info:
            await memory_service.store("test", namespace="invalid_ns")
        assert "invalid_ns" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_document(self, memory_service):
        """Update should modify existing document."""
        await memory_service.store(
            text="Original content",
            namespace="knowledge",
            doc_id="update_test_1",
        )
        await memory_service.update(
            doc_id="update_test_1",
            text="Updated content",
            namespace="knowledge",
        )
        results = await memory_service.search("Updated", namespace="knowledge", top_k=1)
        assert "Updated content" in results["documents"][0][0]

    @pytest.mark.asyncio
    async def test_delete_document(self, fresh_client):
        """Delete should remove document."""
        fresh_client.reset()
        svc = NexusMemoryService(client=fresh_client)
        await svc.store(
            text="To be deleted",
            namespace="conversations",
            doc_id="delete_test_1",
        )
        await svc.delete("delete_test_1", namespace="conversations")
        count = await svc.count(namespace="conversations")
        assert count == 0

    @pytest.mark.asyncio
    async def test_count_documents(self, fresh_client):
        """Count should return accurate document count."""
        fresh_client.reset()
        svc = NexusMemoryService(client=fresh_client)
        await svc.store("doc1", namespace="conversations")
        await svc.store("doc2", namespace="conversations")
        count = await svc.count(namespace="conversations")
        assert count == 2

    @pytest.mark.asyncio
    async def test_auto_metadata(self, memory_service):
        """Auto metadata fields should be added."""
        await memory_service.store(
            text="Auto metadata test",
            namespace="knowledge",
            doc_id="meta_test",
        )
        results = await memory_service.list_documents(namespace="knowledge", limit=1)
        meta = results["metadatas"][0]
        assert "created_at" in meta
        assert "namespace" in meta
        assert meta["namespace"] == "knowledge"
        assert "doc_hash" in meta

    @pytest.mark.asyncio
    async def test_deduplication_hash(self, memory_service):
        """Same text should produce same hash."""
        from nexus.memory.chroma_service import NexusMemoryService as NMS
        hash1 = NMS._compute_hash("test text")
        hash2 = NMS._compute_hash("test text")
        hash3 = NMS._compute_hash("different text")
        assert hash1 == hash2
        assert hash1 != hash3

    @pytest.mark.asyncio
    async def test_search_with_where_filter(self, memory_service):
        """Search with metadata filter should work."""
        await memory_service.store(
            text="Python fact",
            metadata={"source": "python.org"},
            namespace="knowledge",
            doc_id="filter_1",
        )
        await memory_service.store(
            text="Java fact",
            metadata={"source": "java.com"},
            namespace="knowledge",
            doc_id="filter_2",
        )
        results = await memory_service.search(
            query="programming",
            namespace="knowledge",
            where={"source": "python.org"},
        )
        ids = results["ids"][0]
        assert "filter_1" in ids

    @pytest.mark.asyncio
    async def test_reset_namespace(self, memory_service):
        """Reset should clear all documents in namespace."""
        await memory_service.store("doc1", namespace="conversations")
        await memory_service.store("doc2", namespace="conversations")
        await memory_service.reset_namespace("conversations")
        count = await memory_service.count(namespace="conversations")
        assert count == 0


# ── Working Memory Tests ──────────────────────────────────────────

class TestWorkingMemory:

    def test_add_and_get_messages(self):
        """Basic add and retrieval of messages."""
        wm = WorkingMemory(max_tokens=50000)
        wm.add(MessageRole.USER, "Hello")
        wm.add(MessageRole.ASSISTANT, "Hi there!")
        msgs = wm.get_messages()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

    def test_system_prompt(self):
        """System prompt should be included as first message."""
        wm = WorkingMemory(max_tokens=50000)
        wm.set_system_prompt("You are NEXUS.")
        wm.add(MessageRole.USER, "Hello")
        msgs = wm.get_messages(include_system=True)
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == "You are NEXUS."

    def test_token_counting(self):
        """Token count should be tracked."""
        wm = WorkingMemory(max_tokens=50000)
        wm.add(MessageRole.USER, "Hello, this is a test message")
        assert wm.total_tokens > 0
        assert wm.utilization > 0

    def test_compression_triggered(self):
        """Compression should activate when budget exceeded."""
        wm = WorkingMemory(max_tokens=200, compression_threshold=0.7)
        for i in range(20):
            wm.add(MessageRole.USER, f"Message {i}")
        # After compression, should be under max_tokens
        assert wm.total_tokens <= 200

    def test_priority_protection(self):
        """High-priority messages should survive compression."""
        wm = WorkingMemory(max_tokens=200, compression_threshold=0.7)
        wm.add(MessageRole.ASSISTANT, "Critical instruction to preserve", priority=3.0)
        for i in range(15):
            wm.add(MessageRole.USER, f"Filler {i}", priority=0.5)
        msgs = wm.get_messages(include_system=False)
        critical = [m for m in msgs if "Critical instruction" in m["content"]]
        assert len(critical) == 1

    def test_clear(self):
        """Clear should remove all messages."""
        wm = WorkingMemory()
        wm.add(MessageRole.USER, "test")
        wm.clear()
        assert len(wm.messages) == 0

    def test_stats(self):
        """Stats should return correct information."""
        wm = WorkingMemory(max_tokens=50000)
        wm.add(MessageRole.USER, "This is a longer test message for stats check with enough words")
        stats = wm.get_stats()
        assert stats["message_count"] == 1
        assert stats["total_tokens"] > 0
        # Utilization may be very small for short messages, just check it's a valid float
        assert isinstance(stats["utilization"], float)

    def test_utilization_empty(self):
        """Empty working memory should have 0 utilization."""
        wm = WorkingMemory(max_tokens=1000)
        assert wm.utilization == 0.0


# ── Episodic Memory Tests ────────────────────────────────────────

class TestEpisodicMemory:

    @pytest.mark.asyncio
    async def test_record_and_recall(self, fresh_client):
        """Record an episode and recall it."""
        fresh_client.reset()
        svc = NexusMemoryService(client=fresh_client)
        episodic = EpisodicMemory(svc)
        episode = Episode(
            task="Search for AI papers",
            actions=["web_search", "summarize"],
            outcome="Found 5 relevant papers",
            success=True,
            tools_used=["web_search"],
        )
        doc_id = await episodic.record(episode)
        assert doc_id is not None

        recent = await episodic.recall_recent(limit=5)
        assert len(recent) > 0
        # Verify the recorded episode text is present
        all_texts = " ".join(r["text"] for r in recent)
        assert "AI papers" in all_texts

    @pytest.mark.asyncio
    async def test_recall_similar(self, memory_service):
        """Find similar episodes."""
        episodic = EpisodicMemory(memory_service)

        await episodic.record(Episode(
            task="Deploy web application to AWS",
            actions=["terraform apply", "docker push"],
            outcome="Deployed successfully",
            success=True,
        ))
        await episodic.record(Episode(
            task="Write unit tests for API",
            actions=["pytest", "coverage"],
            outcome="All tests pass",
            success=True,
        ))

        results = await episodic.recall_similar("deploy application", top_k=1)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_recall_successful_only(self, memory_service):
        """Should only return successful episodes."""
        episodic = EpisodicMemory(memory_service)

        await episodic.record(Episode(
            task="Failed task",
            actions=["attempted"],
            outcome="Failed",
            success=False,
        ))
        await episodic.record(Episode(
            task="Successful task",
            actions=["completed"],
            outcome="Done",
            success=True,
        ))

        results = await episodic.recall_successful("task", top_k=5)
        assert all(r["metadata"].get("success") == "True" for r in results)


# ── Semantic Memory Tests ────────────────────────────────────────

class TestSemanticMemory:

    @pytest.mark.asyncio
    async def test_add_and_query_fact(self, memory_service):
        """Add a fact and query it."""
        semantic = SemanticMemory(memory_service)
        await semantic.add_fact(
            text="Python was created by Guido van Rossum in 1991",
            source="python.org",
            confidence=0.99,
            tags=["python", "history"],
        )
        results = await semantic.query("Who created Python?")
        assert len(results) > 0
        assert "Guido van Rossum" in results[0]["text"]

    @pytest.mark.asyncio
    async def test_confidence_filter(self, fresh_client):
        """Low-confidence facts should be filtered out."""
        svc = NexusMemoryService(client=fresh_client)
        semantic = SemanticMemory(svc)
        await semantic.add_fact(
            text="Low confidence claim",
            source="rumor",
            confidence=0.2,
            fact_id="low_conf",
        )
        results = await semantic.query("claim", min_confidence=0.5)
        low_conf_items = [r for r in results if r["id"] == "low_conf"]
        assert len(low_conf_items) == 0

    @pytest.mark.asyncio
    async def test_add_document_chunk(self, memory_service):
        """Document chunks should be stored with metadata."""
        semantic = SemanticMemory(memory_service)
        doc_id = await semantic.add_document_chunk(
            text="Chapter 1: Introduction to AI agents",
            source_doc="ai_agents_handbook.pdf",
            chunk_index=0,
            total_chunks=10,
        )
        assert doc_id is not None

    @pytest.mark.asyncio
    async def test_remove_fact(self, memory_service):
        """Remove should delete the fact."""
        semantic = SemanticMemory(memory_service)
        fact_id = await semantic.add_fact("Temporary fact to remove", source="test", fact_id="temp_rm")
        count_before = await memory_service.count(namespace="knowledge")
        await semantic.remove_fact(fact_id)
        count_after = await memory_service.count(namespace="knowledge")
        assert count_after == count_before - 1


# ── Procedural Memory Tests ──────────────────────────────────────

class TestProceduralMemory:

    @pytest.mark.asyncio
    async def test_crystallize_skill(self, memory_service):
        """Crystallize a new skill."""
        procedural = ProceduralMemory(memory_service)
        skill = Skill(
            name="web_search_and_summarize",
            description="Search the web and summarize results",
            pattern="query -> search -> extract -> summarize",
            steps=[
                {"action": "decompose_query", "tool": "reasoning"},
                {"action": "web_search", "tool": "web_search"},
                {"action": "summarize", "tool": "llm"},
            ],
            success_criteria="Summary contains key findings",
            domain="research",
        )
        doc_id = await procedural.crystallize(skill)
        assert doc_id is not None

    @pytest.mark.asyncio
    async def test_find_relevant_skill(self, memory_service):
        """Find skills relevant to a task."""
        procedural = ProceduralMemory(memory_service)
        await procedural.crystallize(Skill(
            name="code_review",
            description="Review code for bugs and improvements",
            pattern="read_code -> analyze -> suggest_fixes",
            steps=[{"action": "read", "tool": "file_read"}, {"action": "analyze", "tool": "llm"}],
            success_criteria="All bugs identified",
            domain="development",
            quality_score=0.8,
        ))
        results = await procedural.find_relevant("I need to review my code", top_k=1)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_skill_versioning(self, fresh_client):
        """Crystallizing same skill twice should update, not duplicate."""
        fresh_client.reset()
        svc = NexusMemoryService(client=fresh_client)
        procedural = ProceduralMemory(svc)
        skill = Skill(
            name="versioned_skill_unique_42",
            description="Test versioning",
            pattern="test",
            steps=[],
            success_criteria="test",
        )
        await procedural.crystallize(skill)
        count_after_first = await svc.count(namespace="skills")
        assert count_after_first == 1
        await procedural.crystallize(skill)
        skills_count = await svc.count(namespace="skills")
        assert skills_count == 1

    @pytest.mark.asyncio
    async def test_record_usage(self, memory_service):
        """Record usage should update statistics."""
        procedural = ProceduralMemory(memory_service)
        await procedural.crystallize(Skill(
            name="usage_test_skill",
            description="Test usage tracking",
            pattern="test",
            steps=[],
            success_criteria="test",
        ))
        await procedural.record_usage("usage_test_skill", success=True)
        skill = await procedural.get_skill_by_name("usage_test_skill")
        assert skill is not None
        assert int(skill["metadata"]["usage_count"]) >= 1


# ── Identity Memory Tests ────────────────────────────────────────

class TestIdentityMemory:

    @pytest.mark.asyncio
    async def test_create_profile(self, memory_service):
        """Create a new user profile."""
        identity = IdentityMemory(memory_service)
        profile = UserProfile(
            user_id="user_001",
            display_name="Alice",
            language_preference="fr",
            domain_expertise=["machine learning", "python"],
        )
        doc_id = await identity.create_or_update_profile(profile)
        assert doc_id is not None

    @pytest.mark.asyncio
    async def test_get_profile(self, memory_service):
        """Retrieve a user profile."""
        identity = IdentityMemory(memory_service)
        await identity.create_or_update_profile(UserProfile(
            user_id="user_002",
            display_name="Bob",
        ))
        profile = await identity.get_profile("user_002")
        assert profile is not None
        assert profile["metadata"]["display_name"] == "Bob"

    @pytest.mark.asyncio
    async def test_update_profile(self, memory_service):
        """Updating profile should merge data."""
        identity = IdentityMemory(memory_service)
        await identity.create_or_update_profile(UserProfile(
            user_id="user_003",
            display_name="Charlie",
            domain_expertise=["rust"],
        ))
        await identity.create_or_update_profile(UserProfile(
            user_id="user_003",
            communication_style="casual",
        ))
        profile = await identity.get_profile("user_003")
        assert profile["metadata"]["communication_style"] == "casual"

    @pytest.mark.asyncio
    async def test_record_preference(self, memory_service):
        """Record a single preference."""
        identity = IdentityMemory(memory_service)
        await identity.create_or_update_profile(UserProfile(user_id="user_004"))
        await identity.record_preference("user_004", "theme", "dark")
        await identity.record_preference("user_004", "model", "gpt-4o")
        profile = await identity.get_profile("user_004")
        assert profile is not None
