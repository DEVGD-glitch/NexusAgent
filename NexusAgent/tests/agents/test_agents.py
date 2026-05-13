"""
NEXUS Agent Tests — Comprehensive tests for all agent implementations.

Tests: BaseAgent, ResearcherAgent, DeveloperAgent, AnalystAgent, OperatorAgent,
       AgentContext, AgentResult, and integration with registry.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from nexus.agents.base import BaseAgent, AgentContext, AgentResult, AgentPhase
from nexus.agents.researcher import ResearcherAgent
from nexus.agents.developer import DeveloperAgent
from nexus.agents.analyst import AnalystAgent
from nexus.agents.operator import OperatorAgent
from nexus.agents import AGENT_TYPE_MAP
from nexus.core.registry import AgentRegistry, AgentCapability, AgentStatus


# ═══════════════════════════════════════════════════════════════
# AgentContext Tests
# ═══════════════════════════════════════════════════════════════

class TestAgentContext:
    """Tests for AgentContext data management."""

    def test_context_creation(self):
        """Should create context with task."""
        ctx = AgentContext(task="Test task")
        assert ctx.task == "Test task"
        assert ctx.agent_id is not None
        assert len(ctx.conversation) == 0

    def test_add_message(self):
        """Should add messages to conversation."""
        ctx = AgentContext(task="Test")
        ctx.add_message("user", "Hello")
        ctx.add_message("assistant", "Hi there")
        assert len(ctx.conversation) == 2
        assert ctx.conversation[0]["role"] == "user"
        assert ctx.conversation[1]["content"] == "Hi there"

    def test_store_and_get_artifact(self):
        """Should store and retrieve artifacts."""
        ctx = AgentContext(task="Test")
        ctx.store_artifact("data", {"key": "value"})
        result = ctx.get_artifact("data")
        assert result == {"key": "value"}

    def test_get_artifact_default(self):
        """Should return default for missing artifacts."""
        ctx = AgentContext(task="Test")
        result = ctx.get_artifact("missing", default="fallback")
        assert result == "fallback"

    def test_max_iterations(self):
        """Should respect max iterations setting."""
        ctx = AgentContext(task="Test", max_iterations=5)
        assert ctx.max_iterations == 5


# ═══════════════════════════════════════════════════════════════
# AgentResult Tests
# ═══════════════════════════════════════════════════════════════

class TestAgentResult:
    """Tests for AgentResult."""

    def test_success_property(self):
        """Should indicate success when completed."""
        result = AgentResult(
            agent_id="test",
            agent_type="researcher",
            status=AgentStatus.COMPLETED,
            answer="Done",
        )
        assert result.success is True

    def test_failure_property(self):
        """Should indicate failure when failed."""
        result = AgentResult(
            agent_id="test",
            agent_type="researcher",
            status=AgentStatus.FAILED,
            error="Something went wrong",
        )
        assert result.success is False

    def test_default_values(self):
        """Should have sensible defaults."""
        result = AgentResult(
            agent_id="test",
            agent_type="researcher",
            status=AgentStatus.IDLE,
        )
        assert result.answer == ""
        assert result.artifacts == {}
        assert result.steps_taken == 0
        assert result.tools_used == []
        assert result.error is None


# ═══════════════════════════════════════════════════════════════
# Concrete Agent Tests
# ═══════════════════════════════════════════════════════════════

class TestResearcherAgent:
    """Tests for ResearcherAgent."""

    def test_researcher_init(self):
        """Should initialize with correct properties."""
        agent = ResearcherAgent()
        assert agent.agent_type == "researcher"
        assert "web_search" in agent.skills
        assert AgentCapability.RESEARCH in agent.capabilities

    def test_researcher_system_prompt(self):
        """Should have a detailed system prompt."""
        agent = ResearcherAgent()
        assert "Researcher" in agent.system_prompt
        assert "search" in agent.system_prompt.lower()

    def test_researcher_get_info(self):
        """Should return agent info."""
        agent = ResearcherAgent()
        info = agent.get_info()
        assert info["agent_type"] == "researcher"
        assert "research" in info["capabilities"]

    @pytest.mark.asyncio
    async def test_researcher_plan(self):
        """Should create a research plan."""
        agent = ResearcherAgent()
        ctx = AgentContext(task="What is quantum computing?")
        plan = await agent.plan(ctx)
        assert len(plan) > 0
        actions = [step["action"] for step in plan]
        assert "web_search" in actions or "deep_research" in actions

    @pytest.mark.asyncio
    async def test_researcher_reflect_done(self):
        """Should stop when synthesis is complete."""
        agent = ResearcherAgent()
        ctx = AgentContext(task="Test")
        ctx.store_artifact("synthesis", "Final answer")
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is False


class TestDeveloperAgent:
    """Tests for DeveloperAgent."""

    def test_developer_init(self):
        """Should initialize with correct properties."""
        agent = DeveloperAgent()
        assert agent.agent_type == "developer"
        assert "code_generation" in agent.skills
        assert AgentCapability.CODING in agent.capabilities

    def test_developer_system_prompt(self):
        """Should have a development-focused system prompt."""
        agent = DeveloperAgent()
        assert "Developer" in agent.system_prompt
        assert "code" in agent.system_prompt.lower()

    @pytest.mark.asyncio
    async def test_developer_plan_coding(self):
        """Should create a coding plan for normal tasks."""
        agent = DeveloperAgent()
        ctx = AgentContext(task="Write a Python function to sort a list")
        plan = await agent.plan(ctx)
        assert len(plan) > 0
        actions = [step["action"] for step in plan]
        assert "implement_code" in actions

    @pytest.mark.asyncio
    async def test_developer_plan_debugging(self):
        """Should create a debugging plan for fix tasks."""
        agent = DeveloperAgent()
        ctx = AgentContext(task="Debug this error: TypeError in my code")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "analyze_error" in actions
        assert "implement_fix" in actions

    @pytest.mark.asyncio
    async def test_developer_plan_review(self):
        """Should create a review plan for code review tasks."""
        agent = DeveloperAgent()
        ctx = AgentContext(task="Review this code for security issues")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "analyze_quality" in actions

    @pytest.mark.asyncio
    async def test_developer_reflect_review_done(self):
        """Should stop when review is complete."""
        agent = DeveloperAgent()
        ctx = AgentContext(task="Review code")
        ctx.store_artifact("review", "Code looks good")
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is False


class TestAnalystAgent:
    """Tests for AnalystAgent."""

    def test_analyst_init(self):
        """Should initialize with correct properties."""
        agent = AnalystAgent()
        assert agent.agent_type == "analyst"
        assert "data_analysis" in agent.skills
        assert AgentCapability.ANALYSIS in agent.capabilities

    def test_analyst_system_prompt(self):
        """Should have an analysis-focused system prompt."""
        agent = AnalystAgent()
        assert "Analyst" in agent.system_prompt
        assert "analy" in agent.system_prompt.lower()

    @pytest.mark.asyncio
    async def test_analyst_plan(self):
        """Should create an analysis plan."""
        agent = AnalystAgent()
        ctx = AgentContext(task="Analyze the sales data from Q4")
        plan = await agent.plan(ctx)
        assert len(plan) > 0
        actions = [step["action"] for step in plan]
        assert "define_question" in actions
        assert "create_report" in actions

    @pytest.mark.asyncio
    async def test_analyst_reflect_done(self):
        """Should stop when report is complete."""
        agent = AnalystAgent()
        ctx = AgentContext(task="Analyze data")
        ctx.store_artifact("report", "Final report")
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is False


class TestOperatorAgent:
    """Tests for OperatorAgent."""

    def test_operator_init(self):
        """Should initialize with correct properties."""
        agent = OperatorAgent()
        assert agent.agent_type == "operator"
        assert "system_admin" in agent.skills
        assert AgentCapability.OPERATION in agent.capabilities

    def test_operator_system_prompt(self):
        """Should have an operations-focused system prompt."""
        agent = OperatorAgent()
        assert "Operator" in agent.system_prompt
        assert "operation" in agent.system_prompt.lower()

    @pytest.mark.asyncio
    async def test_operator_plan_deployment(self):
        """Should create a deployment plan for deploy tasks."""
        agent = OperatorAgent()
        ctx = AgentContext(task="Deploy the new version to production")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "pre_deployment_check" in actions
        assert "execute_deployment" in actions

    @pytest.mark.asyncio
    async def test_operator_plan_monitoring(self):
        """Should create a monitoring plan for health check tasks."""
        agent = OperatorAgent()
        ctx = AgentContext(task="Check the health of all services")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "check_system_health" in actions

    @pytest.mark.asyncio
    async def test_operator_plan_incident(self):
        """Should create an incident plan for incident tasks."""
        agent = OperatorAgent()
        ctx = AgentContext(task="Alert: service X is down")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "triage_incident" in actions
        assert "diagnose_root_cause" in actions

    @pytest.mark.asyncio
    async def test_operator_plan_automation(self):
        """Should create an automation plan for automation tasks."""
        agent = OperatorAgent()
        ctx = AgentContext(task="Automate the daily backup process")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "analyze_automation_target" in actions
        assert "implement_automation" in actions

    @pytest.mark.asyncio
    async def test_operator_reflect_done(self):
        """Should stop when report is complete."""
        agent = OperatorAgent()
        ctx = AgentContext(task="Deploy v2")
        ctx.store_artifact("report", "Deployment complete")
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is False


# ═══════════════════════════════════════════════════════════════
# Agent Type Map Tests
# ═══════════════════════════════════════════════════════════════

class TestAgentTypeMap:
    """Tests for the agent type mapping."""

    def test_type_map_has_all_agents(self):
        """Should map all agent types."""
        assert "researcher" in AGENT_TYPE_MAP
        assert "developer" in AGENT_TYPE_MAP
        assert "analyst" in AGENT_TYPE_MAP
        assert "operator" in AGENT_TYPE_MAP

    def test_type_map_classes(self):
        """Should map to correct classes."""
        assert AGENT_TYPE_MAP["researcher"] is ResearcherAgent
        assert AGENT_TYPE_MAP["developer"] is DeveloperAgent
        assert AGENT_TYPE_MAP["analyst"] is AnalystAgent
        assert AGENT_TYPE_MAP["operator"] is OperatorAgent


# ═══════════════════════════════════════════════════════════════
# Agent Integration with Registry Tests
# ═══════════════════════════════════════════════════════════════

class TestAgentRegistryIntegration:
    """Tests for agent-registry integration."""

    def test_register_agents_with_registry(self):
        """Should register all agent types with the registry."""
        registry = AgentRegistry()
        for type_name, agent_cls in AGENT_TYPE_MAP.items():
            agent = agent_cls()
            registry.register_type(
                type_name,
                capabilities=agent.capabilities,
                description=agent.description,
                skills=agent.skills,
            )

        types = registry.list_types()
        type_names = [t["name"] for t in types]
        assert "researcher" in type_names
        assert "developer" in type_names
        assert "analyst" in type_names
        assert "operator" in type_names

    def test_find_agents_by_capability(self):
        """Should find agents by their capabilities."""
        registry = AgentRegistry()
        for type_name, agent_cls in AGENT_TYPE_MAP.items():
            agent = agent_cls()
            registry.register_type(
                type_name,
                capabilities=agent.capabilities,
                description=agent.description,
            )

        researchers = registry.find_by_capability(AgentCapability.RESEARCH)
        assert "researcher" in researchers

        coders = registry.find_by_capability(AgentCapability.CODING)
        assert "developer" in coders

        analysts = registry.find_by_capability(AgentCapability.ANALYSIS)
        assert "analyst" in analysts

    def test_spawn_and_track_agent(self):
        """Should spawn and track agent instances."""
        registry = AgentRegistry()
        registry.register_type(
            "researcher",
            capabilities=[AgentCapability.RESEARCH],
        )
        instance = registry.spawn("researcher", task="Research AI trends")
        assert instance.status == AgentStatus.IDLE
        assert instance.task == "Research AI trends"

        # Update status
        registry.update_status(instance.instance_id, AgentStatus.RUNNING)
        updated = registry.get_instance(instance.instance_id)
        assert updated.status == AgentStatus.RUNNING


# ═══════════════════════════════════════════════════════════════
# BaseAgent Lifecycle Tests (with mocked LLM)
# ═══════════════════════════════════════════════════════════════

class TestBaseAgentLifecycle:
    """Tests for the base agent lifecycle with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_researcher_run_with_mock_llm(self):
        """Researcher should complete lifecycle with mocked LLM."""
        agent = ResearcherAgent()

        with patch.object(agent, '_call_llm', new_callable=AsyncMock, return_value="Analysis done"):
            with patch.object(agent, '_use_tool', new_callable=AsyncMock, return_value={"results": []}):
                with patch.object(agent, '_log_action', new_callable=AsyncMock):
                    ctx = AgentContext(task="What is AI?")
                    plan = await agent.plan(ctx)
                    assert len(plan) > 0

    @pytest.mark.asyncio
    async def test_developer_execute_step(self):
        """Developer should execute individual steps."""
        agent = DeveloperAgent()

        with patch.object(agent, '_call_llm', new_callable=AsyncMock, return_value="Code result"):
            with patch.object(agent, '_log_action', new_callable=AsyncMock):
                ctx = AgentContext(task="Write a function")
                ctx.store_artifact("requirements", "Need a sort function")
                ctx.store_artifact("design", "Use quicksort algorithm")

                step = {"action": "implement_code", "params": {}}
                result = await agent.execute_step(step, ctx)
                assert result["action"] == "implement_code"

    @pytest.mark.asyncio
    async def test_analyst_execute_step(self):
        """Analyst should execute individual steps."""
        agent = AnalystAgent()

        with patch.object(agent, '_call_llm', new_callable=AsyncMock, return_value="Analysis result"):
            with patch.object(agent, '_log_action', new_callable=AsyncMock):
                ctx = AgentContext(task="Analyze data")
                step = {"action": "define_question", "params": {"task": "Analyze data"}}
                result = await agent.execute_step(step, ctx)
                assert result["action"] == "define_question"

    @pytest.mark.asyncio
    async def test_operator_execute_step(self):
        """Operator should execute individual steps."""
        agent = OperatorAgent()

        with patch.object(agent, '_call_llm', new_callable=AsyncMock, return_value="Ops result"):
            with patch.object(agent, '_log_action', new_callable=AsyncMock):
                ctx = AgentContext(task="Deploy service")
                step = {"action": "assess_request", "params": {"task": "Deploy service"}}
                result = await agent.execute_step(step, ctx)
                assert result["action"] == "assess_request"
