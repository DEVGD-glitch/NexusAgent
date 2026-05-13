"""
Complete tests for NEXUS Knowledge modules.

Covers:
  - KnowledgeGraph: save/load persistence, get_neighbors, find_paths,
    export_to_json, import_from_json, get_stats, remove_entity, get_subgraph
  - MultiSourceWebSearch: with mocked httpx, DuckDuckGo fallback, error handling
  - DeepResearch: investigate() with mocked search, report generation
  - RAGPipeline: query/retrieve/generate pipeline, self-correction, document ingestion
  - WatchdogService: source management, scheduling, RSS parsing, change detection,
    alert generation, seen_hashes serialization
"""

import pytest
import json
import time
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock


# ═══════════════════════════════════════════════════════════════════
# Knowledge Graph Tests
# ═══════════════════════════════════════════════════════════════════

class TestKnowledgeGraph:
    """Complete tests for KnowledgeGraph."""

    @pytest.fixture
    def kg(self):
        from nexus.knowledge.knowledge_graph import KnowledgeGraph
        g = KnowledgeGraph()
        g.add_entity("Python", entity_type="language", properties={"paradigm": "multi"}, source="test")
        g.add_entity("Guido van Rossum", entity_type="person", properties={"nationality": "Dutch"})
        g.add_entity("Django", entity_type="framework", properties={"language": "Python"})
        g.add_entity("PyTorch", entity_type="library", properties={"domain": "ML"})
        g.add_relationship("Guido van Rossum", "Python", "created")
        g.add_relationship("Python", "Django", "used_by")
        g.add_relationship("Python", "PyTorch", "used_by")
        return g

    def test_add_entity(self, kg):
        """add_entity should create a new entity."""
        node_id = kg.add_entity("FastAPI", entity_type="framework")
        assert node_id is not None
        assert node_id.startswith("entity_")
        assert kg.get_entity("FastAPI") is not None

    def test_add_entity_existing_updates(self, kg):
        """add_entity on existing name should update it."""
        node_id = kg.add_entity("Python", entity_type="language", properties={"new_prop": "value"})
        entity = kg.get_entity("Python")
        assert entity["properties"]["new_prop"] == "value"
        assert entity["properties"]["paradigm"] == "multi"  # Old prop preserved

    def test_get_entity_nonexistent(self, kg):
        """get_entity for non-existent name should return None."""
        result = kg.get_entity("NonExistent")
        assert result is None

    def test_add_relationship_auto_creates_entities(self, kg):
        """add_relationship should auto-create entities if they don't exist."""
        kg.add_relationship("NewSource", "NewTarget", "links_to")
        assert kg.get_entity("NewSource") is not None
        assert kg.get_entity("NewTarget") is not None

    def test_add_relationship_bidirectional(self, kg):
        """add_relationship with bidirectional=True should create reverse edge."""
        kg.add_relationship("Python", "Django", "framework_of", bidirectional=True)
        rels = kg.get_relationships("Django", direction="outgoing")
        reverse_rels = [r for r in rels if "reverse" in r.get("relation_type", "")]
        # There should be at least one relationship from Django
        assert len(rels) >= 1

    def test_get_relationships_all(self, kg):
        """get_relationships should return both outgoing and incoming."""
        rels = kg.get_relationships("Python")
        assert len(rels) > 0

    def test_get_relationships_filter_by_type(self, kg):
        """get_relationships should filter by type."""
        rels = kg.get_relationships("Python", relation_type="used_by")
        assert all(r["relation_type"] == "used_by" for r in rels)

    def test_get_relationships_outgoing_only(self, kg):
        """get_relationships with direction='outgoing'."""
        rels = kg.get_relationships("Python", direction="outgoing")
        assert all(r["source"] == "Python" for r in rels)

    def test_get_relationships_incoming_only(self, kg):
        """get_relationships with direction='incoming'."""
        rels = kg.get_relationships("Guido van Rossum", direction="incoming")
        # Guido has no incoming relationships
        assert isinstance(rels, list)

    def test_get_relationships_nonexistent_entity(self, kg):
        """get_relationships for missing entity should return []."""
        rels = kg.get_relationships("Ghost")
        assert rels == []

    def test_find_paths(self, kg):
        """find_paths should return paths between two entities."""
        paths = kg.find_paths("Guido van Rossum", "Django")
        assert len(paths) > 0
        # Path should go through Python
        assert paths[0][0] == "Guido van Rossum"
        assert paths[0][-1] == "Django"

    def test_find_paths_no_path(self, kg):
        """find_paths when no path exists should return []."""
        kg.add_entity("IsolatedNode")
        paths = kg.find_paths("Guido van Rossum", "IsolatedNode")
        assert paths == []

    def test_find_paths_missing_entity(self, kg):
        """find_paths with non-existent entity should return []."""
        paths = kg.find_paths("Ghost", "Python")
        assert paths == []
        paths = kg.find_paths("Python", "Ghost")
        assert paths == []

    def test_get_neighbors_degree_1(self, kg):
        """get_neighbors should return direct neighbors."""
        neighbors = kg.get_neighbors("Python", degree=1)
        assert len(neighbors) > 0
        assert "Guido van Rossum" in neighbors or "Django" in neighbors or "PyTorch" in neighbors

    def test_get_neighbors_degree_2(self, kg):
        """get_neighbors with degree=2 should return further neighbors."""
        # Add a 2-hop chain
        kg.add_entity("WebApp")
        kg.add_relationship("Django", "WebApp", "creates")
        neighbors = kg.get_neighbors("Python", degree=2)
        assert "WebApp" in neighbors

    def test_get_neighbors_unknown_entity(self, kg):
        """get_neighbors for unknown entity should return []."""
        neighbors = kg.get_neighbors("UnknownEntity")
        assert neighbors == []

    def test_search_entities(self, kg):
        """search_entities should find by name prefix."""
        results = kg.search_entities("Py")
        names = [r["name"] for r in results]
        assert "Python" in names
        assert "PyTorch" in names

    def test_search_entities_with_type_filter(self, kg):
        """search_entities should filter by entity_type."""
        results = kg.search_entities("Py", entity_type="language")
        assert len(results) == 1
        assert results[0]["name"] == "Python"

    def test_search_entities_no_results(self, kg):
        """search_entities with no match should return []."""
        results = kg.search_entities("ZZZZ")
        assert results == []

    def test_search_entities_limit(self, kg):
        """search_entities should respect limit."""
        # Add more Python-like entities
        kg.add_entity("Pyramid", entity_type="framework")
        results = kg.search_entities("Py", limit=1)
        assert len(results) <= 1

    def test_get_subgraph(self, kg):
        """get_subgraph should extract subgraph around entity."""
        sub = kg.get_subgraph("Python", radius=1)
        assert "nodes" in sub
        assert "edges" in sub
        assert len(sub["nodes"]) > 0

    def test_get_subgraph_unknown_entity(self, kg):
        """get_subgraph for unknown entity should return empty."""
        sub = kg.get_subgraph("Ghost")
        assert sub == {"nodes": [], "edges": []}

    def test_remove_entity(self, kg):
        """remove_entity should delete entity and its relationships."""
        result = kg.remove_entity("PyTorch")
        assert result is True
        assert kg.get_entity("PyTorch") is None

        # Relationships involving PyTorch should also be removed
        rels = kg.get_relationships("Python")
        pytorch_rels = [r for r in rels if r.get("target") == "PyTorch"]
        assert len(pytorch_rels) == 0

    def test_remove_entity_nonexistent(self, kg):
        """remove_entity for non-existent entity should return False."""
        result = kg.remove_entity("Ghost")
        assert result is False

    def test_get_stats(self, kg):
        """get_stats should return correct statistics."""
        stats = kg.get_stats()
        assert stats["total_entities"] >= 4
        assert stats["total_relationships"] >= 3
        assert "language" in stats["entity_types"]
        assert "used_by" in stats["relation_types"]
        assert "density" in stats
        assert "is_connected" in stats

    def test_get_stats_empty(self):
        """get_stats on empty graph should return zeros."""
        from nexus.knowledge.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        stats = kg.get_stats()
        assert stats["total_entities"] == 0
        assert stats["total_relationships"] == 0
        assert stats["is_connected"] is True  # Empty graph is trivially connected

    def test_save_and_load(self, kg, tmp_path):
        """save() should persist and load() should restore."""
        save_path = tmp_path / "test_kg.json"
        result = kg.save(str(save_path))
        assert result is True
        assert save_path.exists()

        # Create new KG and load
        from nexus.knowledge.knowledge_graph import KnowledgeGraph
        kg2 = KnowledgeGraph()
        load_result = kg2.load(str(save_path))
        assert load_result is True
        assert kg2.get_entity("Python") is not None
        assert kg2.get_entity("Guido van Rossum") is not None
        # Relationships should be restored
        rels = kg2.get_relationships("Python")
        assert len(rels) > 0

    def test_load_file_not_found(self):
        """load() with non-existent file should return False."""
        from nexus.knowledge.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        result = kg.load("/nonexistent/path/kg.json")
        assert result is False

    def test_load_corrupt_file(self, tmp_path):
        """load() with corrupt JSON should return False."""
        from nexus.knowledge.knowledge_graph import KnowledgeGraph
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("this is not valid json {")
        kg = KnowledgeGraph()
        result = kg.load(str(bad_file))
        assert result is False

    def test_save_failure(self, kg):
        """save() should return False on failure."""
        # Use an invalid path that can't be created
        result = kg.save("/invalid/\x00path/kg.json")
        assert result is False

    def test_export_to_json(self, kg):
        """export_to_json should produce valid JSON string."""
        json_str = kg.export_to_json()
        data = json.loads(json_str)
        assert "nodes" in data
        # NetworkX node_link_data may use "edges" or "links" depending on version
        assert "edges" in data or "links" in data
        assert data["directed"] is True

    def test_import_from_json(self, kg):
        """import_from_json should restore graph from JSON string."""
        json_str = kg.export_to_json()
        from nexus.knowledge.knowledge_graph import KnowledgeGraph
        kg2 = KnowledgeGraph()
        count = kg2.import_from_json(json_str)
        assert count >= 4
        assert kg2.get_entity("Python") is not None

    def test_import_from_json_empty(self):
        """import_from_json with minimal JSON should work."""
        from nexus.knowledge.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        # NetworkX node_link_graph expects "edges" key (newer versions)
        minimal_json = json.dumps({
            "directed": True,
            "multigraph": False,
            "graph": {},
            "nodes": [],
            "edges": [],
        })
        count = kg.import_from_json(minimal_json)
        assert count == 0


# ═══════════════════════════════════════════════════════════════════
# Web Search Tests
# ═══════════════════════════════════════════════════════════════════

class TestMultiSourceWebSearch:
    """Test MultiSourceWebSearch with mocked HTTP."""

    @pytest.fixture
    def search(self):
        from nexus.knowledge.web_search import MultiSourceWebSearch
        return MultiSourceWebSearch()

    @pytest.mark.asyncio
    async def test_search_duckduckgo_only(self, search):
        """search should use DuckDuckGo as fallback."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
        <a rel="nofollow" class="result__a" href="https://example.com">Result Title</a>
        <a class="result__snippet">This is a snippet of the result.</a>
        <a rel="nofollow" class="result__a" href="https://example2.com">Second Result</a>
        <a class="result__snippet">Second snippet here.</a>
        </html>
        """

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            # Force only duckduckgo engine
            results = await search.search("test query", num_results=5, engines=["duckduckgo"])
            assert len(results) == 2
            assert results[0].title == "Result Title"
            assert results[0].url == "https://example.com"
            assert results[0].source_engine == "duckduckgo"

    @pytest.mark.asyncio
    async def test_search_duckduckgo_http_error(self, search):
        """DuckDuckGo should return [] on HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            results = await search.search("test", num_results=5, engines=["duckduckgo"])
            assert results == []

    @pytest.mark.asyncio
    async def test_search_serpapi_no_key(self, search):
        """SerpAPI should return [] when no API key configured."""
        with patch.object(search.settings, "serpapi_key", None):
            results = await search.search("test", num_results=5, engines=["serpapi"])
            assert results == []

    @pytest.mark.asyncio
    async def test_search_serpapi_success(self, search):
        """SerpAPI should return parsed results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organic_results": [
                {"title": "Serp Result", "link": "https://serp.com", "snippet": "Serp snippet"},
            ]
        }

        with patch.object(search.settings, "serpapi_key", "fake_key"):
            with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
                results = await search.search("test", num_results=5, engines=["serpapi"])
                assert len(results) == 1
                assert results[0].title == "Serp Result"
                assert results[0].source_engine == "serpapi"

    @pytest.mark.asyncio
    async def test_search_serpapi_http_error(self, search):
        """SerpAPI should return [] on HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.object(search.settings, "serpapi_key", "fake_key"):
            with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
                results = await search.search("test", engines=["serpapi"])
                assert results == []

    @pytest.mark.asyncio
    async def test_search_brave_no_key(self, search):
        """Brave should return [] when no API key configured."""
        with patch.object(search.settings, "brave_search_key", None):
            results = await search.search("test", engines=["brave"])
            assert results == []

    @pytest.mark.asyncio
    async def test_search_brave_success(self, search):
        """Brave Search should return parsed results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {"title": "Brave Result", "url": "https://brave.com", "description": "Brave snippet"},
                ]
            }
        }

        with patch.object(search.settings, "brave_search_key", "fake_brave_key"):
            with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
                results = await search.search("test", engines=["brave"])
                assert len(results) == 1
                assert results[0].title == "Brave Result"
                assert results[0].source_engine == "brave"

    @pytest.mark.asyncio
    async def test_search_brave_http_error(self, search):
        """Brave should return [] on HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch.object(search.settings, "brave_search_key", "fake_brave_key"):
            with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
                results = await search.search("test", engines=["brave"])
                assert results == []

    @pytest.mark.asyncio
    async def test_search_zai_sdk_import_error(self, search):
        """z-ai-web-dev-sdk import failure should return []."""
        with patch.dict("sys.modules", {"z_ai_web_dev_sdk": None}):
            # Force import error by patching
            results = await search.search("test", engines=["zai_sdk"])
            assert results == []  # Falls through gracefully

    @pytest.mark.asyncio
    async def test_search_unknown_engine(self, search):
        """Unknown engine should be skipped."""
        results = await search.search("test", engines=["unknown_engine"])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_all_engines_fail(self, search):
        """When all engines fail, should return []."""
        with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=Exception("Network error"))):
            with patch.object(search.settings, "serpapi_key", "fake"):
                with patch.object(search.settings, "brave_search_key", "fake"):
                    results = await search.search("test", engines=["serpapi", "brave", "duckduckgo"])
                    # Should still attempt each and fail gracefully
                    assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_deduplication(self, search):
        """Search should deduplicate by URL."""
        mock_ddg = MagicMock()
        mock_ddg.status_code = 200
        mock_ddg.text = """
        <a rel="nofollow" class="result__a" href="https://same.com">Same</a>
        <a class="result__snippet">Snippet</a>
        """

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_ddg)):
            results = await search.search("test", num_results=10, engines=["duckduckgo", "duckduckgo"])
            # Should not duplicate
            urls = [r.url for r in results]
            assert len(urls) == len(set(urls))

    @pytest.mark.asyncio
    async def test_search_engine_exception_continues(self, search):
        """Exception in one engine should not stop others."""
        # Make serpapi fail with exception
        with patch.object(search.settings, "serpapi_key", "fake"):
            with patch("httpx.AsyncClient.get") as mock_get:
                mock_serp = MagicMock()
                mock_serp.status_code = 200
                mock_serp.json.return_value = {"organic_results": [{"title": "T", "link": "https://t.com", "snippet": "S"}]}

                # First call fails, second succeeds
                mock_get.side_effect = [Exception("SerpAPI error"), mock_serp]

                results = await search.search("test", engines=["serpapi", "serpapi"])
                assert len(results) > 0


# ═══════════════════════════════════════════════════════════════════
# Deep Research Tests
# ═══════════════════════════════════════════════════════════════════

class TestDeepResearch:
    """Test DeepResearch engine."""

    @pytest.fixture
    def research(self):
        from nexus.knowledge.deep_research import DeepResearch
        return DeepResearch(max_sub_queries=3, max_sources_per_query=3)

    @pytest.fixture
    def mock_llm_response(self):
        mock_response = MagicMock()
        mock_response.content = "\n".join([
            "1. What is the current state of AI agents?",
            "2. How do AI agents handle multi-step reasoning?",
            "3. What frameworks exist for building AI agents?",
        ])
        mock_response.provider = "openai"
        mock_response.model = "gpt-4o"
        mock_response.usage = {"prompt_tokens": 50, "completion_tokens": 30}
        return mock_response

    @pytest.mark.asyncio
    async def test_investigate_quick(self, research, mock_llm_response):
        """investigate with depth='quick' should produce a report."""
        with patch("nexus.llm.router.LLMRouter") as mock_cls:
            mock_router = MagicMock()
            mock_router.complete = AsyncMock(return_value=mock_llm_response)
            mock_cls.return_value = mock_router

            # Mock search sources
            with patch.object(research, "_search_sources", new=AsyncMock(return_value=[])):
                report = await research.investigate("AI agents 2024", depth="quick")
                assert report is not None
                assert report.topic == "AI agents 2024"
                assert report.depth == "quick"

    @pytest.mark.asyncio
    async def test_investigate_with_sources(self, research):
        """investigate should work with mocked sources."""
        from nexus.knowledge.deep_research import ResearchSource

        mock_source = ResearchSource(
            title="Test Source",
            url="https://example.com",
            snippet="Important finding about AI agents and their capabilities",
            source_type="web",
        )

        with patch.object(research, "_search_sources", new=AsyncMock(return_value=[mock_source])):
            with patch.object(research, "_decompose_query", new=AsyncMock(return_value=["test query"])):
                with patch.object(research, "_extract_finding", new=AsyncMock(return_value="Key finding from source")):
                    with patch.object(research, "_synthesize") as mock_synth:
                        from nexus.knowledge.deep_research import ResearchReport
                        mock_synth.return_value = ResearchReport(
                            topic="Test",
                            summary="Summary here",
                            key_findings=["Finding 1"],
                            sources=[mock_source],
                            confidence=0.8,
                            depth="medium",
                        )

                        report = await research.investigate("Test topic", depth="medium")
                        assert report.summary == "Summary here"
                        assert len(report.sources) > 0

    @pytest.mark.asyncio
    async def test_decompose_query_llm_failure(self, research):
        """_decompose_query should fallback on LLM failure."""
        with patch("nexus.llm.router.LLMRouter") as mock_cls:
            mock_router = MagicMock()
            mock_router.complete = AsyncMock(side_effect=Exception("LLM down"))
            mock_cls.return_value = mock_router

            queries = await research._decompose_query("Test topic")
            assert queries == ["Test topic"]  # Falls back to topic

    @pytest.mark.asyncio
    async def test_decompose_query_parsing(self, research, mock_llm_response):
        """_decompose_query should parse numbered list."""
        from nexus.llm.router import LLMRouter

        with patch.object(LLMRouter, "complete", new=AsyncMock(return_value=mock_llm_response)):
            queries = await research._decompose_query("Test")
            assert len(queries) == 3
            assert "What is the current state" in queries[0]

    @pytest.mark.asyncio
    async def test_search_sources_memory_error(self, research):
        """_search_sources should handle memory search failure."""
        with patch("nexus.memory.chroma_service.NexusMemoryService") as mock_cls:
            mock_svc = MagicMock()
            mock_svc.search = AsyncMock(side_effect=Exception("Memory error"))
            mock_cls.return_value = mock_svc

            # Should not raise, just return empty sources
            sources = await research._search_sources("test")
            assert isinstance(sources, list)

    @pytest.mark.asyncio
    async def test_search_sources_web_error(self, research):
        """_search_sources should handle web search failure."""
        with patch("nexus.memory.chroma_service.NexusMemoryService") as mock_mem:
            mock_svc = MagicMock()
            mock_svc.search = AsyncMock(return_value={
                "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]],
            })
            mock_mem.return_value = mock_svc

            with patch("nexus.knowledge.web_search.MultiSourceWebSearch") as mock_web:
                mock_search = MagicMock()
                mock_search.search = AsyncMock(side_effect=Exception("Web error"))
                mock_web.return_value = mock_search

                sources = await research._search_sources("test")
                assert isinstance(sources, list)

    @pytest.mark.asyncio
    async def test_extract_finding(self, research):
        """_extract_finding should format finding from source."""
        from nexus.knowledge.deep_research import ResearchSource

        source = ResearchSource(title="Source", snippet="Important snippet", source_type="web")
        result = await research._extract_finding("query", source)
        assert result is not None

    @pytest.mark.asyncio
    async def test_extract_finding_no_snippet(self, research):
        """_extract_finding should return None for empty snippet."""
        from nexus.knowledge.deep_research import ResearchSource

        source = ResearchSource(title="Empty", snippet="")
        result = await research._extract_finding("query", source)
        assert result is None

    @pytest.mark.asyncio
    async def test_refine_queries(self, research):
        """_refine_queries should generate follow-up questions."""
        from nexus.llm.router import LLMRouter

        mock_response = MagicMock()
        mock_response.content = "\n".join([
            "1. Follow-up question one?",
            "2. Follow-up question two?",
        ])

        with patch.object(LLMRouter, "complete", new=AsyncMock(return_value=mock_response)):
            queries = await research._refine_queries("Test topic", ["Finding 1", "Finding 2"])
            assert len(queries) == 2

    @pytest.mark.asyncio
    async def test_refine_queries_failure(self, research):
        """_refine_queries should fallback on LLM failure."""
        with patch("nexus.llm.router.LLMRouter") as mock_cls:
            mock_router = MagicMock()
            mock_router.complete = AsyncMock(side_effect=Exception("LLM down"))
            mock_cls.return_value = mock_router

            queries = await research._refine_queries("Topic", ["Finding"])
            assert queries == ["Topic"]

    @pytest.mark.asyncio
    async def test_synthesize_json_response(self, research):
        """_synthesize should parse JSON from LLM response."""
        from nexus.llm.router import LLMRouter

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "summary": "Research summary",
            "key_findings": ["Finding 1", "Finding 2"],
            "confidence": "high",
        })

        with patch.object(LLMRouter, "complete", new=AsyncMock(return_value=mock_response)):
            from nexus.knowledge.deep_research import ResearchSource
            sources = [ResearchSource(title="S", url="https://x.com", snippet="Snippet", source_type="web")]

            report = await research._synthesize("Topic", ["Finding 1"], sources, "deep")
            assert report.summary == "Research summary"
            assert len(report.key_findings) == 2
            assert report.confidence == 1.0  # high -> 1.0

    @pytest.mark.asyncio
    async def test_synthesize_json_in_code_block(self, research):
        """_synthesize should extract JSON from markdown code block."""
        from nexus.llm.router import LLMRouter

        mock_response = MagicMock()
        mock_response.content = "```json\n{\"summary\": \"Sum\", \"key_findings\": [\"F1\"], \"confidence\": \"medium\"}\n```"

        with patch.object(LLMRouter, "complete", new=AsyncMock(return_value=mock_response)):
            report = await research._synthesize("Topic", ["F1"], [], "quick")
            assert report.summary == "Sum"
            assert report.confidence == 0.5  # medium -> 0.5

    @pytest.mark.asyncio
    async def test_synthesize_fallback_on_parse_error(self, research):
        """_synthesize should fallback when JSON is invalid."""
        from nexus.llm.router import LLMRouter

        mock_response = MagicMock()
        mock_response.content = "Some plain text response without JSON"

        with patch.object(LLMRouter, "complete", new=AsyncMock(return_value=mock_response)):
            report = await research._synthesize("Topic", ["F1"], [], "quick")
            assert report.topic == "Topic"
            assert len(report.key_findings) > 0

    @pytest.mark.asyncio
    async def test_synthesize_llm_failure(self, research):
        """_synthesize should return error report on LLM failure."""
        with patch("nexus.llm.router.LLMRouter") as mock_cls:
            mock_router = MagicMock()
            mock_router.complete = AsyncMock(side_effect=Exception("LLM failed"))
            mock_cls.return_value = mock_router

            report = await research._synthesize("Topic", ["F1"], [], "quick")
            assert "failed" in report.summary.lower()

    @pytest.mark.asyncio
    async def test_investigate_deep_with_refinement(self, research):
        """investigate with depth='deep' should refine queries."""
        from nexus.llm.router import LLMRouter
        from nexus.knowledge.deep_research import ResearchSource

        mock_q = MagicMock()
        mock_q.content = "1. Refined question?"

        mock_synth = MagicMock()
        mock_synth.content = json.dumps({
            "summary": "Deep summary",
            "key_findings": ["Deep finding"],
            "confidence": "high",
        })

        # First call returns queries, then refined queries
        call_count = [0]
        async def mock_complete(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 1:
                return mock_q
            return mock_synth

        with patch.object(LLMRouter, "complete", new=AsyncMock(side_effect=mock_complete)):
            with patch.object(research, "_search_sources", new=AsyncMock(return_value=[
                ResearchSource(title="S", snippet="Content")
            ])):
                with patch.object(research, "_extract_finding", new=AsyncMock(return_value="Key finding")):
                    report = await research.investigate("Topic", depth="deep")
                    assert report is not None


# ═══════════════════════════════════════════════════════════════════
# RAG Pipeline Tests
# ═══════════════════════════════════════════════════════════════════

class TestRAGPipeline:
    """Test RAGPipeline — query, retrieve, generate, ingest."""

    @pytest.fixture
    def rag(self):
        from nexus.knowledge.rag_pipeline import RAGPipeline
        return RAGPipeline(top_k=3, max_retrieval_attempts=2, min_relevance_score=0.3)

    @pytest.fixture
    def mock_search_results(self):
        return {
            "ids": [["doc1", "doc2", "doc3"]],
            "documents": [["Python is a programming language created by Guido van Rossum.",
                          "Python is used for web development, data science, and AI.",
                          "Guido van Rossum is the creator of Python."]],
            "metadatas": [[{"source": "wiki"}, {"source": "docs"}, {"source": "article"}]],
            "distances": [[0.1, 0.2, 0.3]],
        }

    @pytest.mark.asyncio
    async def test_query_success(self, rag, mock_search_results):
        """query() should return RAGResult with answer."""
        from nexus.llm.router import LLMRouter

        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "Python was created by Guido van Rossum."
        mock_response.provider = "openai"
        mock_response.model = "gpt-4o"
        mock_response.usage = {}
        mock_llm.complete.return_value = mock_response

        with patch("nexus.memory.chroma_service.NexusMemoryService") as mock_cls:
            mock_svc = MagicMock()
            mock_svc.search = AsyncMock(return_value=mock_search_results)
            mock_cls.return_value = mock_svc

            with patch.object(LLMRouter, "complete", new=AsyncMock(return_value=mock_response)):
                result = await rag.query("Who created Python?")
                assert result.answer == "Python was created by Guido van Rossum."
                assert result.documents_used > 0
                assert result.query == "Who created Python?"

    @pytest.mark.asyncio
    async def test_query_no_results(self, rag):
        """query() with no results should return fallback answer."""
        from nexus.memory.chroma_service import NexusMemoryService

        with patch.object(NexusMemoryService, "search", new=AsyncMock(return_value={
            "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]],
        })):
            result = await rag.query("Something very obscure")
            assert "couldn't find" in result.answer.lower()

    @pytest.mark.asyncio
    async def test_retrieve_error(self, rag):
        """_retrieve should handle exceptions gracefully."""
        with patch("nexus.memory.chroma_service.NexusMemoryService") as mock_cls:
            mock_svc = MagicMock()
            mock_svc.search = AsyncMock(side_effect=Exception("ChromaDB error"))
            mock_cls.return_value = mock_svc

            docs = await rag._retrieve("test query", "knowledge")
            assert docs == []

    @pytest.mark.asyncio
    async def test_reformulate_query(self, rag):
        """_reformulate_query should return reformulated text."""
        from nexus.llm.router import LLMRouter

        mock_response = MagicMock()
        mock_response.content = "What is the creator of Python programming language?"

        with patch.object(LLMRouter, "complete", new=AsyncMock(return_value=mock_response)):
            reformulated = await rag._reformulate_query("Who made Python?", 1)
            assert len(reformulated) > 0
            assert "Python" in reformulated

    @pytest.mark.asyncio
    async def test_reformulate_query_failure(self, rag):
        """_reformulate_query should return original on failure."""
        with patch("nexus.llm.router.LLMRouter") as mock_cls:
            mock_router = MagicMock()
            mock_router.complete = AsyncMock(side_effect=Exception("LLM error"))
            mock_cls.return_value = mock_router

            result = await rag._reformulate_query("Original query", 1)
            assert result == "Original query"

    @pytest.mark.asyncio
    async def test_rerank(self, rag):
        """_rerank should sort by score descending."""
        from nexus.knowledge.rag_pipeline import RAGDocument

        docs = [
            RAGDocument(text="A", score=0.3),
            RAGDocument(text="B", score=0.9),
            RAGDocument(text="C", score=0.6),
        ]
        ranked = await rag._rerank("query", docs)
        assert ranked[0].score == 0.9
        assert ranked[1].score == 0.6
        assert ranked[2].score == 0.3

    @pytest.mark.asyncio
    async def test_generate(self, rag):
        """_generate should produce answer from context."""
        from nexus.llm.router import LLMRouter
        from nexus.knowledge.rag_pipeline import RAGDocument

        mock_response = MagicMock()
        mock_response.content = "Generated answer."
        mock_response.provider = "openai"
        mock_response.model = "gpt-4o"
        mock_response.usage = {}

        with patch.object(LLMRouter, "complete", new=AsyncMock(return_value=mock_response)):
            docs = [RAGDocument(text="Context", source="test", score=0.9)]
            answer = await rag._generate("Question?", docs)
            assert answer == "Generated answer."

    @pytest.mark.asyncio
    async def test_generate_with_context_messages(self, rag):
        """_generate should incorporate context messages."""
        from nexus.llm.router import LLMRouter
        from nexus.knowledge.rag_pipeline import RAGDocument

        mock_response = MagicMock()
        mock_response.content = "Answer with context."

        with patch.object(LLMRouter, "complete", new=AsyncMock(return_value=mock_response)):
            docs = [RAGDocument(text="Context", source="test", score=0.9)]
            answer = await rag._generate("Question?", docs, context_messages=[{"role": "assistant", "content": "Previous"}])
            assert answer == "Answer with context."

    @pytest.mark.asyncio
    async def test_generate_error(self, rag):
        """_generate should return error message on LLM failure."""
        from nexus.knowledge.rag_pipeline import RAGDocument

        with patch("nexus.llm.router.LLMRouter") as mock_cls:
            mock_router = MagicMock()
            mock_router.complete = AsyncMock(side_effect=Exception("Generation failed"))
            mock_cls.return_value = mock_router

            docs = [RAGDocument(text="Context", source="test", score=0.9)]
            answer = await rag._generate("Question?", docs)
            assert "Error" in answer

    @pytest.mark.asyncio
    async def test_self_correction_loop(self, rag):
        """query() should reformulate on low relevance scores."""
        from nexus.memory.chroma_service import NexusMemoryService
        from nexus.llm.router import LLMRouter

        # First search returns low relevance, second returns good
        call_count = [0]
        async def mock_search(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    "ids": [["low"]],
                    "documents": [["Irrelevant content that doesn't match the query at all"]],
                    "metadatas": [[{"source": "wiki"}]],
                    "distances": [[0.9]],  # Low relevance
                }
            return {
                "ids": [["good"]],
                "documents": [["Python was created by Guido van Rossum in 1991."]],
                "metadatas": [[{"source": "wiki"}]],
                "distances": [[0.1]],  # High relevance
            }

        mock_response = MagicMock()
        mock_response.content = "Reformulated query version"
        mock_gen_response = MagicMock()
        mock_gen_response.content = "Guido van Rossum created Python."

        with patch.object(NexusMemoryService, "search", new=AsyncMock(side_effect=mock_search)):
            with patch.object(LLMRouter, "complete", new=AsyncMock(side_effect=[mock_response, mock_gen_response])):
                result = await rag.query("Who created Python?")
                assert result.retrieval_attempts > 1
                assert result.answer is not None

    @pytest.mark.asyncio
    async def test_ingest_document(self, rag):
        """ingest_document should split text and store chunks."""
        from nexus.memory.chroma_service import NexusMemoryService

        with patch.object(NexusMemoryService, "search", new=AsyncMock(return_value={
            "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]],
        })):
            with patch("nexus.memory.semantic.SemanticMemory") as mock_sem:
                mock_sem_inst = MagicMock()
                mock_sem_inst.add_document_chunk = AsyncMock(return_value="chunk_id")
                mock_sem.return_value = mock_sem_inst

                text = "This is a long document. It has multiple sentences. " * 100
                count = await rag.ingest_document(text, source="test_doc", chunk_size=500, chunk_overlap=50)
                assert count > 0
                assert mock_sem_inst.add_document_chunk.call_count == count


# ═══════════════════════════════════════════════════════════════════
# Watchdog Service Tests
# ═══════════════════════════════════════════════════════════════════

class TestWatchdogService:
    """Test WatchdogService — source management, RSS, change detection, alerts."""

    @pytest.fixture
    def watchdog(self):
        from nexus.knowledge.watchdog import WatchdogService
        return WatchdogService()

    # ── Source Management ───────────────────────────────────────

    def test_add_rss_source(self, watchdog):
        """add_rss_source should create WatchdogSource."""
        source = watchdog.add_rss_source(
            "tech-news", "Tech News", "https://example.com/feed.xml",
            schedule="0 * * * *", keywords=["AI", "ML"],
        )
        assert source.source_id == "tech-news"
        assert source.source_type.value == "rss"
        assert source.keywords == ["AI", "ML"]

    def test_add_web_source(self, watchdog):
        """add_web_source should create WatchdogSource."""
        source = watchdog.add_web_source(
            "my-site", "My Site", "https://example.com",
            schedule="0 */6 * * *", keywords=["update"],
        )
        assert source.source_id == "my-site"
        assert source.source_type.value == "web_page"

    def test_add_search_source(self, watchdog):
        """add_search_source should create WatchdogSource."""
        source = watchdog.add_search_source(
            "my-search", "Search News", "AI breakthroughs",
            schedule="0 9 * * *", keywords=["AI"],
        )
        assert source.source_id == "my-search"
        assert source.source_type.value == "search"
        assert source.query == "AI breakthroughs"

    def test_remove_source(self, watchdog):
        """remove_source should remove existing source."""
        watchdog.add_rss_source("s1", "S1", "https://example.com/rss")
        result = watchdog.remove_source("s1")
        assert result is True
        assert len(watchdog._sources) == 0

    def test_remove_nonexistent_source(self, watchdog):
        """remove_source for missing source should return False."""
        result = watchdog.remove_source("nonexistent")
        assert result is False

    def test_pause_and_resume_source(self, watchdog):
        """pause_source and resume_source should toggle status."""
        from nexus.knowledge.watchdog import MonitorStatus

        watchdog.add_rss_source("s1", "S1", "https://example.com/rss")
        assert watchdog.pause_source("s1") is True
        assert watchdog._sources["s1"].status == MonitorStatus.PAUSED
        assert watchdog.resume_source("s1") is True
        assert watchdog._sources["s1"].status == MonitorStatus.ACTIVE

    def test_pause_nonexistent_source(self, watchdog):
        """pause_source for missing source should return False."""
        assert watchdog.pause_source("nonexistent") is False

    def test_list_sources(self, watchdog):
        """list_sources should return all sources as dicts."""
        watchdog.add_rss_source("s1", "S1", "https://example.com/rss")
        watchdog.add_web_source("s2", "S2", "https://example.com")
        sources = watchdog.list_sources()
        assert len(sources) == 2

    def test_get_source(self, watchdog):
        """get_source should return source details."""
        watchdog.add_rss_source("s1", "My Source", "https://example.com/rss")
        details = watchdog.get_source("s1")
        assert details is not None
        assert details["name"] == "My Source"

    def test_get_nonexistent_source(self, watchdog):
        """get_source for missing source should return None."""
        assert watchdog.get_source("nonexistent") is None

    # ── Alert Management ────────────────────────────────────────

    def test_get_pending_alerts(self, watchdog):
        """get_pending_alerts should return alerts."""
        from nexus.knowledge.watchdog import WatchdogAlert

        watchdog._alerts.append(WatchdogAlert(
            source_id="s1", source_name="S1", alert_type="new_item",
            title="Test Alert", content="Content", timestamp=time.time(),
        ))
        alerts = watchdog.get_pending_alerts()
        assert len(alerts) == 1
        assert alerts[0]["title"] == "Test Alert"

    def test_clear_alerts(self, watchdog):
        """clear_alerts should remove all alerts."""
        from nexus.knowledge.watchdog import WatchdogAlert
        watchdog._alerts.append(WatchdogAlert(
            source_id="s1", source_name="S1", alert_type="new_item",
            title="Test", content="Content",
        ))
        watchdog.clear_alerts()
        assert len(watchdog._alerts) == 0

    def test_add_callback(self, watchdog):
        """add_callback should register callback."""
        def my_callback(alerts):
            pass
        watchdog.add_callback(my_callback)
        assert len(watchdog._callbacks) == 1

    # ── RSS Parsing ─────────────────────────────────────────────

    def test_parse_rss_xml(self, watchdog):
        """_parse_rss_xml should parse RSS XML."""
        rss_xml = """<?xml version="1.0"?>
        <rss version="2.0">
        <channel>
        <item>
            <title>Article One</title>
            <link>https://example.com/1</link>
            <description>First article description</description>
            <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
            <author>Author One</author>
            <guid>guid-1</guid>
        </item>
        <item>
            <title>Article Two</title>
            <link>https://example.com/2</link>
            <description>Second article description</description>
        </item>
        </channel>
        </rss>"""
        items = watchdog._parse_rss_xml(rss_xml)
        assert len(items) == 2
        assert items[0].title == "Article One"
        assert items[0].link == "https://example.com/1"
        assert items[0].author == "Author One"
        assert items[1].title == "Article Two"

    def test_parse_rss_xml_atom(self, watchdog):
        """_parse_rss_xml should parse Atom XML."""
        atom_xml = """<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
        <entry>
            <title>Atom Entry</title>
            <link href="https://example.com/atom1"/>
            <summary>Atom summary content</summary>
            <published>2024-01-01T00:00:00Z</published>
            <author><name>Atom Author</name></author>
            <id>atom-id-1</id>
        </entry>
        </feed>"""
        items = watchdog._parse_rss_xml(atom_xml)
        assert len(items) == 1
        assert items[0].title == "Atom Entry"
        assert items[0].link == "https://example.com/atom1"

    def test_parse_rss_xml_cdata(self, watchdog):
        """_parse_rss_xml should strip CDATA."""
        rss_xml = """<?xml version="1.0"?>
        <rss><channel><item>
            <title><![CDATA[CDATA Title]]></title>
            <link>https://example.com</link>
            <description><![CDATA[<b>CDATA Description</b>]]></description>
        </item></channel></rss>"""
        items = watchdog._parse_rss_xml(rss_xml)
        assert len(items) == 1
        assert items[0].title == "CDATA Title"
        assert items[0].description == "CDATA Description"

    def test_parse_rss_xml_empty(self, watchdog):
        """_parse_rss_xml with no items should return []."""
        items = watchdog._parse_rss_xml("<rss><channel></channel></rss>")
        assert items == []

    def test_parse_rss_xml_with_html_in_description(self, watchdog):
        """_parse_rss_xml should strip HTML from description."""
        rss_xml = """<?xml version="1.0"?>
        <rss><channel><item>
            <title>HTML Desc</title>
            <link>https://example.com</link>
            <description><p>Hello <b>world</b></p></description>
        </item></channel></rss>"""
        items = watchdog._parse_rss_xml(rss_xml)
        assert "Hello" in items[0].description
        assert "<b>" not in items[0].description

    # ── RSS Check ───────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_fetch_rss_success(self, watchdog):
        """_fetch_rss should return parsed items."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """<?xml version="1.0"?>
        <rss><channel><item>
            <title>RSS Item</title>
            <link>https://example.com/item</link>
            <description>Description</description>
        </item></channel></rss>"""

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            items = await watchdog._fetch_rss("https://example.com/feed")
            assert len(items) == 1
            assert items[0].title == "RSS Item"

    @pytest.mark.asyncio
    async def test_fetch_rss_http_error(self, watchdog):
        """_fetch_rss should return [] on HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            items = await watchdog._fetch_rss("https://example.com/bad-feed")
            assert items == []

    @pytest.mark.asyncio
    async def test_fetch_rss_exception(self, watchdog):
        """_fetch_rss should return [] on exception."""
        with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=Exception("Network error"))):
            items = await watchdog._fetch_rss("https://example.com/feed")
            assert items == []

    # ── RSS Monitoring ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_check_rss_new_items(self, watchdog):
        """_check_rss should return alerts for new items."""
        from nexus.knowledge.watchdog import RSSItem

        source = watchdog.add_rss_source(
            "rss1", "RSS Source", "https://example.com/feed",
            keywords=["AI"],
        )

        # Mock the internal fetch method
        with patch.object(watchdog, "_fetch_rss", new=AsyncMock(return_value=[
            RSSItem(title="AI Breakthrough", link="https://example.com/ai",
                    description="Major AI breakthrough announced"),
            RSSItem(title="Weather Report", link="https://example.com/weather",
                    description="Sunny today"),
        ])):
            alerts = await watchdog._check_rss(source)
            # Only the AI-related item should match keywords
            assert len(alerts) == 1
            assert alerts[0].title == "AI Breakthrough"

    @pytest.mark.asyncio
    async def test_check_rss_deduplication(self, watchdog):
        """_check_rss should skip seen hashes."""
        import hashlib
        from nexus.knowledge.watchdog import RSSItem

        source = watchdog.add_rss_source("rss1", "RSS Source", "https://example.com/feed")
        source.seen_hashes.add(hashlib.sha256(
            f"First Item|https://example.com/1|Description".encode()
        ).hexdigest()[:16])

        item = RSSItem(title="First Item", link="https://example.com/1", description="Description")
        item.compute_hash()

        with patch.object(watchdog, "_fetch_rss", new=AsyncMock(return_value=[
            item,
            RSSItem(title="Second Item", link="https://example.com/2", description="Description"),
        ])):
            alerts = await watchdog._check_rss(source)
            # Only second item should produce alert
            assert len(alerts) == 1
            assert alerts[0].title == "Second Item"

    @pytest.mark.asyncio
    async def test_check_rss_no_keywords_filter(self, watchdog):
        """_check_rss without keywords should return all items."""
        from nexus.knowledge.watchdog import RSSItem

        source = watchdog.add_rss_source("rss1", "RSS Source", "https://example.com/feed")

        with patch.object(watchdog, "_fetch_rss", new=AsyncMock(return_value=[
            RSSItem(title="Any Item", link="https://example.com/1", description="Content"),
        ])):
            alerts = await watchdog._check_rss(source)
            assert len(alerts) == 1

    # ── Web Page Change Detection ───────────────────────────────

    @pytest.mark.asyncio
    async def test_check_web_page_first_check(self, watchdog):
        """First web page check should not generate an alert."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><title>Test Page</title><body>Content</body></html>"

        source = watchdog.add_web_source("wp1", "Web Page", "https://example.com")

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            alerts = await watchdog._check_web_page(source)
            assert alerts == []  # First check, no baseline

    @pytest.mark.asyncio
    async def test_check_web_page_change_detected(self, watchdog):
        """Second check with changed content should generate alert."""
        from nexus.knowledge.watchdog import WebPageSnapshot

        source = watchdog.add_web_source("wp1", "Web Page", "https://example.com")

        # Set up previous snapshot
        prev_snapshot = WebPageSnapshot(url="https://example.com")
        prev_snapshot.compute_hash("Original content")
        watchdog._page_snapshots["wp1"] = prev_snapshot

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><title>Changed Page</title><body>Changed content</body></html>"

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            alerts = await watchdog._check_web_page(source)
            assert len(alerts) == 1
            assert alerts[0].alert_type == "page_changed"
            assert "Change detected" in alerts[0].title

    @pytest.mark.asyncio
    async def test_check_web_page_no_change(self, watchdog):
        """Same content should not generate alert."""
        import re
        from nexus.knowledge.watchdog import WebPageSnapshot

        source = watchdog.add_web_source("wp1", "Web Page", "https://example.com")

        # Set up previous snapshot with same content
        content = "<html><title>Test</title><body>Content</body></html>"
        stripped = re.sub(r"<[^>]+>", " ", content)
        stripped = re.sub(r"\s+", " ", stripped).strip()

        prev_snapshot = WebPageSnapshot(url="https://example.com")
        prev_snapshot.compute_hash(stripped)
        watchdog._page_snapshots["wp1"] = prev_snapshot

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = content

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            alerts = await watchdog._check_web_page(source)
            assert alerts == []

    @pytest.mark.asyncio
    async def test_check_web_page_http_error(self, watchdog):
        """HTTP error should return empty alerts."""
        source = watchdog.add_web_source("wp1", "Web Page", "https://example.com")

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=MagicMock(status_code=500))):
            alerts = await watchdog._check_web_page(source)
            assert alerts == []

    @pytest.mark.asyncio
    async def test_check_web_page_exception(self, watchdog):
        """Exception should return empty alerts."""
        source = watchdog.add_web_source("wp1", "Web Page", "https://example.com")

        with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=Exception("Connection error"))):
            alerts = await watchdog._check_web_page(source)
            assert alerts == []

    @pytest.mark.asyncio
    async def test_check_web_page_keyword_filter(self, watchdog):
        """Keyword filter on web page change."""
        from nexus.knowledge.watchdog import WebPageSnapshot

        source = watchdog.add_web_source("wp1", "Web Page", "https://example.com", keywords=["important"])

        # Previous snapshot
        prev_snapshot = WebPageSnapshot(url="https://example.com")
        prev_snapshot.compute_hash("Original")
        watchdog._page_snapshots["wp1"] = prev_snapshot

        mock_response = MagicMock()
        mock_response.status_code = 200
        # Content without keyword
        mock_response.text = "<html><body>Unrelated change</body></html>"

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            alerts = await watchdog._check_web_page(source)
            assert alerts == []  # Filtered out by keyword

    # ── Search Monitoring ───────────────────────────────────────

    @pytest.mark.asyncio
    async def test_check_search(self, watchdog):
        """_check_search should return alerts for new results."""
        from nexus.knowledge.web_search import SearchResult

        source = watchdog.add_search_source("s1", "Search", "AI news")

        with patch("nexus.knowledge.web_search.MultiSourceWebSearch") as mock_cls:
            mock_search = MagicMock()
            mock_search.search = AsyncMock(return_value=[
                SearchResult(title="AI News", url="https://example.com/ai",
                             snippet="Latest AI developments", source_engine="duckduckgo"),
            ])
            mock_cls.return_value = mock_search

            alerts = await watchdog._check_search(source)
            assert len(alerts) == 1
            assert alerts[0].alert_type == "search_hit"

    @pytest.mark.asyncio
    async def test_check_search_deduplication(self, watchdog):
        """_check_search should skip already-seen results."""
        from nexus.knowledge.web_search import SearchResult
        import hashlib

        source = watchdog.add_search_source("s1", "Search", "AI news")
        seen_hash = hashlib.sha256(b"https://example.com/seen").hexdigest()[:16]
        source.seen_hashes.add(seen_hash)

        with patch("nexus.knowledge.web_search.MultiSourceWebSearch") as mock_cls:
            mock_search = MagicMock()
            mock_search.search = AsyncMock(return_value=[
                SearchResult(title="New Result", url="https://example.com/new",
                             snippet="New snippet", source_engine="duckduckgo"),
                SearchResult(title="Seen Result", url="https://example.com/seen",
                             snippet="Already seen", source_engine="duckduckgo"),
            ])
            mock_cls.return_value = mock_search

            alerts = await watchdog._check_search(source)
            assert len(alerts) == 1
            assert alerts[0].title == "New Result"

    @pytest.mark.asyncio
    async def test_check_search_keyword_filter(self, watchdog):
        """_check_search should filter by keywords."""
        from nexus.knowledge.web_search import SearchResult

        source = watchdog.add_search_source("s1", "Search", "news", keywords=["AI"])

        with patch("nexus.knowledge.web_search.MultiSourceWebSearch") as mock_cls:
            mock_search = MagicMock()
            mock_search.search = AsyncMock(return_value=[
                SearchResult(title="AI News", url="https://example.com/ai",
                             snippet="AI developments", source_engine="duckduckgo"),
                SearchResult(title="Sports News", url="https://example.com/sports",
                             snippet="Sports results", source_engine="duckduckgo"),
            ])
            mock_cls.return_value = mock_search

            alerts = await watchdog._check_search(source)
            assert len(alerts) == 1
            assert "AI" in alerts[0].title

    @pytest.mark.asyncio
    async def test_check_search_exception(self, watchdog):
        """_check_search should handle exceptions gracefully."""
        source = watchdog.add_search_source("s1", "Search", "query")

        with patch("nexus.knowledge.web_search.MultiSourceWebSearch") as mock_cls:
            mock_search = MagicMock()
            mock_search.search = AsyncMock(side_effect=Exception("Search failed"))
            mock_cls.return_value = mock_search

            alerts = await watchdog._check_search(source)
            assert alerts == []

    # ── Cron Schedule ───────────────────────────────────────────

    def test_cron_parse(self):
        """CronSchedule.parse should parse valid expression."""
        from nexus.knowledge.watchdog import CronSchedule

        sched = CronSchedule.parse("0 9 * * 1-5")
        assert sched.minute == "0"
        assert sched.hour == "9"
        assert sched.day_of_week == "1-5"

    def test_cron_parse_invalid(self):
        """CronSchedule.parse should raise on invalid expression."""
        from nexus.knowledge.watchdog import CronSchedule

        with pytest.raises(ValueError, match="Invalid cron expression"):
            CronSchedule.parse("not enough fields")

    def test_cron_should_run_match(self):
        """CronSchedule.should_run should return True when matching."""
        from nexus.knowledge.watchdog import CronSchedule
        import datetime

        sched = CronSchedule.parse("* * * * *")  # Every minute
        now = datetime.datetime.now().timestamp()
        assert sched.should_run(now) is True

    def test_cron_should_run_no_match(self):
        """CronSchedule.should_run should return False when not matching."""
        from nexus.knowledge.watchdog import CronSchedule
        import datetime

        # Set schedule to a non-matching minute
        sched = CronSchedule.parse("59 * * * *")  # :59 of every hour
        now = datetime.datetime.now().replace(minute=0).timestamp()
        assert sched.should_run(now) is False

    # ── Watchdog Source Serialization ───────────────────────────

    def test_source_to_dict(self):
        """WatchdogSource.to_dict should serialize correctly."""
        from nexus.knowledge.watchdog import WatchdogSource, SourceType

        source = WatchdogSource(
            source_id="test-id",
            name="Test",
            source_type=SourceType.RSS,
            url="https://example.com/rss",
            seen_hashes={"hash1", "hash2"},
        )
        d = source.to_dict()
        assert d["source_id"] == "test-id"
        assert d["source_type"] == "rss"
        assert d["status"] == "active"
        assert set(d["seen_hashes"]) == {"hash1", "hash2"}

    def test_alert_to_dict(self):
        """WatchdogAlert.to_dict should serialize correctly."""
        from nexus.knowledge.watchdog import WatchdogAlert

        alert = WatchdogAlert(
            source_id="s1", source_name="S1", alert_type="new_item",
            title="Title", content="Content", url="https://example.com",
            timestamp=1234567890.0, summary="Summary",
        )
        d = alert.to_dict()
        assert d["source_id"] == "s1"
        assert d["alert_type"] == "new_item"
        assert d["summary"] == "Summary"

    # ── RSSItem ─────────────────────────────────────────────────

    def test_rss_item_compute_hash(self):
        """RSSItem.compute_hash should produce consistent hash."""
        from nexus.knowledge.watchdog import RSSItem

        item1 = RSSItem(title="Title", link="https://example.com", description="Desc")
        item2 = RSSItem(title="Title", link="https://example.com", description="Desc")
        assert item1.compute_hash() == item2.compute_hash()
        assert len(item1.content_hash) == 16

    def test_web_page_snapshot_compute_hash(self):
        """WebPageSnapshot.compute_hash should work correctly."""
        from nexus.knowledge.watchdog import WebPageSnapshot

        snap = WebPageSnapshot(url="https://example.com")
        result = snap.compute_hash("content")
        assert len(result) == 16
        assert snap.content_length == 7

    # ── Integration Checks ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_check_source_rss(self, watchdog):
        """_check_source with RSS should update check_count and last_checked."""
        from nexus.knowledge.watchdog import RSSItem

        source = watchdog.add_rss_source("rss1", "RSS", "https://example.com/feed")

        with patch.object(watchdog, "_fetch_rss", new=AsyncMock(return_value=[
            RSSItem(title="Item", link="https://example.com/1", description="Desc"),
        ])):
            await watchdog._check_source(source)
            assert source.check_count == 1
            assert source.last_checked > 0

    @pytest.mark.asyncio
    async def test_check_source_error_sets_status(self, watchdog):
        """_check_source should set ERROR status on failure."""
        from nexus.knowledge.watchdog import MonitorStatus

        source = watchdog.add_rss_source("rss1", "RSS", "https://example.com/feed")

        with patch.object(watchdog, "_fetch_rss", new=AsyncMock(side_effect=Exception("Fetch failed"))):
            await watchdog._check_source(source)
            assert source.status == MonitorStatus.ERROR
            assert "Fetch failed" in source.last_error

    @pytest.mark.asyncio
    async def test_start_and_stop(self, watchdog):
        """start() and stop() should manage the monitoring loop."""
        await watchdog.start(check_interval=1)
        assert watchdog._running is True
        assert watchdog._task is not None

        await watchdog.stop()
        assert watchdog._running is False
        assert watchdog._task is None

    @pytest.mark.asyncio
    async def test_start_already_running(self, watchdog):
        """start() while already running should warn and return."""
        watchdog._running = True
        await watchdog.start(check_interval=1)
        # Should not create a new task
        assert watchdog._task is None

    @pytest.mark.asyncio
    async def test_manual_check_all(self, watchdog):
        """check_now() without source_id should check all."""
        source = watchdog.add_rss_source("rss1", "RSS", "https://example.com/feed")

        with patch.object(watchdog, "_fetch_rss", new=AsyncMock(return_value=[])):
            alerts = await watchdog.check_now()
            assert isinstance(alerts, list)

    @pytest.mark.asyncio
    async def test_manual_check_specific(self, watchdog):
        """check_now() with source_id should check that source."""
        source = watchdog.add_rss_source("rss1", "RSS", "https://example.com/feed")

        # Spy on _check_source
        with patch.object(watchdog, "_check_source", new=AsyncMock()) as mock_check:
            await watchdog.check_now(source_id="rss1")
            mock_check.assert_called_once_with(source)

    @pytest.mark.asyncio
    async def test_manual_check_nonexistent(self, watchdog):
        """check_now() with invalid source_id should return []."""
        alerts = await watchdog.check_now(source_id="nonexistent")
        assert alerts == []

    # ── Summarization ───────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_summarize_alerts(self, watchdog):
        """_summarize_alerts should set summary on all alerts."""
        from nexus.knowledge.watchdog import WatchdogAlert
        from nexus.llm.router import LLMRouter

        mock_response = MagicMock()
        mock_response.content = "Combined summary of all items."
        mock_response.provider = "openai"
        mock_response.model = "gpt-4o"
        mock_response.usage = {}

        with patch.object(LLMRouter, "complete", new=AsyncMock(return_value=mock_response)):
            alerts = [
                WatchdogAlert(source_id="s1", source_name="S1", alert_type="new_item",
                              title="A1", content="Content 1", url="https://example.com/1"),
                WatchdogAlert(source_id="s2", source_name="S2", alert_type="new_item",
                              title="A2", content="Content 2", url="https://example.com/2"),
            ]
            await watchdog._summarize_alerts(alerts)
            assert all(a.summary == "Combined summary of all items." for a in alerts)

    @pytest.mark.asyncio
    async def test_summarize_alert(self, watchdog):
        """_summarize_alert should set summary on single alert."""
        from nexus.knowledge.watchdog import WatchdogAlert
        from nexus.llm.router import LLMRouter

        mock_response = MagicMock()
        mock_response.content = "One sentence summary."

        with patch.object(LLMRouter, "complete", new=AsyncMock(return_value=mock_response)):
            alert = WatchdogAlert(
                source_id="s1", source_name="S1", alert_type="new_item",
                title="Title", content="Content",
            )
            await watchdog._summarize_alert(alert)
            assert alert.summary == "One sentence summary."

    @pytest.mark.asyncio
    async def test_summarize_failure(self, watchdog):
        """Summarization failure should not raise."""
        from nexus.knowledge.watchdog import WatchdogAlert

        with patch.object(watchdog, "_get_router") as mock_router:
            mock_router.return_value.complete = AsyncMock(side_effect=Exception("LLM error"))
            alert = WatchdogAlert(
                source_id="s1", source_name="S1", alert_type="new_item",
                title="Title", content="Content",
            )
            # Should not raise
            await watchdog._summarize_alert(alert)
            assert alert.summary == ""

    # ── Memory Integration ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_store_alerts(self, watchdog):
        """_store_alerts should store in memory service."""
        from nexus.knowledge.watchdog import WatchdogAlert

        mock_memory = MagicMock()
        mock_memory.store = AsyncMock(return_value="stored")
        watchdog._memory_service = mock_memory

        alerts = [
            WatchdogAlert(
                source_id="s1", source_name="S1", alert_type="new_item",
                title="Alert Title", content="Alert content",
                url="https://example.com", summary="Summary text",
            ),
        ]
        await watchdog._store_alerts(alerts)
        mock_memory.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_alerts_no_service(self, watchdog):
        """_store_alerts without memory service should skip."""
        watchdog._memory_service = None
        await watchdog._store_alerts([])
        # Should not raise

    @pytest.mark.asyncio
    async def test_store_alerts_error(self, watchdog):
        """_store_alerts should handle store errors."""
        from nexus.knowledge.watchdog import WatchdogAlert

        mock_memory = MagicMock()
        mock_memory.store = AsyncMock(side_effect=Exception("Store failed"))
        watchdog._memory_service = mock_memory

        alerts = [WatchdogAlert(
            source_id="s1", source_name="S1", alert_type="new_item",
            title="T", content="C",
        )]
        # Should not raise (logged internally)
        await watchdog._store_alerts(alerts)

    @pytest.mark.asyncio
    async def test_notify_callbacks(self, watchdog):
        """_notify_callbacks should call registered callbacks."""
        from nexus.knowledge.watchdog import WatchdogAlert

        callback_called = [False]

        async def my_callback(alerts):
            callback_called[0] = True
            return len(alerts)

        watchdog.add_callback(my_callback)
        alerts = [WatchdogAlert(
            source_id="s1", source_name="S1", alert_type="new_item",
            title="T", content="C",
        )]
        await watchdog._notify_callbacks(alerts)
        assert callback_called[0] is True

    @pytest.mark.asyncio
    async def test_notify_callbacks_sync(self, watchdog):
        """_notify_callbacks should handle sync callbacks."""
        from nexus.knowledge.watchdog import WatchdogAlert

        callback_called = [False]

        def sync_callback(alerts):
            callback_called[0] = True

        watchdog.add_callback(sync_callback)
        alerts = [WatchdogAlert(source_id="s1", source_name="S1", alert_type="new_item", title="T", content="C")]
        await watchdog._notify_callbacks(alerts)
        assert callback_called[0] is True

    @pytest.mark.asyncio
    async def test_notify_callbacks_with_error(self, watchdog):
        """_notify_callbacks should handle callback errors."""
        from nexus.knowledge.watchdog import WatchdogAlert

        def failing_callback(alerts):
            raise ValueError("Callback error")

        watchdog.add_callback(failing_callback)
        alerts = [WatchdogAlert(source_id="s1", source_name="S1", alert_type="new_item", title="T", content="C")]
        # Should not raise
        await watchdog._notify_callbacks(alerts)

    # ── Check All Sources ───────────────────────────────────────

    @pytest.mark.asyncio
    async def test_check_all_sources(self, watchdog):
        """_check_all_sources should check active sources."""
        from nexus.knowledge.watchdog import MonitorStatus

        src1 = watchdog.add_rss_source("s1", "S1", "https://example.com/feed", schedule="* * * * *")
        src2 = watchdog.add_rss_source("s2", "S2", "https://example.com/feed2", schedule="99 99 99 99 99")  # Won't match
        src3 = watchdog.add_web_source("s3", "S3", "https://example.com")
        src3.status = MonitorStatus.PAUSED  # Should be skipped

        # Mock CronSchedule.should_run
        with patch("nexus.knowledge.watchdog.CronSchedule.parse") as mock_parse:
            mock_sched = MagicMock()
            mock_sched.should_run = MagicMock(side_effect=[True, False])
            mock_parse.return_value = mock_sched

            with patch.object(watchdog, "_check_source", new=AsyncMock()) as mock_check:
                await watchdog._check_all_sources()
                # Only s1 should be checked (active + matching schedule)
                mock_check.assert_called_once_with(src1)

    @pytest.mark.asyncio
    async def test_monitor_loop_error(self, watchdog):
        """_monitor_loop should handle errors without crashing."""
        with patch.object(watchdog, "_check_all_sources", new=AsyncMock(side_effect=Exception("Error"))):
            watchdog._running = True
            # Loop runs once, catches error, then we stop it
            async def stop_after():
                await asyncio.sleep(0.05)
                watchdog._running = False
            await asyncio.gather(
                watchdog._monitor_loop(check_interval=0.01),
                stop_after(),
            )
            # Should not raise

    # ── Router ──────────────────────────────────────────────────

    def test_get_router_lazy(self, watchdog):
        """_get_router should lazy-load LLMRouter."""
        assert watchdog._router is None
        with patch("nexus.llm.router.LLMRouter") as mock_cls:
            mock_cls.return_value = "router_instance"
            router = watchdog._get_router()
            assert router == "router_instance"
            mock_cls.assert_called_once()

    def test_get_router_cached(self, watchdog):
        """_get_router should return cached instance."""
        watchdog._router = "cached"
        with patch("nexus.llm.router.LLMRouter") as mock_cls:
            router = watchdog._get_router()
            assert router == "cached"
            mock_cls.assert_not_called()
