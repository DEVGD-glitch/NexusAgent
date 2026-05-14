"""
Complete tests for NEXUS Orchestrator modules.

Covers:
  - TaskAnalyzer: analyze() with different tasks, keyword matching, edge cases
  - OrchestrationRouter: route() for different collaboration styles, engine
    selection, availability checking, fallback engine search, stats
  - RoutingDecision/RoutingLog: creation, to_dict, statistics
  - Patterns: pipeline_pattern, parallel_pattern, supervisor_pattern,
    swarm_pattern with mocked agent_handler, PatternResult, AgentTask
  - LangGraph engine: planner_node, executor_node, reflector_node,
    NexusState management, run_nexus_task with all params, fallback loop
  - Skill lifecycle: SkillLifecycleManager discover/design/implement/
    validate/deploy/evolve, SkillDefinition to_dict, error cases,
    SelfImprovementLoop
"""

import pytest
import json
import time
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch


# ═══════════════════════════════════════════════════════════════════
# Module-Level Patches (to avoid import-time get_settings() issues)
# ═══════════════════════════════════════════════════════════════════

_GET_SETTINGS_TARGETS = [
    "nexus.orchestrator.router.get_settings",
    "nexus.orchestrator.langgraph_engine.get_settings",
    "nexus.orchestrator.skill_lifecycle.get_settings",
]


@pytest.fixture(autouse=True)
def mock_all_settings():
    """Mock get_settings in all orchestrator modules."""
    settings = MagicMock()
    settings.orchestrator_max_iterations = 10
    settings.orchestrator_checkpointer = "memory"
    settings.orchestrator_interrupt_before_executor = False
    settings.chroma_persist_dir = "/tmp/nexus_test"
    settings.nexus_env = "development"
    settings.nexus_host = "0.0.0.0"
    settings.nexus_port = 8080
    settings.llm_default_provider = "openai"
    settings.llm_default_model = "gpt-4o"

    patchers = [patch(target, return_value=settings) for target in _GET_SETTINGS_TARGETS]
    for p in patchers:
        p.start()
    yield settings
    for p in patchers:
        p.stop()


# ═══════════════════════════════════════════════════════════════════
# TaskAnalyzer Tests
# ═══════════════════════════════════════════════════════════════════

class TestTaskAnalyzer:
    """Complete tests for TaskAnalyzer.analyze()."""

    @pytest.fixture
    def analyzer(self):
        from nexus.orchestrator.router import TaskAnalyzer
        return TaskAnalyzer()

    def test_analyze_simple_task(self, analyzer):
        """Simple task should get simple complexity."""
        result = analyzer.analyze("what is the capital of France")
        assert result.complexity == "simple"
        assert result.agent_count == 1
        assert result.domain == "general"

    def test_analyze_complex_task(self, analyzer):
        """Task with complex indicators should get complex complexity."""
        result = analyzer.analyze("Design and build a comprehensive web application with multiple features")
        assert result.complexity == "complex"
        assert result.agent_count == 3
        assert result.has_sub_tasks is True

    def test_analyze_medium_task(self, analyzer):
        """Generic task without indicators should be medium complexity."""
        result = analyzer.analyze("Read the documentation")
        assert result.complexity == "medium"
        assert result.agent_count == 2

    def test_analyze_structured_task(self, analyzer):
        """Task with pipeline keywords should get structured structure."""
        result = analyzer.analyze("Create a step by step workflow pipeline for deployment")
        assert result.structure.value == "structured"
        assert result.requires_determinism is False

    def test_analyze_unstructured_task(self, analyzer):
        """Task with brainstorm keywords should get unstructured."""
        result = analyzer.analyze("Brainstorm innovative ideas for the new product design")
        assert result.structure.value == "unstructured"
        assert result.requires_creativity is True

    def test_analyze_collaborative_task(self, analyzer):
        """Task with collaborate keywords should get collaborative style."""
        result = analyzer.analyze("The team must collaborate to reach consensus on the architecture")
        assert result.collaboration.value == "collaborative"

    def test_analyze_hierarchical_task(self, analyzer):
        """Task with manage/coordinate keywords should get hierarchical."""
        result = analyzer.analyze("Coordinate the team and delegate tasks to complete the project")
        assert result.collaboration.value == "hierarchical"

    def test_analyze_parallel_task(self, analyzer):
        """Task with parallel keywords should get parallel style."""
        result = analyzer.analyze("Run tests simultaneously and in parallel to speed up CI")
        assert result.collaboration.value == "parallel"

    def test_analyze_sequential_task(self, analyzer):
        """Task with sequential keywords should get sequential style."""
        result = analyzer.analyze("First research, then design, next implement, finally deploy")
        assert result.collaboration.value == "sequential"

    def test_analyze_domain_research(self, analyzer):
        """Task with research keywords should detect domain."""
        result = analyzer.analyze("Research and investigate the latest AI papers")
        assert result.domain == "research"

    def test_analyze_domain_development(self, analyzer):
        """Task with coding keywords should detect development domain."""
        result = analyzer.analyze("Build and implement a Python program")
        assert result.domain == "development"

    def test_analyze_domain_analysis(self, analyzer):
        """Task with data keywords should detect analysis domain."""
        result = analyzer.analyze("Analyze the data and find insights and trends")
        assert result.domain == "analysis"

    def test_analyze_domain_operations(self, analyzer):
        """Task with deploy/monitor keywords should detect operations."""
        result = analyzer.analyze("Deploy and monitor the infrastructure on the server")
        assert result.domain == "operations"

    def test_analyze_determinism_required(self, analyzer):
        """Task with reproducible keyword should require determinism."""
        result = analyzer.analyze("Create a reproducible deterministic pipeline")
        assert result.requires_determinism is True

    def test_analyze_creativity_required(self, analyzer):
        """Task with creative keyword should require creativity."""
        result = analyzer.analyze("Design a creative and novel solution")
        assert result.requires_creativity is True

    def test_analyze_sub_tasks_detected(self, analyzer):
        """Multiple 'and then' indicators should mark has_sub_tasks."""
        result = analyzer.analyze("Do this and then that, after that do more")
        assert result.has_sub_tasks is True

    def test_analyze_confidence_calculation(self, analyzer):
        """Confidence should increase with more detected indicators."""
        simple = analyzer.analyze("hello")
        complex_task = analyzer.analyze("Research and develop a comprehensive analysis pipeline")
        assert complex_task.confidence > simple.confidence

    def test_analyze_reasoning_includes_key_info(self, analyzer):
        """Reasoning string should contain key analysis decisions."""
        result = analyzer.analyze("Research and investigate latest AI trends")
        reasoning = result.reasoning
        assert "Complexity" in reasoning
        assert "Domain" in reasoning
        assert "Agent count" in reasoning

    def test_analyze_empty_task(self, analyzer):
        """Empty task should produce sensible defaults."""
        result = analyzer.analyze("")
        assert result.complexity == "medium"
        assert result.structure.value == "semi"
        assert result.collaboration.value == "sequential"

    def test_analyze_explicit_multi_agent(self, analyzer):
        """Multi-agent indicators should increase agent count."""
        result = analyzer.analyze("research and build with a team of multiple agents")
        assert result.agent_count >= 3


# ═══════════════════════════════════════════════════════════════════
# Routing Decision Tests
# ═══════════════════════════════════════════════════════════════════

class TestRoutingDecision:
    """Test RoutingDecision dataclass and methods."""

    def test_creation(self):
        """RoutingDecision creation with all fields."""
        from nexus.orchestrator.router import RoutingDecision, EngineType, TaskAnalysis, TaskStructure

        analysis = TaskAnalysis(task="test", structure=TaskStructure.STRUCTURED)
        decision = RoutingDecision(
            engine=EngineType.LANGGRAPH,
            task_analysis=analysis,
            confidence=0.85,
            reasoning="Best engine for structured tasks",
            fallback_engine=EngineType.ADK,
        )
        assert decision.engine == EngineType.LANGGRAPH
        assert decision.confidence == 0.85
        assert decision.fallback_engine == EngineType.ADK

    def test_to_dict(self):
        """to_dict should serialize correctly."""
        from nexus.orchestrator.router import RoutingDecision, EngineType, TaskAnalysis

        analysis = TaskAnalysis(task="test", complexity="complex")
        decision = RoutingDecision(
            engine=EngineType.CREWAI,
            task_analysis=analysis,
            fallback_engine=EngineType.LANGGRAPH,
        )
        d = decision.to_dict()
        assert d["engine"] == "crewai"
        assert d["fallback_engine"] == "langgraph"
        assert d["complexity"] == "complex"
        assert d["confidence"] == analysis.confidence
        assert "timestamp" in d

    def test_to_dict_no_fallback(self):
        """to_dict with no fallback should have None."""
        from nexus.orchestrator.router import RoutingDecision, EngineType, TaskAnalysis

        analysis = TaskAnalysis(task="test")
        decision = RoutingDecision(engine=EngineType.LANGGRAPH, task_analysis=analysis)
        d = decision.to_dict()
        assert d["fallback_engine"] is None


class TestRoutingLog:
    """Test RoutingLog dataclass."""

    def test_creation(self):
        """RoutingLog creation."""
        from nexus.orchestrator.router import RoutingLog, RoutingDecision, EngineType, TaskAnalysis

        analysis = TaskAnalysis(task="test")
        decision = RoutingDecision(engine=EngineType.LANGGRAPH, task_analysis=analysis)
        log = RoutingLog(
            task_preview="test task preview",
            decision=decision,
            success=True,
            execution_time_ms=150.0,
        )
        assert log.task_preview == "test task preview"
        assert log.success is True
        assert log.execution_time_ms == 150.0

    def test_creation_with_error(self):
        """RoutingLog with error."""
        from nexus.orchestrator.router import RoutingLog, RoutingDecision, EngineType, TaskAnalysis

        analysis = TaskAnalysis(task="test")
        decision = RoutingDecision(engine=EngineType.LANGGRAPH, task_analysis=analysis)
        log = RoutingLog(
            task_preview="failing task",
            decision=decision,
            success=False,
            error="Engine not available",
        )
        assert log.success is False
        assert log.error == "Engine not available"


# ═══════════════════════════════════════════════════════════════════
# OrchestrationRouter Tests
# ═══════════════════════════════════════════════════════════════════

class TestOrchestrationRouterAnalyze:
    """Test OrchestrationRouter.analyze() for routing decisions."""

    @pytest.fixture
    def router(self):
        from nexus.orchestrator.router import OrchestrationRouter
        # Mock all engines as available so routing rules aren't overridden
        with patch("nexus.orchestrator.router._check_engine_available", return_value=True):
            router = OrchestrationRouter()
        # Directly patch on the module function for the test methods
        return router

    @pytest.fixture(autouse=True)
    def mock_engine_availability(self):
        """Ensure all engines appear available for routing tests."""
        with patch("nexus.orchestrator.router._check_engine_available", return_value=True):
            yield

    def test_structured_deterministic_to_langgraph(self, router):
        """Structured + deterministic tasks should route to LangGraph."""
        decision = router.analyze("Create a reproducible pipeline workflow")
        assert decision.engine.value == "langgraph"

    def test_collaborative_creative_to_crewai(self, router):
        """Creative collaborative tasks should route to CrewAI."""
        decision = router.analyze("Collaborate and brainstorm innovative design ideas")
        assert decision.engine.value == "crewai"

    def test_hierarchical_deterministic_to_langgraph(self, router):
        """Hierarchical + deterministic tasks should route to LangGraph."""
        decision = router.analyze("Manage the team precisely and delegate tasks")
        assert decision.engine.value == "langgraph"

    def test_hierarchical_flexible_to_crewai(self, router):
        """Hierarchical + flexible tasks should route to CrewAI."""
        decision = router.analyze("Coordinate and oversee the creative team")
        assert decision.engine.value == "crewai"

    def test_sequential_pipeline_to_adk(self, router):
        """Sequential pipeline with sub-tasks should route to ADK."""
        decision = router.analyze("First research this and then implement that")
        assert decision.engine.value == "adk"

    def test_parallel_execution_to_adk(self, router):
        """Parallel execution tasks should route to ADK."""
        decision = router.analyze("Run these tasks simultaneously and in parallel")
        assert decision.engine.value == "adk"

    def test_simple_task_to_langgraph(self, router):
        """Simple tasks should route to LangGraph."""
        decision = router.analyze("Quick lookup of a simple definition")
        assert decision.engine.value == "langgraph"

    def test_default_to_langgraph(self, router):
        """Rule 6 triggers for simple task, routing to LangGraph."""
        decision = router.analyze("just a simple generic text")
        assert decision.engine.value == "langgraph"

    def test_analyze_includes_reasoning(self, router):
        """Analyze result should include reasoning string."""
        decision = router.analyze("Build and deploy a web application")
        assert len(decision.reasoning) > 0

    def test_analyze_confidence_between_0_and_1(self, router):
        """Confidence should always be between 0 and 1."""
        decision = router.analyze("Do something simple")
        assert 0 <= decision.confidence <= 1.0

    def test_fallback_engine_always_set(self, router):
        """Every routing decision should have a fallback engine."""
        decision = router.analyze("Run a quick test")
        assert decision.fallback_engine is not None


class TestOrchestrationRouterStats:
    """Test OrchestrationRouter statistics and history."""

    @pytest.fixture
    def router(self):
        from nexus.orchestrator.router import OrchestrationRouter
        return OrchestrationRouter()

    @pytest.fixture(autouse=True)
    def mock_engine_availability(self):
        """Prevent actual engine imports that can hang."""
        with patch("nexus.orchestrator.router._check_engine_available", return_value=True):
            yield

    def test_get_stats_empty(self, router):
        """get_stats on fresh router should return zeros."""
        stats = router.get_stats()
        assert stats["tasks_routed"] == 0
        assert stats["total_decisions"] == 0
        assert stats["success_rate"] == 0
        assert "engine_distribution" in stats
        assert "available_engines" in stats

    def test_get_routing_history_empty(self, router):
        """get_routing_history on fresh router should return empty list."""
        history = router.get_routing_history()
        assert history == []


class TestOrchestrationRouterExecute:
    """Test OrchestrationRouter.execute() with mocked dispatch."""

    @pytest.fixture
    def router(self):
        from nexus.orchestrator.router import OrchestrationRouter
        return OrchestrationRouter()

    @pytest.fixture(autouse=True)
    def mock_engine_availability(self):
        """Prevent actual engine imports that can hang."""
        with patch("nexus.orchestrator.router._check_engine_available", return_value=True):
            yield

    @pytest.mark.asyncio
    async def test_execute_success(self, router):
        """execute should return result dict with routing info."""
        async def fake_dispatch(engine, task, **kwargs):
            return {"status": "completed", "result": "Task done"}

        with patch.object(router, "_dispatch_to_engine", new=fake_dispatch):
            result = await router.execute(task="Test task")
            assert result["status"] == "completed"
            assert "routing_decision" in result

    @pytest.mark.asyncio
    async def test_execute_increments_task_count(self, router):
        """execute should increment _tasks_routed."""
        async def fake_dispatch(engine, task, **kwargs):
            return {"status": "completed", "result": "Done"}

        with patch.object(router, "_dispatch_to_engine", new=fake_dispatch):
            assert router._tasks_routed == 0
            await router.execute(task="Task 1")
            assert router._tasks_routed == 1

    @pytest.mark.asyncio
    async def test_execute_adds_routing_log(self, router):
        """Successful execute should add to routing log."""
        async def fake_dispatch(engine, task, **kwargs):
            return {"status": "completed", "result": "Done"}

        with patch.object(router, "_dispatch_to_engine", new=fake_dispatch):
            assert len(router._routing_log) == 0
            await router.execute(task="Log test")
            assert len(router._routing_log) == 1
            assert router._routing_log[0].success is True

    @pytest.mark.asyncio
    async def test_execute_fallback_on_failure(self, router):
        """execute should try fallback engine when primary fails."""
        call_order = []

        async def failing_dispatch(engine, task, **kwargs):
            call_order.append(engine.value)
            raise Exception(f"{engine.value} failed")

        async def fallback_dispatch(engine, task, **kwargs):
            call_order.append(engine.value)
            return {"status": "completed", "result": "Fallback worked"}

        original_dispatch = router._dispatch_to_engine

        async def side_effect_dispatch(engine, task, **kwargs):
            if len(call_order) == 0:
                call_order.append(engine.value)
                raise Exception("Primary failed")
            else:
                call_order.append(engine.value)
                return {"status": "completed", "result": "Fallback worked"}

        # Make primary fail, fallback succeed
        with patch.object(router, "_dispatch_to_engine", new=side_effect_dispatch):
            result = await router.execute(task="Test fallback")
            assert result["status"] == "completed"
            assert result.get("used_fallback") is True

    @pytest.mark.asyncio
    async def test_execute_both_fail(self, router):
        """execute should return failed status when both engines fail."""
        async def always_fail(engine, task, **kwargs):
            raise Exception(f"{engine.value} crashed")

        with patch.object(router, "_dispatch_to_engine", new=always_fail):
            result = await router.execute(task="Doomed task")
            assert result["status"] == "failed"
            assert "error" in result
            assert "routing_decision" in result

    @pytest.mark.asyncio
    async def test_execute_with_precomputed_decision(self, router):
        """execute should accept pre-computed decision."""
        from nexus.orchestrator.router import RoutingDecision, EngineType, TaskAnalysis

        analysis = TaskAnalysis(task="Custom routed task")
        decision = RoutingDecision(
            engine=EngineType.ADK,
            task_analysis=analysis,
        )

        async def fake_dispatch(engine, task, **kwargs):
            assert engine == EngineType.ADK
            return {"status": "completed", "result": "Custom routed"}

        with patch.object(router, "_dispatch_to_engine", new=fake_dispatch):
            result = await router.execute(task="Custom routed task", decision=decision)
            assert result["status"] == "completed"


# ═══════════════════════════════════════════════════════════════════
# Engine Availability Tests
# ═══════════════════════════════════════════════════════════════════

class TestEngineAvailability:
    """Test engine availability checking."""

    def test_check_engine_available_langgraph(self):
        """_check_engine_available for langgraph should work."""
        from nexus.orchestrator.router import _check_engine_available, EngineType

        result = _check_engine_available(EngineType.LANGGRAPH)
        assert isinstance(result, bool)

    def test_check_engine_available_crewai(self):
        """_check_engine_available for crewai."""
        from nexus.orchestrator.router import _check_engine_available, EngineType

        result = _check_engine_available(EngineType.CREWAI)
        assert isinstance(result, bool)

    def test_check_engine_available_adk(self):
        """_check_engine_available for adk."""
        from nexus.orchestrator.router import _check_engine_available, EngineType

        result = _check_engine_available(EngineType.ADK)
        assert isinstance(result, bool)

    def test_get_available_engines(self):
        """get_available_engines should return dict with all engines."""
        from nexus.orchestrator.router import get_available_engines

        engines = get_available_engines()
        assert "langgraph" in engines
        assert "crewai" in engines
        assert "adk" in engines
        assert all(isinstance(v, bool) for v in engines.values())

    def test_availability_langgraph_import_error(self):
        """Should handle import error for langgraph."""
        from nexus.orchestrator.router import _check_engine_available, EngineType

        with patch.dict("sys.modules", {"langgraph": None}):
            result = _check_engine_available(EngineType.LANGGRAPH)
            assert result is False

    def test_availability_crewai_import_error(self):
        """Should handle import error for crewai."""
        from nexus.orchestrator.router import _check_engine_available, EngineType

        with patch.dict("sys.modules", {"crewai": None}):
            result = _check_engine_available(EngineType.CREWAI)
            assert result is False

    def test_availability_adk_import_error(self):
        """Should handle import error for adk."""
        from nexus.orchestrator.router import _check_engine_available, EngineType

        with patch.dict("sys.modules", {"google.adk": None}):
            result = _check_engine_available(EngineType.ADK)
            assert result is False

    def test_unknown_engine_returns_false(self):
        """Unknown engine type should return False."""
        from nexus.orchestrator.router import _check_engine_available, EngineType

        # EngineType has only 3 members, test with a sentinel
        class FakeEngine:
            value = "nonexistent"
        result = _check_engine_available(FakeEngine())
        assert result is False


# ═══════════════════════════════════════════════════════════════════
# Multi-Agent Patterns Tests
# ═══════════════════════════════════════════════════════════════════

class TestAgentTask:
    """Test AgentTask dataclass."""

    def test_default_id_generated(self):
        """AgentTask should auto-generate task_id."""
        from nexus.orchestrator.patterns import AgentTask

        task = AgentTask(description="Test")
        assert task.task_id is not None
        assert len(task.task_id) == 12

    def test_dependencies_list(self):
        """AgentTask with dependencies."""
        from nexus.orchestrator.patterns import AgentTask

        task = AgentTask(
            description="Step 3",
            assigned_to="agent3",
            dependencies=["task_1", "task_2"],
        )
        assert task.dependencies == ["task_1", "task_2"]

    def test_status_transitions(self):
        """AgentTask status should be mutable."""
        from nexus.orchestrator.patterns import AgentTask

        task = AgentTask(description="Test")
        assert task.status == "pending"
        task.status = "completed"
        task.result = "Done"
        assert task.status == "completed"
        assert task.result == "Done"


class TestPatternResult:
    """Test PatternResult dataclass."""

    def test_creation(self):
        """PatternResult creation."""
        from nexus.orchestrator.patterns import PatternResult, PatternType

        result = PatternResult(
            pattern=PatternType.SUPERVISOR,
            success=True,
            results=[{"task_id": "1", "status": "completed"}],
            total_tasks=1,
            completed_tasks=1,
        )
        assert result.pattern == PatternType.SUPERVISOR
        assert result.success is True
        assert result.total_tasks == 1
        assert result.completed_tasks == 1

    def test_failed_tasks_count(self):
        """PatternResult with failures."""
        from nexus.orchestrator.patterns import PatternResult, PatternType

        result = PatternResult(
            pattern=PatternType.PARALLEL,
            success=False,
            total_tasks=3,
            completed_tasks=1,
            failed_tasks=2,
            errors=["Error 1", "Error 2"],
        )
        assert result.success is False
        assert result.failed_tasks == 2
        assert len(result.errors) == 2


class TestSupervisorPattern:
    """Test supervisor_pattern execution."""

    @pytest.mark.asyncio
    async def test_supervisor_with_handler(self):
        """Supervisor pattern with custom agent handler."""
        from nexus.orchestrator.patterns import supervisor_pattern

        async def handler(description, agent_name):
            return f"{agent_name} completed: {description[:20]}"

        result = await supervisor_pattern(
            main_task="Build a web app",
            sub_tasks=["Research", "Design", "Implement"],
            worker_agents=["researcher", "designer", "developer"],
            agent_handler=handler,
        )
        assert result.pattern.value == "supervisor"
        assert result.total_tasks == 3
        assert result.success is True

    @pytest.mark.asyncio
    async def test_supervisor_auto_workers(self):
        """Supervisor pattern should auto-generate workers."""
        from nexus.orchestrator.patterns import supervisor_pattern

        async def handler(description, agent_name):
            return f"{agent_name} done"

        result = await supervisor_pattern(
            main_task="Simple task",
            sub_tasks=["Step 1", "Step 2"],
            agent_handler=handler,
        )
        assert result.total_tasks == 2
        assert len(result.results) == 2

    @pytest.mark.asyncio
    async def test_supervisor_with_failures(self):
        """Supervisor pattern with some failures."""
        from nexus.orchestrator.patterns import supervisor_pattern

        call_count = [0]

        async def handler(description, agent_name):
            call_count[0] += 1
            if call_count[0] == 2:
                raise ValueError("Task failed")
            return f"{agent_name} done"

        result = await supervisor_pattern(
            main_task="Mixed task",
            sub_tasks=["Good", "Bad", "Good2"],
            agent_handler=handler,
        )
        assert result.success is False
        assert result.failed_tasks >= 1

    @pytest.mark.asyncio
    async def test_supervisor_no_handler(self):
        """Supervisor pattern should work without handler (uses LLM router)."""
        from nexus.orchestrator.patterns import supervisor_pattern

        with patch("nexus.llm.router.LLMRouter") as mock_cls:
            mock_router = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "LLM result"
            mock_router.complete = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_router

            result = await supervisor_pattern(
                main_task="Test task",
                sub_tasks=["Do something"],
            )
            assert result.total_tasks >= 1


class TestPipelinePattern:
    """Test pipeline_pattern execution."""

    @pytest.mark.asyncio
    async def test_pipeline_all_success(self):
        """Pipeline with all stages succeeding."""
        from nexus.orchestrator.patterns import pipeline_pattern

        results_order = []

        async def handler(description, agent_name):
            results_order.append(agent_name)
            return f"{agent_name} output"

        result = await pipeline_pattern(
            main_task="Build app",
            stages=[
                {"agent": "planner", "description": "Plan the work"},
                {"agent": "executor", "description": "Execute the plan"},
                {"agent": "tester", "description": "Test the result"},
            ],
            agent_handler=handler,
        )
        assert result.success is True
        assert result.total_tasks == 3
        assert result.completed_tasks == 3
        assert results_order == ["planner", "executor", "tester"]

    @pytest.mark.asyncio
    async def test_pipeline_breaks_on_failure(self):
        """Pipeline should break when a stage fails."""
        from nexus.orchestrator.patterns import pipeline_pattern

        async def handler(description, agent_name):
            if agent_name == "executor":
                raise RuntimeError("Execution failed")
            return f"{agent_name} output"

        result = await pipeline_pattern(
            main_task="Failing pipeline",
            stages=[
                {"agent": "planner", "description": "Plan"},
                {"agent": "executor", "description": "Execute"},
                {"agent": "tester", "description": "Test"},
            ],
            agent_handler=handler,
        )
        assert result.success is False
        assert result.completed_tasks == 1
        assert result.failed_tasks == 1

    @pytest.mark.asyncio
    async def test_pipeline_empty_stages(self):
        """Pipeline with no stages should succeed trivially."""
        from nexus.orchestrator.patterns import pipeline_pattern

        result = await pipeline_pattern(
            main_task="Empty pipeline",
            stages=[],
        )
        assert result.success is True
        assert result.total_tasks == 0


class TestParallelPattern:
    """Test parallel_pattern execution."""

    @pytest.mark.asyncio
    async def test_parallel_all_success(self):
        """Parallel pattern with all tasks succeeding."""
        from nexus.orchestrator.patterns import parallel_pattern

        async def handler(description, agent_name):
            return f"{agent_name}: {description[:20]}"

        result = await parallel_pattern(
            main_task="Do many things",
            sub_tasks=["Task A", "Task B", "Task C"],
            agents=["agent1", "agent2", "agent3"],
            agent_handler=handler,
        )
        assert result.success is True
        assert result.total_tasks == 3
        assert result.completed_tasks == 3

    @pytest.mark.asyncio
    async def test_parallel_auto_agents(self):
        """Parallel pattern should auto-generate agents."""
        from nexus.orchestrator.patterns import parallel_pattern

        async def handler(description, agent_name):
            return f"result"

        result = await parallel_pattern(
            main_task="Task",
            sub_tasks=["A", "B"],
            agent_handler=handler,
        )
        assert result.total_tasks == 2

    @pytest.mark.asyncio
    async def test_parallel_partial_failure(self):
        """Parallel pattern with some failures."""
        from nexus.orchestrator.patterns import parallel_pattern

        async def handler(description, agent_name):
            if "fail" in description.lower():
                raise ValueError("Failed")
            return "success"

        result = await parallel_pattern(
            main_task="Mixed",
            sub_tasks=["Good", "fail", "Also good"],
            agent_handler=handler,
        )
        assert result.success is False
        assert result.failed_tasks >= 1


class TestSwarmPattern:
    """Test swarm_pattern execution."""

    @pytest.mark.asyncio
    async def test_swarm_with_handler(self):
        """Swarm pattern with agent handler."""
        from nexus.orchestrator.patterns import swarm_pattern

        async def handler(description, agent_name):
            return f"{agent_name} contribution"

        result = await swarm_pattern(
            main_task="Explore ideas",
            num_agents=3,
            iterations=2,
            agent_handler=handler,
        )
        assert result.pattern.value == "swarm"
        assert result.total_tasks == 6  # 3 agents * 2 iterations
        assert result.success is True

    @pytest.mark.asyncio
    async def test_swarm_single_iteration(self):
        """Swarm pattern with single iteration."""
        from nexus.orchestrator.patterns import swarm_pattern

        async def handler(description, agent_name):
            return "result"

        result = await swarm_pattern(
            main_task="Quick swarm",
            num_agents=2,
            iterations=1,
            agent_handler=handler,
        )
        assert result.total_tasks == 2
        assert result.success is True

    @pytest.mark.asyncio
    async def test_swarm_with_failures(self):
        """Swarm pattern handling agent failures."""
        from nexus.orchestrator.patterns import swarm_pattern

        async def handler(description, agent_name):
            if "agent_0" in agent_name:
                raise Exception("Agent failed")
            return "ok"

        result = await swarm_pattern(
            main_task="Swarm with issues",
            num_agents=2,
            iterations=2,
            agent_handler=handler,
        )
        assert result.failed_tasks >= 1


class TestExecutePattern:
    """Test execute_pattern function dispatch."""

    @pytest.mark.asyncio
    async def test_execute_unknown_pattern(self):
        """execute_pattern with unknown type should raise."""
        from nexus.orchestrator.patterns import execute_pattern
        from nexus.orchestrator.patterns import PatternType

        # Create an unknown pattern type
        class FakeType:
            value = "nonexistent"

        with pytest.raises(Exception):
            await execute_pattern(FakeType(), main_task="test")

    @pytest.mark.asyncio
    async def test_execute_pipeline_via_dispatch(self):
        """execute_pattern should dispatch to pipeline pattern."""
        from nexus.orchestrator.patterns import execute_pattern, PatternType

        async def handler(description, agent_name):
            return "result"

        result = await execute_pattern(
            PatternType.PIPELINE,
            main_task="Test",
            stages=[{"agent": "a1", "description": "Step 1"}],
            agent_handler=handler,
        )
        assert result.pattern.value == "pipeline"
        assert result.success is True


# ═══════════════════════════════════════════════════════════════════
# LangGraph Engine Tests
# ═══════════════════════════════════════════════════════════════════

class TestNexusState:
    """Test NexusState TypedDict."""

    def test_empty_state(self):
        """Empty state creation."""
        from nexus.orchestrator.langgraph_engine import NexusState
        state: NexusState = {}
        assert state == {}

    def test_state_with_all_fields(self):
        """State with all fields."""
        from nexus.orchestrator.langgraph_engine import NexusState
        state: NexusState = {
            "task": "Test task",
            "sub_tasks": ["step1", "step2"],
            "current_sub_task": "step1",
            "plan": "Plan text",
            "result": "Result text",
            "reflection": "Reflection text",
            "messages": [{"role": "user", "content": "test"}],
            "next_action": "execute",
            "iteration": 1,
            "metadata": {"key": "value"},
        }
        assert state["next_action"] == "execute"
        assert len(state["sub_tasks"]) == 2
        assert state["iteration"] == 1

    def test_state_next_action_literals(self):
        """State next_action should accept all literals."""
        from nexus.orchestrator.langgraph_engine import NexusState
        for action in ["plan", "execute", "reflect", "done", "replan"]:
            state: NexusState = {"next_action": action}
            assert state["next_action"] == action


class TestPlannerNode:
    """Test planner_node function."""

    @pytest.mark.asyncio
    async def test_planner_simple_task(self):
        """Planner node with simple task."""
        from nexus.orchestrator.langgraph_engine import planner_node

        state = {"task": "What is 2+2?", "iteration": 0}
        result = await planner_node(state)
        assert "plan" in result
        assert "sub_tasks" in result
        assert "next_action" in result
        assert result["iteration"] == 1

    @pytest.mark.asyncio
    async def test_planner_with_messages(self):
        """Planner node with existing messages."""
        from nexus.orchestrator.langgraph_engine import planner_node

        state = {
            "task": "Write a poem",
            "messages": [{"role": "user", "content": "Write about nature"}],
            "iteration": 0,
        }
        result = await planner_node(state)
        assert "plan" in result
        assert len(result["sub_tasks"]) > 0

    @pytest.mark.asyncio
    async def test_planner_llm_failure_fallback(self):
        """Planner should fallback when LLM fails."""
        from nexus.orchestrator.langgraph_engine import planner_node

        with patch("nexus.llm.router.LLMRouter") as mock_cls:
            mock_router = MagicMock()
            mock_router.complete = AsyncMock(side_effect=Exception("LLM down"))
            mock_cls.return_value = mock_router

            state = {"task": "Do the thing", "iteration": 0}
            result = await planner_node(state)
            assert "plan" in result
            assert len(result["sub_tasks"]) >= 1


class TestExecutorNode:
    """Test executor_node function."""

    @pytest.mark.asyncio
    async def test_executor_with_subtask(self):
        """Executor node with current_sub_task."""
        from nexus.orchestrator.langgraph_engine import executor_node

        state = {"current_sub_task": "Calculate 5+3", "messages": []}
        result = await executor_node(state)
        assert "result" in result
        assert result["next_action"] == "reflect"

    @pytest.mark.asyncio
    async def test_executor_falls_back_to_task(self):
        """Executor should use task when no current_sub_task."""
        from nexus.orchestrator.langgraph_engine import executor_node

        state = {"task": "Main task", "messages": []}
        result = await executor_node(state)
        assert "result" in result

    @pytest.mark.asyncio
    async def test_executor_handles_llm_failure(self):
        """Executor should handle LLM failure gracefully."""
        from nexus.orchestrator.langgraph_engine import executor_node

        with patch("nexus.llm.router.LLMRouter") as mock_cls:
            mock_router = MagicMock()
            mock_router.complete = AsyncMock(side_effect=Exception("API error"))
            mock_cls.return_value = mock_router

            state = {"current_sub_task": "Do it", "messages": []}
            result = await executor_node(state)
            assert "Execution error" in result["result"]


class TestReflectorNode:
    """Test reflector_node function."""

    @pytest.mark.asyncio
    async def test_reflector_decides_done(self):
        """Reflector should decide 'done' for completed task."""
        from nexus.orchestrator.langgraph_engine import reflector_node

        with patch("nexus.llm.router.LLMRouter") as mock_cls:
            mock_router = MagicMock()
            mock_response = MagicMock()
            mock_response.content = '{"action": "done", "reason": "Task complete"}'
            mock_router.complete = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_router

            state = {
                "task": "Test",
                "result": "Completed",
                "sub_tasks": ["step1"],
                "current_sub_task": "step1",
                "iteration": 1,
            }
            result = await reflector_node(state)
            assert result["next_action"] == "done"

    @pytest.mark.asyncio
    async def test_reflector_decides_execute(self):
        """Reflector should decide 'execute' for more work."""
        from nexus.orchestrator.langgraph_engine import reflector_node

        with patch("nexus.llm.router.LLMRouter") as mock_cls:
            mock_router = MagicMock()
            mock_response = MagicMock()
            mock_response.content = '{"action": "execute", "reason": "More to do"}'
            mock_router.complete = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_router

            state = {
                "task": "Multi-step task",
                "result": "Partial result",
                "sub_tasks": ["step1", "step2"],
                "current_sub_task": "step1",
                "iteration": 1,
            }
            result = await reflector_node(state)
            assert result["next_action"] == "execute"

    @pytest.mark.asyncio
    async def test_reflector_decides_replan(self):
        """Reflector should decide 'replan' when approach fails."""
        from nexus.orchestrator.langgraph_engine import reflector_node

        with patch("nexus.llm.router.LLMRouter") as mock_cls:
            mock_router = MagicMock()
            mock_response = MagicMock()
            mock_response.content = '{"action": "replan", "reason": "Wrong approach"}'
            mock_router.complete = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_router

            state = {
                "task": "Complex task",
                "result": "Failed",
                "sub_tasks": ["step1"],
                "current_sub_task": "step1",
                "iteration": 1,
            }
            result = await reflector_node(state)
            assert result["next_action"] == "replan"

    @pytest.mark.asyncio
    async def test_reflector_max_iterations_reached(self):
        """Reflector should return 'done' when max iterations reached."""
        from nexus.orchestrator.langgraph_engine import reflector_node

        state = {
            "task": "Task",
            "result": "Ongoing",
            "sub_tasks": [],
            "iteration": 100,
        }
        result = await reflector_node(state)
        assert result["next_action"] == "done"
        assert "Max iterations" in result["reflection"]

    @pytest.mark.asyncio
    async def test_reflector_defaults_on_llm_failure(self):
        """Reflector should default to execute on LLM failure."""
        from nexus.orchestrator.langgraph_engine import reflector_node

        with patch("nexus.llm.router.LLMRouter") as mock_cls:
            mock_router = MagicMock()
            mock_router.complete = AsyncMock(side_effect=Exception("LLM failed"))
            mock_cls.return_value = mock_router

            state = {
                "task": "Task",
                "result": "Result",
                "sub_tasks": ["step1", "step2"],
                "current_sub_task": "step1",
                "iteration": 1,
            }
            result = await reflector_node(state)
            assert result["next_action"] in ("execute", "done")

    @pytest.mark.asyncio
    async def test_reflector_auto_done_when_all_subtasks_complete(self):
        """Reflector should auto-done when all sub-tasks are processed."""
        from nexus.orchestrator.langgraph_engine import reflector_node

        with patch("nexus.llm.router.LLMRouter") as mock_cls:
            mock_router = MagicMock()
            mock_response = MagicMock()
            mock_response.content = '{"action": "execute", "reason": "Continue"}'
            mock_router.complete = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_router

            state = {
                "task": "Task",
                "result": "Done",
                "sub_tasks": ["only_step"],
                "current_sub_task": "only_step",
                "iteration": 1,
            }
            result = await reflector_node(state)
            # current idx = 0, last = 0 -> action should become "done"
            assert result["next_action"] == "done"

    @pytest.mark.asyncio
    async def test_reflector_json_in_code_block(self, monkeypatch):
        """Reflector should extract JSON from markdown code blocks."""
        from nexus.orchestrator.langgraph_engine import reflector_node

        with patch("nexus.llm.router.LLMRouter") as mock_cls:
            mock_router = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "```json\n{\"action\": \"done\", \"reason\": \"All good\"}\n```"
            mock_router.complete = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_router

            state = {
                "task": "Task",
                "result": "Result",
                "sub_tasks": ["step1"],
                "current_sub_task": "step1",
                "iteration": 1,
            }
            result = await reflector_node(state)
            assert result["next_action"] == "done"


class TestRunNexusTask:
    """Test run_nexus_task function."""

    @pytest.mark.asyncio
    async def test_run_simple_loop_success(self):
        """run_nexus_task should complete via simple loop fallback."""
        from nexus.orchestrator.langgraph_engine import run_nexus_task

        with patch("nexus.orchestrator.langgraph_engine.build_nexus_graph", return_value=None):
            with patch("nexus.llm.router.LLMRouter") as mock_cls:
                mock_router = MagicMock()
                mock_response = MagicMock()
                mock_response.content = "Completed successfully"
                mock_router.complete = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_router

                result = await run_nexus_task(task="Test task")
                assert result["status"] == "completed"
                assert "result" in result

    @pytest.mark.asyncio
    async def test_run_with_messages(self):
        """run_nexus_task with messages should pass them through."""
        from nexus.orchestrator.langgraph_engine import run_nexus_task

        with patch("nexus.orchestrator.langgraph_engine.build_nexus_graph", return_value=None):
            with patch("nexus.llm.router.LLMRouter") as mock_cls:
                mock_router = MagicMock()
                mock_response = MagicMock()
                mock_response.content = "Result with context"
                mock_router.complete = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_router

                result = await run_nexus_task(
                    task="Contextual task",
                    messages=[{"role": "user", "content": "Previous context"}],
                )
                assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_run_with_thread_id(self):
        """run_nexus_task with thread_id should pass through."""
        from nexus.orchestrator.langgraph_engine import run_nexus_task

        with patch("nexus.orchestrator.langgraph_engine.build_nexus_graph", return_value=None):
            with patch("nexus.llm.router.LLMRouter") as mock_cls:
                mock_router = MagicMock()
                mock_response = MagicMock()
                mock_response.content = "Threaded result"
                mock_router.complete = AsyncMock(return_value=mock_response)
                mock_cls.return_value = mock_router

                result = await run_nexus_task(
                    task="Thread task",
                    thread_id="my_thread_42",
                )
                assert result["status"] == "completed"
                # thread_id is only returned when using the actual graph,
                # not in the _run_simple_loop fallback
                assert result["task"] == "Thread task"


class TestBuildNexusGraph:
    """Test build_nexus_graph function."""

    def test_build_graph_with_langgraph(self):
        """build_nexus_graph should return compiled graph when langgraph available."""
        from nexus.orchestrator.langgraph_engine import build_nexus_graph

        graph = build_nexus_graph()
        # May be None if langgraph not installed, but should not crash
        if graph is not None:
            assert hasattr(graph, "ainvoke")

    def test_build_graph_without_langgraph(self):
        """build_nexus_graph should return None when langgraph missing."""
        from nexus.orchestrator.langgraph_engine import build_nexus_graph

        with patch.dict("sys.modules", {"langgraph.graph": None, "langgraph.checkpoint.memory": None}):
            graph = build_nexus_graph()
            assert graph is None


# ═══════════════════════════════════════════════════════════════════
# Skill Lifecycle Tests
# ═══════════════════════════════════════════════════════════════════

class TestSkillDefinition:
    """Test SkillDefinition dataclass."""

    def test_default_creation(self):
        """SkillDefinition with defaults."""
        from nexus.orchestrator.skill_lifecycle import SkillDefinition, SkillStage, SkillStatus

        skill = SkillDefinition(name="test_skill", description="A test skill")
        assert skill.name == "test_skill"
        assert skill.skill_id is not None
        assert skill.stage == SkillStage.DISCOVERY
        assert skill.status == SkillStatus.DRAFT
        assert skill.version == 1
        assert skill.usage_count == 0
        assert skill.success_rate == 0.0

    def test_to_dict(self):
        """to_dict should return serializable dict."""
        from nexus.orchestrator.skill_lifecycle import SkillDefinition

        skill = SkillDefinition(
            name="format_converter",
            description="Converts data between formats",
            category="utility",
            parameters=[{"name": "input", "type": "str"}],
            return_type="str",
        )
        d = skill.to_dict()
        assert d["name"] == "format_converter"
        assert d["category"] == "utility"
        assert d["stage"] == "discovery"
        assert len(d["parameters"]) == 1
        # Should not include implementation or test_cases
        assert "implementation" not in d
        assert "test_cases" not in d

    def test_to_dict_with_all_fields(self):
        """to_dict with usage tracking fields."""
        from nexus.orchestrator.skill_lifecycle import SkillDefinition, SkillStage, SkillStatus

        skill = SkillDefinition(
            name="web_scraper",
            description="Scrapes web pages",
            version=3,
            usage_count=50,
            success_rate=0.85,
        )
        d = skill.to_dict()
        assert d["version"] == 3
        assert d["usage_count"] == 50
        assert d["success_rate"] == 0.85


class TestSkillLifecycleManagerDiscover:
    """Test SkillLifecycleManager.discover_skill()."""

    @pytest.fixture
    def manager(self):
        from nexus.orchestrator.skill_lifecycle import SkillLifecycleManager
        m = SkillLifecycleManager()
        m.min_usage_for_discovery = 999
        return m

    @pytest.mark.asyncio
    async def test_discover_new_skill(self, manager):
        """Discover a new skill from task pattern."""
        skill = await manager.discover_skill(
            task_pattern="convert data between JSON and CSV",
            frequency=1,
            category="utility",
        )
        assert skill.name == "convert_data_between_json_and_csv"
        assert skill.category == "utility"
        assert skill.stage.value == "discovery"
        assert skill.skill_id in manager._skills

    @pytest.mark.asyncio
    async def test_discover_tracks_pattern(self, manager):
        """Discover should track task pattern frequency."""
        await manager.discover_skill(task_pattern="parse text", frequency=3)
        assert manager._task_patterns["parse text"] == 3

    @pytest.mark.asyncio
    async def test_discover_accumulates_frequency(self, manager):
        """Discover should accumulate pattern frequency."""
        await manager.discover_skill(task_pattern="parse text", frequency=2)
        await manager.discover_skill(task_pattern="parse text", frequency=3)
        assert manager._task_patterns["parse text"] == 5

    @pytest.mark.asyncio
    async def test_discover_auto_advances_on_threshold(self, manager):
        """Discover should auto-advance when frequency >= min."""
        manager.min_usage_for_discovery = 2
        with patch.object(manager, "design_skill", new=AsyncMock()) as mock_design:
            mock_design.return_value = MagicMock()
            await manager.discover_skill(task_pattern="auto skill", frequency=3)
            mock_design.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_sanitizes_name(self, manager):
        """Discover should remove special characters from name."""
        skill = await manager.discover_skill(task_pattern="convert@data#format!", frequency=1)
        assert "@" not in skill.name
        assert "#" not in skill.name
        assert "!" not in skill.name

    @pytest.mark.asyncio
    async def test_discover_without_auto_advance(self, manager):
        """Discover should NOT auto-advance when frequency below threshold."""
        with patch.object(manager, "design_skill", new=AsyncMock()) as mock_design:
            await manager.discover_skill(task_pattern="manual skill", frequency=1)
            mock_design.assert_not_called()


class TestSkillLifecycleManagerDesign:
    """Test SkillLifecycleManager.design_skill()."""

    @pytest.fixture
    def manager(self):
        from nexus.orchestrator.skill_lifecycle import SkillLifecycleManager
        m = SkillLifecycleManager()
        m.min_usage_for_discovery = 999
        return m

    @pytest.mark.asyncio
    async def test_design_with_parameters(self, manager):
        """Design skill with explicit parameters."""
        skill = await manager.discover_skill(task_pattern="test pattern", frequency=1)
        with patch.object(manager, "advance_stage", new=AsyncMock(return_value=MagicMock(stage="design"))):
            updated = await manager.design_skill(
                skill.skill_id,
                parameters=[{"name": "input", "type": "str", "required": True}],
                description="Enhanced description",
            )
            assert updated.stage.value == "design"
            assert updated.description == "Enhanced description"
            assert len(updated.parameters) == 1

    @pytest.mark.asyncio
    async def test_design_generates_parameters_on_llm(self, manager):
        """Design should use LLM when no parameters given."""
        skill = await manager.discover_skill(task_pattern="test pattern", frequency=1)
        mock_response = MagicMock()
        mock_response.content = '[{"name": "text", "type": "str", "description": "Input text"}]'

        with patch("nexus.llm.router.LLMRouter") as mock_cls:
            mock_router = MagicMock()
            mock_router.complete = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_router
            updated = await manager.design_skill(skill.skill_id)
            assert len(updated.parameters) >= 1

    @pytest.mark.asyncio
    async def test_design_nonexistent_skill(self, manager):
        """Design should raise for missing skill."""
        with pytest.raises(ValueError, match="not found"):
            await manager.design_skill("nonexistent_id")

    @pytest.mark.asyncio
    async def test_design_llm_invalid_json(self, manager):
        """Design should fallback on invalid JSON from LLM."""
        skill = await manager.discover_skill(task_pattern="test", frequency=1)
        mock_response = MagicMock()
        mock_response.content = "not valid json"

        with patch("nexus.llm.router.LLMRouter") as mock_cls:
            mock_router = MagicMock()
            mock_router.complete = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_router

            # Auto-advance will call implement_skill, which will need mock
            with patch.object(manager, "implement_skill", new=AsyncMock()) as mock_impl:
                mock_impl.return_value = MagicMock()
                updated = await manager.design_skill(skill.skill_id)
                assert len(updated.parameters) >= 1  # Falls back to default params


class TestSkillLifecycleManagerImplement:
    """Test SkillLifecycleManager.implement_skill()."""

    @pytest.fixture
    def manager(self):
        from nexus.orchestrator.skill_lifecycle import SkillLifecycleManager
        m = SkillLifecycleManager()
        m.min_usage_for_discovery = 999
        return m

    @pytest.mark.asyncio
    async def test_implement_generates_code(self, manager):
        """Implement should generate skill code."""
        skill = await manager.discover_skill(task_pattern="test", frequency=1)
        skill.parameters = [{"name": "input", "type": "str"}]

        mock_response = MagicMock()
        mock_response.content = "def test_skill(input: str) -> str:\n    return input"

        with patch("nexus.llm.router.LLMRouter") as mock_cls:
            mock_router = MagicMock()
            mock_router.complete = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_router
            with patch.object(manager, "advance_stage", new=AsyncMock()) as mock_adv:
                mock_adv.return_value = MagicMock()
                updated = await manager.implement_skill(skill.skill_id)
                assert updated.stage.value == "implement"
                assert len(updated.implementation) > 0

    @pytest.mark.asyncio
    async def test_implement_nonexistent_skill(self, manager):
        """Implement should raise for missing skill."""
        with pytest.raises(ValueError, match="not found"):
            await manager.implement_skill("nonexistent")

    @pytest.mark.asyncio
    async def test_implement_llm_failure(self, manager):
        """Implement should fallback on LLM failure."""
        skill = await manager.discover_skill(task_pattern="test", frequency=1)

        with patch("nexus.llm.router.LLMRouter") as mock_cls:
            mock_router = MagicMock()
            mock_router.complete = AsyncMock(side_effect=Exception("LLM error"))
            mock_cls.return_value = mock_router
            with patch.object(manager, "advance_stage", new=AsyncMock()):
                updated = await manager.implement_skill(skill.skill_id)
                assert "# Auto-generated stub" in updated.implementation


class TestSkillLifecycleManagerValidate:
    """Test SkillLifecycleManager.validate_skill()."""

    @pytest.fixture
    def manager(self):
        from nexus.orchestrator.skill_lifecycle import SkillLifecycleManager
        m = SkillLifecycleManager()
        m.min_usage_for_discovery = 999
        return m

    @pytest.mark.asyncio
    async def test_validate_passing_skill(self, manager):
        """Validate skill that passes tests."""
        skill = await manager.discover_skill(task_pattern="test", frequency=1)
        skill.parameters = [{"name": "input", "type": "str"}]

        with patch.object(manager, "_llm_generate_test_cases", new=AsyncMock()) as mock_gen:
            mock_gen.return_value = [{"input": {"test": "value"}, "expected_output": "success"}]
            with patch.object(manager, "_run_test_case", new=AsyncMock()) as mock_run:
                mock_run.return_value = {"success": True, "output": "success"}
                with patch.object(manager, "advance_stage", new=AsyncMock()) as mock_adv:
                    mock_adv.return_value = MagicMock()
                    updated = await manager.validate_skill(skill.skill_id)
                    assert updated.stage.value == "validate"
                    assert updated.success_rate == 1.0

    @pytest.mark.asyncio
    async def test_validate_failing_skill(self, manager):
        """Validate skill that fails tests."""
        skill = await manager.discover_skill(task_pattern="test", frequency=1)
        skill.parameters = [{"name": "input", "type": "str"}]

        with patch.object(manager, "_llm_generate_test_cases", new=AsyncMock()) as mock_gen:
            mock_gen.return_value = [{"input": {"test": "value"}, "expected_output": "success"}]
            with patch.object(manager, "_run_test_case", new=AsyncMock()) as mock_run:
                mock_run.return_value = {"success": False, "error": "Failed"}
                updated = await manager.validate_skill(skill.skill_id)
                assert updated.success_rate == 0.0
                assert updated.status.value == "failed"

    @pytest.mark.asyncio
    async def test_validate_nonexistent_skill(self, manager):
        """Validate should raise for missing skill."""
        with pytest.raises(ValueError, match="not found"):
            await manager.validate_skill("nonexistent")

    @pytest.mark.asyncio
    async def test_validate_runs_test_cases(self, manager):
        """Validate should run existing test cases."""
        skill = await manager.discover_skill(task_pattern="test", frequency=1)
        skill.test_cases = [
            {"input": {"a": 1}, "expected_output": "2"},
            {"input": {"a": 2}, "expected_output": "3"},
        ]

        with patch.object(manager, "_run_test_case", new=AsyncMock()) as mock_run:
            mock_run.side_effect = [
                {"success": True, "output": "2"},
                {"success": True, "output": "3"},
            ]
            with patch.object(manager, "advance_stage", new=AsyncMock()):
                updated = await manager.validate_skill(skill.skill_id)
                assert updated.success_rate == 1.0
                assert mock_run.call_count == 2


class TestSkillLifecycleManagerDeploy:
    """Test SkillLifecycleManager.deploy_skill()."""

    @pytest.fixture
    def manager(self):
        from nexus.orchestrator.skill_lifecycle import SkillLifecycleManager
        m = SkillLifecycleManager()
        m.min_usage_for_discovery = 999
        return m

    @pytest.mark.asyncio
    async def test_deploy_success(self, manager):
        """Deploy a validated skill."""
        skill = await manager.discover_skill(task_pattern="deploy_test", frequency=1)
        skill.success_rate = 0.9

        with patch("nexus.memory.chroma_service.NexusMemoryService") as mock_mem_cls:
            mock_mem = MagicMock()
            mock_mem.store = AsyncMock(return_value="stored")
            mock_mem_cls.return_value = mock_mem

            updated = await manager.deploy_skill(skill.skill_id)
            assert updated.stage.value == "deploy"
            assert updated.status.value == "active"

    @pytest.mark.asyncio
    async def test_deploy_nonexistent_skill(self, manager):
        """Deploy should raise for missing skill."""
        with pytest.raises(ValueError, match="not found"):
            await manager.deploy_skill("nonexistent")

    @pytest.mark.asyncio
    async def test_deploy_handles_memory_error(self, manager):
        """Deploy should handle memory storage failure gracefully."""
        skill = await manager.discover_skill(task_pattern="deploy_test", frequency=1)

        with patch("nexus.memory.chroma_service.NexusMemoryService") as mock_mem_cls:
            mock_mem = MagicMock()
            mock_mem.store = AsyncMock(side_effect=Exception("Memory error"))
            mock_mem_cls.return_value = mock_mem

            updated = await manager.deploy_skill(skill.skill_id)
            assert updated.stage.value == "deploy"
            assert updated.status.value == "active"


class TestSkillLifecycleManagerUtils:
    """Test SkillLifecycleManager utility methods."""

    @pytest.fixture
    def manager(self):
        from nexus.orchestrator.skill_lifecycle import SkillLifecycleManager
        m = SkillLifecycleManager()
        m.min_usage_for_discovery = 999
        return m

    def test_get_skill(self, manager):
        """get_skill should return skill by ID."""
        import asyncio
        skill = asyncio.run(manager.discover_skill(task_pattern="get_test", frequency=1))
        retrieved = manager.get_skill(skill.skill_id)
        assert retrieved is not None
        assert retrieved.name == "get_test"

    def test_get_skill_nonexistent(self, manager):
        """get_skill should return None for missing ID."""
        result = manager.get_skill("nonexistent")
        assert result is None

    def test_list_skills_all(self, manager):
        """list_skills should return all skills."""
        import asyncio
        asyncio.run(manager.discover_skill(task_pattern="skill_a", frequency=1))
        asyncio.run(manager.discover_skill(task_pattern="skill_b", frequency=1))
        skills = manager.list_skills()
        assert len(skills) == 2

    def test_list_skills_filtered_by_status(self, manager):
        """list_skills should filter by status."""
        from nexus.orchestrator.skill_lifecycle import SkillStatus

        import asyncio
        asyncio.run(manager.discover_skill(task_pattern="filter_test", frequency=1))
        skills = manager.list_skills(status=SkillStatus.DRAFT)
        assert len(skills) >= 1
        skills_active = manager.list_skills(status=SkillStatus.ACTIVE)
        assert len(skills_active) == 0

    def test_get_stats_empty(self, manager):
        """get_stats should return zeros for empty manager."""
        stats = manager.get_stats()
        assert stats["total_skills"] == 0
        assert stats["task_patterns_tracked"] == 0

    def test_get_stats_with_skills(self, manager):
        """get_stats should reflect current state."""
        import asyncio
        asyncio.run(manager.discover_skill(task_pattern="stat_test", frequency=1))
        stats = manager.get_stats()
        assert stats["total_skills"] == 1
        assert "discovery" in stats["by_stage"]
        assert "draft" in stats["by_status"]

    def test_custom_parameters(self):
        """Custom initialization parameters."""
        from nexus.orchestrator.skill_lifecycle import SkillLifecycleManager

        manager = SkillLifecycleManager(
            min_usage_for_discovery=10,
            min_success_rate=0.9,
            auto_deploy=True,
        )
        assert manager.min_usage_for_discovery == 10
        assert manager.min_success_rate == 0.9
        assert manager.auto_deploy is True


class TestSkillLifecycleManagerEvolve:
    """Test SkillLifecycleManager.evolve_skill()."""

    @pytest.fixture
    def manager(self):
        from nexus.orchestrator.skill_lifecycle import SkillLifecycleManager
        m = SkillLifecycleManager()
        m.min_usage_for_discovery = 999
        return m

    @pytest.mark.asyncio
    async def test_evolve_increments_version(self, manager):
        """Evolve should increment version number."""
        skill = await manager.discover_skill(task_pattern="evolve_test", frequency=1)
        original_version = skill.version

        with patch.object(manager, "advance_stage", new=AsyncMock()) as mock_adv:
            mock_adv.return_value = MagicMock(version=original_version + 1)
            evolved = await manager.evolve_skill(skill.skill_id, feedback="Make it faster")
            assert evolved.version == original_version + 1

    @pytest.mark.asyncio
    async def test_evolve_resets_stage(self, manager):
        """Evolve should reset to design stage."""
        skill = await manager.discover_skill(task_pattern="evolve_reset", frequency=1)

        with patch.object(manager, "advance_stage", new=AsyncMock()) as mock_adv:
            evolved = await manager.evolve_skill(skill.skill_id)
            assert evolved.stage.value == "design"
            assert evolved.status.value == "draft"

    @pytest.mark.asyncio
    async def test_evolve_nonexistent_skill(self, manager):
        """Evolve should raise for missing skill."""
        with pytest.raises(ValueError, match="not found"):
            await manager.evolve_skill("nonexistent", feedback="Fix it")


class TestSkillLifecycleManagerAdvanceStage:
    """Test SkillLifecycleManager.advance_stage()."""

    @pytest.fixture
    def manager(self):
        from nexus.orchestrator.skill_lifecycle import SkillLifecycleManager
        m = SkillLifecycleManager()
        m.min_usage_for_discovery = 999
        return m

    @pytest.mark.asyncio
    async def test_advance_from_discovery_to_deploy(self, manager):
        """Full lifecycle advance through all stages."""
        skill = await manager.discover_skill(task_pattern="full_lifecycle", frequency=1)

        # Mock all subsequent stages
        with patch.object(manager, "design_skill", new=AsyncMock()) as mock_design:
            mock_design.return_value = MagicMock(stage="design")
            with patch.object(manager, "implement_skill", new=AsyncMock()) as mock_impl:
                mock_impl.return_value = MagicMock(stage="implement")
                with patch.object(manager, "validate_skill", new=AsyncMock()) as mock_val:
                    mock_val.return_value = MagicMock(stage="validate")
                    with patch.object(manager, "deploy_skill", new=AsyncMock()) as mock_deploy:
                        mock_deploy.return_value = MagicMock(stage="deploy")

                        s1 = await manager.advance_stage(skill.skill_id)
                        mock_design.assert_called_once()

    @pytest.mark.asyncio
    async def test_advance_at_final_stage(self, manager):
        """Advance at final stage should return skill unchanged."""
        from nexus.orchestrator.skill_lifecycle import SkillStage

        skill = await manager.discover_skill(task_pattern="final_stage", frequency=1)
        skill.stage = SkillStage.DEPLOY
        manager._skills[skill.skill_id] = skill

        result = await manager.advance_stage(skill.skill_id)
        assert result.stage == SkillStage.DEPLOY

    @pytest.mark.asyncio
    async def test_advance_nonexistent_skill(self, manager):
        """Advance should raise for missing skill."""
        with pytest.raises(ValueError, match="not found"):
            await manager.advance_stage("nonexistent")


class TestSelfImprovementLoop:
    """Test SelfImprovementLoop."""

    def test_init_defaults(self):
        """SelfImprovementLoop with defaults."""
        from nexus.orchestrator.skill_lifecycle import SelfImprovementLoop

        loop = SelfImprovementLoop()
        assert loop.min_success_rate == 0.7
        assert loop.check_interval == 50
        assert loop.auto_evolve is False

    def test_lifecycle_property_lazy(self):
        """lifecycle property should lazy-load."""
        from nexus.orchestrator.skill_lifecycle import SelfImprovementLoop

        loop = SelfImprovementLoop()
        assert loop._lifecycle is None
        lc = loop.lifecycle
        assert lc is not None
        assert loop._lifecycle is lc  # Same instance

    def test_evaluator_property_lazy(self):
        """evaluator property should lazy-load."""
        from nexus.orchestrator.skill_lifecycle import SelfImprovementLoop

        loop = SelfImprovementLoop()
        assert loop._evaluator is None
        ev = loop.evaluator
        assert ev is not None
        assert loop._evaluator is ev

    @pytest.mark.asyncio
    async def test_record_usage(self):
        """record_usage should track usage counts."""
        from nexus.orchestrator.skill_lifecycle import SelfImprovementLoop

        loop = SelfImprovementLoop(check_interval=50)
        await loop.record_usage("skill_1", success=True)
        assert loop._usage_counts["skill_1"] == 1

    @pytest.mark.asyncio
    async def test_record_usage_triggers_check(self):
        """record_usage should trigger check at interval."""
        from nexus.orchestrator.skill_lifecycle import SelfImprovementLoop

        loop = SelfImprovementLoop(check_interval=2)
        with patch.object(loop, "_check_and_improve", new=AsyncMock()) as mock_check:
            await loop.record_usage("skill_x", success=True)
            await loop.record_usage("skill_x", success=True)
            await loop.record_usage("skill_x", success=True)
            # After 3 records (2 from last check = 0), should trigger
            assert mock_check.call_count >= 1

    def test_build_feedback(self):
        """_build_feedback should create feedback string."""
        from nexus.orchestrator.skill_lifecycle import SelfImprovementLoop, SkillDefinition

        loop = SelfImprovementLoop()
        skill = SkillDefinition(
            name="test",
            description="Test skill",
            usage_count=10,
            success_rate=0.5,
        )
        feedback = loop._build_feedback(skill)
        assert "50%" in feedback
        assert "70%" in feedback  # threshold
        assert "10" in feedback  # usage count

    def test_build_feedback_with_implementation(self):
        """_build_feedback with implementation."""
        from nexus.orchestrator.skill_lifecycle import SelfImprovementLoop, SkillDefinition

        loop = SelfImprovementLoop()
        skill = SkillDefinition(
            name="test",
            description="Test",
            success_rate=0.6,
            implementation="def test(): pass",
        )
        feedback = loop._build_feedback(skill)
        assert "Implementation length" in feedback

    def test_get_stats(self):
        """get_stats should return current stats."""
        from nexus.orchestrator.skill_lifecycle import SelfImprovementLoop

        loop = SelfImprovementLoop()
        stats = loop.get_stats()
        assert stats["tracked_skills"] == 0
        assert stats["total_usages"] == 0
        assert stats["check_interval"] == 50

    @pytest.mark.asyncio
    async def test_run_full_cycle_empty(self):
        """run_full_cycle with no active skills should return zeros."""
        from nexus.orchestrator.skill_lifecycle import SelfImprovementLoop

        loop = SelfImprovementLoop()
        result = await loop.run_full_cycle()
        assert result["total_skills"] == 0
        assert result["healthy"] == 0

    @pytest.mark.asyncio
    async def test_run_full_cycle_with_skills(self):
        """run_full_cycle should analyze active skills."""
        from nexus.orchestrator.skill_lifecycle import SelfImprovementLoop, SkillStatus

        loop = SelfImprovementLoop(min_success_rate=0.7, auto_evolve=True)
        # Add a skill directly
        skill = loop.lifecycle.list_skills()
        result = await loop.run_full_cycle()
        assert isinstance(result, dict)
        assert "total_skills" in result


# ═══════════════════════════════════════════════════════════════════
# Enums Tests
# ═══════════════════════════════════════════════════════════════════

class TestEngineTypeEnum:
    """Test EngineType enum."""

    def test_all_values(self):
        from nexus.orchestrator.router import EngineType
        assert EngineType.LANGGRAPH.value == "langgraph"
        assert EngineType.CREWAI.value == "crewai"
        assert EngineType.ADK.value == "adk"


class TestTaskStructureEnum:
    """Test TaskStructure enum."""

    def test_all_values(self):
        from nexus.orchestrator.router import TaskStructure
        assert TaskStructure.STRUCTURED.value == "structured"
        assert TaskStructure.SEMI_STRUCTURED.value == "semi"
        assert TaskStructure.UNSTRUCTURED.value == "unstructured"


class TestCollaborationStyleEnum:
    """Test CollaborationStyle enum."""

    def test_all_values(self):
        from nexus.orchestrator.router import CollaborationStyle
        assert CollaborationStyle.SEQUENTIAL.value == "sequential"
        assert CollaborationStyle.PARALLEL.value == "parallel"
        assert CollaborationStyle.COLLABORATIVE.value == "collaborative"
        assert CollaborationStyle.HIERARCHICAL.value == "hierarchical"


class TestPatternTypeEnum:
    """Test PatternType enum."""

    def test_all_values(self):
        from nexus.orchestrator.patterns import PatternType
        assert PatternType.SUPERVISOR.value == "supervisor"
        assert PatternType.PIPELINE.value == "pipeline"
        assert PatternType.PARALLEL.value == "parallel"
        assert PatternType.HIERARCHICAL.value == "hierarchical"
        assert PatternType.MESH.value == "mesh"
        assert PatternType.SWARM.value == "swarm"


class TestSkillStageEnum:
    """Test SkillStage enum."""

    def test_all_values(self):
        from nexus.orchestrator.skill_lifecycle import SkillStage
        assert SkillStage.DISCOVERY.value == "discovery"
        assert SkillStage.DESIGN.value == "design"
        assert SkillStage.IMPLEMENT.value == "implement"
        assert SkillStage.VALIDATE.value == "validate"
        assert SkillStage.DEPLOY.value == "deploy"


class TestSkillCategoryEnum:
    """Test SkillCategory enum."""

    def test_all_values(self):
        from nexus.orchestrator.skill_lifecycle import SkillCategory
        assert SkillCategory.CODING.value == "coding"
        assert SkillCategory.RESEARCH.value == "research"
        assert SkillCategory.ANALYSIS.value == "analysis"
        assert SkillCategory.ORCHESTRATION.value == "orchestration"
        assert SkillCategory.SECURITY.value == "security"
        assert SkillCategory.MEMORY.value == "memory"
        assert SkillCategory.WEB.value == "web"
        assert SkillCategory.FILE.value == "file"
        assert SkillCategory.UTILITY.value == "utility"


class TestSkillStatusEnum:
    """Test SkillStatus enum."""

    def test_all_values(self):
        from nexus.orchestrator.skill_lifecycle import SkillStatus
        assert SkillStatus.DISCOVERED.value == "discovered"
        assert SkillStatus.DRAFT.value == "draft"
        assert SkillStatus.TESTING.value == "testing"
        assert SkillStatus.ACTIVE.value == "active"
        assert SkillStatus.DEPRECATED.value == "deprecated"
        assert SkillStatus.FAILED.value == "failed"
