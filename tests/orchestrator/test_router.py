"""
Tests for nexus.orchestrator.router.
"""

import pytest
from nexus.orchestrator.router import (
    OrchestrationRouter,
    RoutingDecision,
    RoutingLog,
    TaskAnalysis,
    TaskAnalyzer,
    TaskStructure,
    CollaborationStyle,
    EngineType,
    OrchestratorError,
)


class TestOrchestrationRouter:
    """Test cases for OrchestrationRouter."""

    @pytest.fixture
    def router(self):
        return OrchestrationRouter()

    def test_init(self, router):
        assert router is not None


class TestCollaborationStyle:
    """Test cases for CollaborationStyle enum."""

    def test_all_styles(self):
        """All collaboration styles should exist."""
        assert CollaborationStyle.SEQUENTIAL.value == "sequential"
        assert CollaborationStyle.PARALLEL.value == "parallel"
        assert CollaborationStyle.COLLABORATIVE.value == "collaborative"
        assert CollaborationStyle.HIERARCHICAL.value == "hierarchical"


class TestEngineType:
    """Test cases for EngineType enum."""

    def test_all_engines(self):
        """All engine types should exist."""
        assert EngineType.LANGGRAPH.value == "langgraph"
        assert EngineType.CREWAI.value == "crewai"
        assert EngineType.ADK.value == "adk"


class TestTaskStructure:
    """Test cases for TaskStructure enum."""

    def test_all_structures(self):
        """All task structures should exist."""
        assert TaskStructure.STRUCTURED.value == "structured"
        assert TaskStructure.SEMI_STRUCTURED.value == "semi"
        assert TaskStructure.UNSTRUCTURED.value == "unstructured"


class TestRoutingDecision:
    """Test cases for RoutingDecision."""

    def test_creation(self):
        """RoutingDecision creation."""
        analysis = TaskAnalysis(task="Test task")
        decision = RoutingDecision(
            engine=EngineType.LANGGRAPH,
            task_analysis=analysis
        )
        assert decision.engine == EngineType.LANGGRAPH
        assert decision.task_analysis.task == "Test task"


class TestTaskAnalysis:
    """Test cases for TaskAnalysis."""

    def test_creation(self):
        """TaskAnalysis creation."""
        analysis = TaskAnalysis(
            task="Test task",
            complexity="medium",
            structure=TaskStructure.STRUCTURED
        )
        assert analysis.task == "Test task"
        assert analysis.complexity == "medium"

    def test_creation_with_defaults(self):
        """TaskAnalysis with defaults."""
        analysis = TaskAnalysis(task="Simple task")
        assert analysis.complexity == "medium"
        assert analysis.collaboration == CollaborationStyle.SEQUENTIAL


class TestTaskAnalyzer:
    """Test cases for TaskAnalyzer."""

    def test_analyze(self):
        """TaskAnalyzer should have analyze method."""
        analyzer = TaskAnalyzer()
        assert hasattr(analyzer, 'analyze')


class TestOrchestratorError:
    """Test cases for OrchestratorError."""

    def test_error_creation(self):
        """OrchestratorError creation."""
        error = OrchestratorError("Test error")
        assert "Test error" in str(error)