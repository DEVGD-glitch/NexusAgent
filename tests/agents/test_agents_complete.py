"""
Comprehensive tests for agent subclasses — AnalystAgent, DeveloperAgent,
ResearcherAgent, OperatorAgent.

Covers all uncovered code paths:
  - __init__() with correct type, description, skills, capabilities
  - get_info() returning expected dict
  - plan() with all task type branches
  - execute_step() for each step handler and generic fallback
  - reflect() returning correct done/continue decisions
  - system_prompt returning domain-specific content
  - Error handling for step execution
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from nexus.agents.base import AgentContext, AgentCapability
from nexus.agents.analyst import AnalystAgent
from nexus.agents.developer import DeveloperAgent
from nexus.agents.researcher import ResearcherAgent
from nexus.agents.operator import OperatorAgent
from nexus.core.registry import AgentCapability as Cap


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def ctx():
    """Basic AgentContext with a simple task."""
    return AgentContext(task="Test task")


@pytest.fixture
def mock_call_llm():
    """Patches _call_llm on an agent instance to return LLM text."""
    def _make(return_value="Mocked LLM response"):
        return patch(
            "nexus.agents.base.BaseAgent._call_llm",
            new_callable=AsyncMock,
            return_value=return_value,
        )
    return _make


@pytest.fixture
def mock_use_tool():
    """Patches _use_tool on an agent instance."""
    def _make(return_value=None):
        if return_value is None:
            return_value = {"result": "tool executed"}
        return patch(
            "nexus.agents.base.BaseAgent._use_tool",
            new_callable=AsyncMock,
            return_value=return_value,
        )
    return _make


@pytest.fixture
def mock_log_action():
    """Patches _log_action on an agent instance."""
    return patch(
        "nexus.agents.base.BaseAgent._log_action",
        new_callable=AsyncMock,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ResearcherAgent Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestResearcherAgentInit:
    """Tests for ResearcherAgent.__init__."""

    def test_agent_type_and_description(self):
        agent = ResearcherAgent()
        assert agent.agent_type == "researcher"
        assert agent.description == "Research agent for information gathering and synthesis"

    def test_skills(self):
        agent = ResearcherAgent()
        assert "web_search" in agent.skills
        assert "document_analysis" in agent.skills
        assert "fact_checking" in agent.skills
        assert "deep_research" in agent.skills
        assert "knowledge_graph_query" in agent.skills
        assert "rag_pipeline" in agent.skills
        assert "source_verification" in agent.skills
        assert "citation_tracking" in agent.skills

    def test_capabilities(self):
        agent = ResearcherAgent()
        assert Cap.RESEARCH in agent.capabilities
        assert Cap.BROWSING in agent.capabilities
        assert Cap.REASONING in agent.capabilities

    def test_default_research_depth(self):
        agent = ResearcherAgent()
        assert agent._research_depth == "standard"

    def test_system_prompt(self):
        agent = ResearcherAgent()
        prompt = agent.system_prompt
        assert "Researcher" in prompt
        assert "web_search" in prompt
        assert "deep_research" in prompt
        assert "rag_pipeline" in prompt

    def test_get_info(self):
        agent = ResearcherAgent()
        info = agent.get_info()
        assert info["agent_type"] == "researcher"
        assert "research" in info["capabilities"]
        assert "browsing" in info["capabilities"]
        assert "reasoning" in info["capabilities"]
        assert info["phase"] == "initializing"


class TestResearcherAgentPlan:
    """Tests for ResearcherAgent.plan()."""

    @pytest.mark.asyncio
    async def test_plan_with_decomposition(self, mock_call_llm):
        agent = ResearcherAgent()
        ctx = AgentContext(task="What is quantum computing?")
        with mock_call_llm(return_value="Decomposition result"):
            plan = await agent.plan(ctx)
        assert len(plan) > 0
        actions = [step["action"] for step in plan]
        assert "analyze_question" in actions
        assert "web_search" in actions
        assert "deep_research" in actions
        assert "cross_reference" in actions
        assert "synthesize" in actions
        assert "decomposition" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_plan_decomposition_failure_fallback(self):
        agent = ResearcherAgent()
        ctx = AgentContext(task="Quick research on Python")
        with patch.object(agent, "_call_llm", new_callable=AsyncMock, side_effect=Exception("LLM down")):
            plan = await agent.plan(ctx)
        assert len(plan) > 0
        # Should fall back and still produce a plan
        assert ctx.artifacts.get("decomposition") is None

    @pytest.mark.asyncio
    async def test_plan_detects_deep_depth(self):
        agent = ResearcherAgent()
        ctx = AgentContext(task="Provide a comprehensive analysis of AI trends")
        with patch.object(agent, "_call_llm", new_callable=AsyncMock, return_value="Decomposition"):
            plan = await agent.plan(ctx)
        assert agent._research_depth == "deep"

    @pytest.mark.asyncio
    async def test_plan_detects_quick_depth(self):
        agent = ResearcherAgent()
        ctx = AgentContext(task="Give me a quick brief on Python")
        with patch.object(agent, "_call_llm", new_callable=AsyncMock, return_value="Decomposition"):
            plan = await agent.plan(ctx)
        assert agent._research_depth == "quick"

    @pytest.mark.asyncio
    async def test_plan_default_standard_depth(self):
        agent = ResearcherAgent()
        ctx = AgentContext(task="What is the capital of France?")
        with patch.object(agent, "_call_llm", new_callable=AsyncMock, return_value="Decomposition"):
            plan = await agent.plan(ctx)
        assert agent._research_depth == "standard"


class TestResearcherAgentExecuteStep:
    """Tests for ResearcherAgent.execute_step()."""

    @pytest.mark.asyncio
    async def test_analyze_question(self, mock_call_llm):
        agent = ResearcherAgent()
        ctx = AgentContext(task="Analyze AI trends")
        step = {"action": "analyze_question", "params": {"task": "Analyze AI trends"}}
        with mock_call_llm(return_value="Question analysis result"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "analyze_question"
        assert "question_analysis" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_web_search(self, mock_use_tool):
        agent = ResearcherAgent()
        ctx = AgentContext(task="Search for Python")
        step = {"action": "web_search", "params": {"query": "Python", "num_results": 5}}
        with mock_use_tool(return_value={"results": ["result1"]}):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "web_search"

    @pytest.mark.asyncio
    async def test_deep_research(self, mock_use_tool):
        agent = ResearcherAgent()
        ctx = AgentContext(task="Deep research on ML")
        step = {"action": "deep_research", "params": {"query": "ML", "iterations": 2}}
        with mock_use_tool(return_value={"result": "research done"}):
            with patch("nexus.knowledge.deep_research.DeepResearch") as mock_dr:
                mock_dr_instance = MagicMock()
                mock_dr_instance.investigate = AsyncMock(return_value={"summary": "deep result"})
                mock_dr.return_value = mock_dr_instance
                result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "deep_research"

    @pytest.mark.asyncio
    async def test_deep_research_fallback_on_error(self, mock_use_tool):
        agent = ResearcherAgent()
        ctx = AgentContext(task="Deep research on X")
        step = {"action": "deep_research", "params": {"query": "X", "iterations": 2}}
        with mock_use_tool(return_value={"results": "web result"}):
            with patch("nexus.knowledge.deep_research.DeepResearch") as mock_dr:
                mock_dr_instance = MagicMock()
                mock_dr_instance.investigate = AsyncMock(side_effect=ImportError("No module"))
                mock_dr.return_value = mock_dr_instance
                result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "deep_research"

    @pytest.mark.asyncio
    async def test_cross_reference(self, mock_call_llm):
        agent = ResearcherAgent()
        ctx = AgentContext(task="Cross ref data")
        ctx.store_artifact("search_results", "search data")
        ctx.store_artifact("deep_research", "deep data")
        step = {"action": "cross_reference", "params": {}}
        with mock_call_llm(return_value="Cross reference analysis"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "cross_reference"
        assert "cross_reference" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_synthesize(self, mock_call_llm):
        agent = ResearcherAgent()
        ctx = AgentContext(task="Synthesize findings")
        ctx.store_artifact("search_results", "search")
        ctx.store_artifact("deep_research", "deep")
        ctx.store_artifact("cross_reference", "xref")
        ctx.store_artifact("question_analysis", "analysis")
        step = {"action": "synthesize", "params": {}}
        with mock_call_llm(return_value="Synthesis result"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "synthesize"
        assert "synthesis" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_generic_step(self, mock_call_llm):
        agent = ResearcherAgent()
        ctx = AgentContext(task="Generic research")
        step = {"action": "unknown_action", "params": {}}
        with mock_call_llm(return_value="Generic result"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "unknown_action"

    @pytest.mark.asyncio
    async def test_execute_step_error(self):
        agent = ResearcherAgent()
        ctx = AgentContext(task="Test")
        step = {"action": "analyze_question", "params": {}}
        # Force an error by making _call_llm raise
        with patch.object(agent, "_call_llm", new_callable=AsyncMock, side_effect=ValueError("Bad call")):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is False
        assert "error" in result
        assert result["action"] == "analyze_question"


class TestResearcherAgentReflect:
    """Tests for ResearcherAgent.reflect()."""

    @pytest.mark.asyncio
    async def test_synthesis_done(self):
        agent = ResearcherAgent()
        ctx = AgentContext(task="Research")
        ctx.store_artifact("synthesis", "Final answer")
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is False
        assert "complete" in reflection["assessment"]

    @pytest.mark.asyncio
    async def test_cross_reference_complete(self):
        agent = ResearcherAgent()
        ctx = AgentContext(task="Research")
        ctx.store_artifact("cross_reference", "Xref done")
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is True
        assert reflection["adjustments"]["next_action"] == "synthesize"

    @pytest.mark.asyncio
    async def test_need_more_data(self):
        agent = ResearcherAgent()
        ctx = AgentContext(task="Research")
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is True
        assert "Need more" in reflection["assessment"]

    @pytest.mark.asyncio
    async def test_sufficient_data(self):
        agent = ResearcherAgent()
        ctx = AgentContext(task="Research")
        ctx.store_artifact("search_results", "data1")
        ctx.store_artifact("deep_research", "data2")
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is True
        assert "cross-reference" in reflection["assessment"].lower()


# ═══════════════════════════════════════════════════════════════════════════════
# AnalystAgent Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnalystAgentInit:
    """Tests for AnalystAgent.__init__."""

    def test_agent_type_and_description(self):
        agent = AnalystAgent()
        assert agent.agent_type == "analyst"
        assert agent.description == "Data analysis agent for insights and reporting"

    def test_skills(self):
        agent = AnalystAgent()
        assert "data_analysis" in agent.skills
        assert "visualization" in agent.skills
        assert "reporting" in agent.skills
        assert "statistical_analysis" in agent.skills
        assert "trend_forecasting" in agent.skills
        assert "comparative_analysis" in agent.skills
        assert "benchmarking" in agent.skills

    def test_capabilities(self):
        agent = AnalystAgent()
        assert Cap.ANALYSIS in agent.capabilities
        assert Cap.REASONING in agent.capabilities

    def test_system_prompt(self):
        agent = AnalystAgent()
        prompt = agent.system_prompt
        assert "Analyst" in prompt
        assert "data" in prompt.lower()
        assert "analysis" in prompt.lower()

    def test_get_info(self):
        agent = AnalystAgent()
        info = agent.get_info()
        assert info["agent_type"] == "analyst"
        assert "analysis" in info["capabilities"]


class TestAnalystAgentPlan:
    """Tests for AnalystAgent.plan()."""

    @pytest.mark.asyncio
    async def test_plan_standard_analysis(self):
        agent = AnalystAgent()
        ctx = AgentContext(task="Analyze the quarterly revenue data")
        plan = await agent.plan(ctx)
        assert len(plan) > 0
        actions = [step["action"] for step in plan]
        assert "define_question" in actions
        assert "gather_data" in actions
        assert "perform_analysis" in actions
        assert "generate_insights" in actions
        assert "create_report" in actions
        # Should NOT have comparative_analysis
        assert "comparative_analysis" not in actions

    @pytest.mark.asyncio
    async def test_plan_comparative_analysis(self):
        agent = AnalystAgent()
        ctx = AgentContext(task="Compare product A vs product B")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "comparative_analysis" in actions

    @pytest.mark.asyncio
    async def test_plan_comparative_with_benchmark(self):
        agent = AnalystAgent()
        ctx = AgentContext(task="Benchmark our performance against competitors")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "comparative_analysis" in actions

    @pytest.mark.asyncio
    async def test_plan_with_versus_keyword(self):
        agent = AnalystAgent()
        ctx = AgentContext(task="Analyze iOS versus Android market share")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "comparative_analysis" in actions

    @pytest.mark.asyncio
    async def test_plan_with_contrast_keyword(self):
        agent = AnalystAgent()
        ctx = AgentContext(task="Contrast the two marketing strategies")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "comparative_analysis" in actions


class TestAnalystAgentExecuteStep:
    """Tests for AnalystAgent.execute_step()."""

    @pytest.mark.asyncio
    async def test_define_question(self, mock_call_llm):
        agent = AnalystAgent()
        ctx = AgentContext(task="Analyze Q4 sales")
        step = {"action": "define_question", "params": {"task": "Analyze Q4 sales"}}
        with mock_call_llm(return_value="Analytical brief"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "define_question"
        assert "analytical_brief" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_gather_data(self, mock_call_llm, mock_use_tool):
        agent = AnalystAgent()
        ctx = AgentContext(task="Analyze sales")
        ctx.store_artifact("analytical_brief", "Brief data")
        step = {"action": "gather_data", "params": {}}
        with mock_call_llm(return_value="Data inventory"):
            with mock_use_tool(return_value={"results": "search results"}):
                result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "gather_data"
        assert "data_inventory" in ctx.artifacts
        assert "external_data" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_perform_analysis(self, mock_call_llm, mock_use_tool):
        agent = AnalystAgent()
        ctx = AgentContext(task="Analyze data")
        ctx.store_artifact("analytical_brief", "Brief")
        ctx.store_artifact("data_inventory", "Data")
        step = {"action": "perform_analysis", "params": {}}
        with mock_call_llm(return_value="import pandas as pd"):
            with mock_use_tool(return_value={"output": "analysis complete"}):
                result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "perform_analysis"
        assert "analysis_code" in ctx.artifacts
        assert "analysis_result" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_comparative_analysis(self, mock_call_llm):
        agent = AnalystAgent()
        ctx = AgentContext(task="Compare A and B")
        ctx.store_artifact("analytical_brief", "Comparison brief")
        step = {"action": "comparative_analysis", "params": {}}
        with mock_call_llm(return_value="Comparison results"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "comparative_analysis"
        assert "comparative_analysis" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_generate_insights(self, mock_call_llm):
        agent = AnalystAgent()
        ctx = AgentContext(task="Get insights")
        ctx.store_artifact("analysis_result", {"output": "numbers"})
        ctx.store_artifact("comparative_analysis", "Comparisons")
        step = {"action": "generate_insights", "params": {}}
        with mock_call_llm(return_value="Key insights"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "generate_insights"
        assert "insights" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_create_report(self, mock_call_llm):
        agent = AnalystAgent()
        ctx = AgentContext(task="Create report")
        ctx.store_artifact("analytical_brief", "Brief")
        ctx.store_artifact("insights", "Insights")
        ctx.store_artifact("analysis_result", "Results")
        step = {"action": "create_report", "params": {}}
        with mock_call_llm(return_value="Final report"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "create_report"
        assert "report" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_generic_analysis_step(self, mock_call_llm):
        agent = AnalystAgent()
        ctx = AgentContext(task="Generic analysis")
        step = {"action": "unknown_analysis_action", "params": {"custom": True}}
        with mock_call_llm(return_value="Generic result"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "unknown_analysis_action"

    @pytest.mark.asyncio
    async def test_execute_step_error(self):
        agent = AnalystAgent()
        ctx = AgentContext(task="Test")
        step = {"action": "define_question", "params": {"task": "Test"}}
        with patch.object(agent, "_call_llm", new_callable=AsyncMock, side_effect=RuntimeError("LLM error")):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is False
        assert "error" in result


class TestAnalystAgentReflect:
    """Tests for AnalystAgent.reflect()."""

    @pytest.mark.asyncio
    async def test_report_done(self):
        agent = AnalystAgent()
        ctx = AgentContext(task="Analysis")
        ctx.store_artifact("report", "Final report")
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is False
        assert "complete" in reflection["assessment"]

    @pytest.mark.asyncio
    async def test_insights_ready(self):
        agent = AnalystAgent()
        ctx = AgentContext(task="Analysis")
        ctx.store_artifact("insights", "Key insights")
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is True
        assert "Ready to create report" in reflection["assessment"]

    @pytest.mark.asyncio
    async def test_analysis_in_progress(self):
        agent = AnalystAgent()
        ctx = AgentContext(task="Analysis")
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is True
        assert "in progress" in reflection["assessment"].lower()


# ═══════════════════════════════════════════════════════════════════════════════
# DeveloperAgent Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeveloperAgentInit:
    """Tests for DeveloperAgent.__init__."""

    def test_agent_type_and_description(self):
        agent = DeveloperAgent()
        assert agent.agent_type == "developer"
        assert agent.description == "Software development agent for writing and debugging code"

    def test_skills(self):
        agent = DeveloperAgent()
        assert "code_generation" in agent.skills
        assert "debugging" in agent.skills
        assert "code_review" in agent.skills
        assert "testing" in agent.skills
        assert "refactoring" in agent.skills
        assert "documentation" in agent.skills
        assert "git_integration" in agent.skills

    def test_capabilities(self):
        agent = DeveloperAgent()
        assert Cap.CODING in agent.capabilities
        assert Cap.FILE_OPS in agent.capabilities
        assert Cap.REASONING in agent.capabilities

    def test_system_prompt(self):
        agent = DeveloperAgent()
        prompt = agent.system_prompt
        assert "Developer" in prompt
        assert "production-quality" in prompt
        assert "SOLID" in prompt

    def test_get_info(self):
        agent = DeveloperAgent()
        info = agent.get_info()
        assert info["agent_type"] == "developer"
        assert "coding" in info["capabilities"]


class TestDeveloperAgentPlan:
    """Tests for DeveloperAgent.plan()."""

    @pytest.mark.asyncio
    async def test_plan_coding_task(self):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Write a Python CLI calculator")
        plan = await agent.plan(ctx)
        assert len(plan) > 0
        actions = [step["action"] for step in plan]
        assert "analyze_requirements" in actions
        assert "design_solution" in actions
        assert "implement_code" in actions
        assert "execute_and_test" in actions
        assert "review_and_refine" in actions

    @pytest.mark.asyncio
    async def test_plan_debugging_task(self):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Debug the crash in the login module")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "analyze_error" in actions
        assert "locate_issue" in actions
        assert "implement_fix" in actions
        assert "verify_fix" in actions

    @pytest.mark.asyncio
    async def test_plan_debugging_fix_keyword(self):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Fix the null pointer exception")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "analyze_error" in actions

    @pytest.mark.asyncio
    async def test_plan_debugging_broken_keyword(self):
        agent = DeveloperAgent()
        ctx = AgentContext(task="The API endpoint is broken")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "analyze_error" in actions

    @pytest.mark.asyncio
    async def test_plan_review_task(self):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Review the authentication module code")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "read_code" in actions
        assert "analyze_quality" in actions
        assert "provide_feedback" in actions

    @pytest.mark.asyncio
    async def test_plan_audit_task(self):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Audit the codebase for security issues")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "read_code" in actions

    @pytest.mark.asyncio
    async def test_plan_improve_task(self):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Improve the performance of the data pipeline")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "read_code" in actions


class TestDeveloperAgentExecuteStep:
    """Tests for DeveloperAgent.execute_step()."""

    @pytest.mark.asyncio
    async def test_analyze_requirements(self, mock_call_llm, mock_log_action):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Build auth system")
        step = {"action": "analyze_requirements", "params": {"task": "Build auth system"}}
        with mock_call_llm(return_value="Requirements analysis"):
            with mock_log_action:
                result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "analyze_requirements"
        assert "requirements" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_design_solution(self, mock_call_llm, mock_log_action):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Design a system")
        ctx.store_artifact("requirements", "Need a scalable API")
        step = {"action": "design_solution", "params": {}}
        with mock_call_llm(return_value="Design document"):
            with mock_log_action:
                result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "design_solution"
        assert "design" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_implement_code(self, mock_call_llm, mock_log_action):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Write code")
        ctx.store_artifact("design", "Use Flask")
        ctx.store_artifact("requirements", "REST API")
        step = {"action": "implement_code", "params": {}}
        with mock_call_llm(return_value="def hello(): pass"):
            with mock_log_action:
                result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "implement_code"
        assert "code" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_execute_and_test(self, mock_use_tool, mock_log_action):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Test code")
        ctx.store_artifact("code", "print('hello')")
        step = {"action": "execute_and_test", "params": {}}
        with mock_use_tool(return_value={"output": "hello", "exit_code": 0}):
            with mock_log_action:
                result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "execute_and_test"
        assert "execution_result" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_execute_and_test_no_code(self, mock_log_action):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Test code")
        step = {"action": "execute_and_test", "params": {}}
        with mock_log_action:
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["result"]["error"] == "No code to execute"

    @pytest.mark.asyncio
    async def test_review_and_refine(self, mock_call_llm):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Review code")
        ctx.store_artifact("code", "print('hello')")
        ctx.store_artifact("execution_result", {"output": "hello"})
        step = {"action": "review_and_refine", "params": {}}
        with mock_call_llm(return_value="Code looks good"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "review_and_refine"
        assert "review" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_analyze_error(self, mock_call_llm):
        agent = DeveloperAgent()
        ctx = AgentContext(task="App crashes on startup")
        step = {"action": "analyze_error", "params": {"task": "App crashes on startup"}}
        with mock_call_llm(return_value="Error analysis"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "analyze_error"
        assert "error_analysis" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_locate_issue(self, mock_call_llm):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Find bug")
        ctx.store_artifact("error_analysis", "Null pointer in login()")
        step = {"action": "locate_issue", "params": {}}
        with mock_call_llm(return_value="Issue located in auth.py:42"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "locate_issue"
        assert "issue_location" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_implement_fix(self, mock_call_llm):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Fix bug")
        ctx.store_artifact("error_analysis", "Null pointer")
        ctx.store_artifact("issue_location", "auth.py:42")
        step = {"action": "implement_fix", "params": {}}
        with mock_call_llm(return_value="def fixed_func(): pass"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "implement_fix"
        assert "fix" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_verify_fix(self, mock_use_tool):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Verify fix")
        ctx.store_artifact("fix", "print('fixed')")
        step = {"action": "verify_fix", "params": {}}
        with mock_use_tool(return_value={"output": "fixed", "exit_code": 0}):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "verify_fix"
        assert "fix_verification" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_read_code_with_file_path(self, mock_use_tool):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Review /home/user/code/app.py for bugs")
        step = {"action": "read_code", "params": {}}
        with mock_use_tool(return_value={"content": "print('hello')"}):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "read_code"
        assert "code_under_review" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_read_code_without_file_path(self):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Review the code in the description")
        step = {"action": "read_code", "params": {}}
        result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "read_code"
        assert "code_under_review" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_analyze_quality(self, mock_call_llm):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Analyze quality")
        ctx.store_artifact("code_under_review", "def foo(): pass")
        step = {"action": "analyze_quality", "params": {}}
        with mock_call_llm(return_value="Quality review results"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "analyze_quality"
        assert "quality_review" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_provide_feedback(self, mock_call_llm):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Provide feedback")
        ctx.store_artifact("quality_review", "Review notes")
        step = {"action": "provide_feedback", "params": {}}
        with mock_call_llm(return_value="Actionable feedback"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "provide_feedback"
        assert "feedback" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_generic_dev_step(self, mock_call_llm):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Generic dev")
        step = {"action": "unknown_dev_action", "params": {}}
        with mock_call_llm(return_value="Generic result"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "unknown_dev_action"

    @pytest.mark.asyncio
    async def test_execute_step_error(self):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Test")
        step = {"action": "analyze_requirements", "params": {"task": "Test"}}
        with patch.object(agent, "_call_llm", new_callable=AsyncMock, side_effect=ValueError("fail")):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is False
        assert "error" in result


class TestDeveloperAgentReflect:
    """Tests for DeveloperAgent.reflect()."""

    @pytest.mark.asyncio
    async def test_review_done(self):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Dev")
        ctx.store_artifact("review", "Code looks good")
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is False

    @pytest.mark.asyncio
    async def test_feedback_done(self):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Dev")
        ctx.store_artifact("feedback", "Feedback provided")
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is False

    @pytest.mark.asyncio
    async def test_fix_verified_successfully(self):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Dev")
        ctx.store_artifact("fix_verification", {"output": "all good", "exit_code": 0})
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is False
        assert "verified" in reflection["assessment"].lower()

    @pytest.mark.asyncio
    async def test_fix_verified_with_errors(self):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Dev")
        ctx.store_artifact("fix_verification", {"error": "still broken"})
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is True

    @pytest.mark.asyncio
    async def test_execution_success_needs_review(self):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Dev")
        ctx.store_artifact("execution_result", {"output": "success"})
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is True
        assert "Moving to review" in reflection["assessment"]

    @pytest.mark.asyncio
    async def test_execution_with_error(self):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Dev")
        ctx.store_artifact("execution_result", {"error": "syntax error"})
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is True

    @pytest.mark.asyncio
    async def test_default_continue(self):
        agent = DeveloperAgent()
        ctx = AgentContext(task="Dev")
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is True
        assert "Continuing" in reflection["assessment"]


# ═══════════════════════════════════════════════════════════════════════════════
# OperatorAgent Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestOperatorAgentInit:
    """Tests for OperatorAgent.__init__."""

    def test_agent_type_and_description(self):
        agent = OperatorAgent()
        assert agent.agent_type == "operator"
        assert agent.description == "Operations agent for system management and automation"

    def test_skills(self):
        agent = OperatorAgent()
        assert "system_admin" in agent.skills
        assert "deployment" in agent.skills
        assert "monitoring" in agent.skills
        assert "automation" in agent.skills
        assert "security_operations" in agent.skills
        assert "backup_restore" in agent.skills
        assert "troubleshooting" in agent.skills
        assert "compliance" in agent.skills

    def test_capabilities(self):
        agent = OperatorAgent()
        assert Cap.OPERATION in agent.capabilities
        assert Cap.FILE_OPS in agent.capabilities
        assert Cap.BROWSING in agent.capabilities

    def test_system_prompt(self):
        agent = OperatorAgent()
        prompt = agent.system_prompt
        assert "Operator" in prompt
        assert "least-privilege" in prompt

    def test_get_info(self):
        agent = OperatorAgent()
        info = agent.get_info()
        assert info["agent_type"] == "operator"
        assert "operation" in info["capabilities"]


class TestOperatorAgentPlan:
    """Tests for OperatorAgent.plan()."""

    @pytest.mark.asyncio
    async def test_plan_deployment(self):
        agent = OperatorAgent()
        ctx = AgentContext(task="Deploy version 2.0 to production")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "pre_deployment_check" in actions
        assert "create_backup" in actions
        assert "execute_deployment" in actions
        assert "verify_deployment" in actions
        assert "post_deployment_report" in actions

    @pytest.mark.asyncio
    async def test_plan_release(self):
        agent = OperatorAgent()
        ctx = AgentContext(task="Release the hotfix to staging")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "pre_deployment_check" in actions

    @pytest.mark.asyncio
    async def test_plan_rollout(self):
        agent = OperatorAgent()
        ctx = AgentContext(task="Rollout the new feature gradually")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "pre_deployment_check" in actions

    @pytest.mark.asyncio
    async def test_plan_monitoring(self):
        agent = OperatorAgent()
        ctx = AgentContext(task="Monitor the database cluster health")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "assess_monitoring_scope" in actions
        assert "check_system_health" in actions
        assert "analyze_metrics" in actions
        assert "generate_health_report" in actions

    @pytest.mark.asyncio
    async def test_plan_monitoring_status(self):
        agent = OperatorAgent()
        ctx = AgentContext(task="Check the status of all microservices")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "assess_monitoring_scope" in actions

    @pytest.mark.asyncio
    async def test_plan_automation(self):
        agent = OperatorAgent()
        ctx = AgentContext(task="Automate the database backup process")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "analyze_automation_target" in actions
        assert "design_automation" in actions
        assert "implement_automation" in actions
        assert "test_automation" in actions
        assert "deploy_automation" in actions

    @pytest.mark.asyncio
    async def test_plan_automation_schedule(self):
        agent = OperatorAgent()
        ctx = AgentContext(task="Schedule nightly report generation")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "analyze_automation_target" in actions

    @pytest.mark.asyncio
    async def test_plan_automation_cron(self):
        agent = OperatorAgent()
        ctx = AgentContext(task="Set up a cron job for log rotation")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "analyze_automation_target" in actions

    @pytest.mark.asyncio
    async def test_plan_incident(self):
        agent = OperatorAgent()
        ctx = AgentContext(task="Incident: database is down")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "triage_incident" in actions
        assert "diagnose_root_cause" in actions
        assert "implement_mitigation" in actions
        assert "verify_resolution" in actions
        assert "post_incident_report" in actions

    @pytest.mark.asyncio
    async def test_plan_incident_alert(self):
        agent = OperatorAgent()
        ctx = AgentContext(task="Alert: high error rate detected")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "triage_incident" in actions

    @pytest.mark.asyncio
    async def test_plan_incident_failure(self):
        agent = OperatorAgent()
        ctx = AgentContext(task="Service failure in payment gateway")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "triage_incident" in actions

    @pytest.mark.asyncio
    async def test_plan_general_ops(self):
        agent = OperatorAgent()
        ctx = AgentContext(task="Set up a new development environment")
        plan = await agent.plan(ctx)
        actions = [step["action"] for step in plan]
        assert "assess_request" in actions
        assert "plan_execution" in actions
        assert "execute_operations" in actions
        assert "verify_results" in actions
        assert "document_operations" in actions


class TestOperatorAgentExecuteStep:
    """Tests for OperatorAgent.execute_step()."""

    @pytest.mark.asyncio
    async def test_assess_request(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Assess monitoring setup")
        step = {"action": "assess_request", "params": {"task": "Assess monitoring setup"}}
        with mock_call_llm(return_value="Assessment result"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "assess_request"
        assert "assessment" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_pre_deployment_check(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Deploy v3")
        step = {"action": "pre_deployment_check", "params": {"task": "Deploy v3"}}
        with mock_call_llm(return_value="Checklist complete"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "pre_deployment_check"
        assert "pre_deploy_checklist" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_create_backup(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Backup before deploy")
        step = {"action": "create_backup", "params": {}}
        with mock_call_llm(return_value="Backup script"):
            with patch.object(agent, "_log_action", new_callable=AsyncMock):
                result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "create_backup"
        assert "backup_plan" in ctx.artifacts
        assert result["result"]["mode"] == "advisory"

    @pytest.mark.asyncio
    async def test_execute_deployment(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Deploy app")
        ctx.store_artifact("pre_deploy_checklist", "All checks passed")
        step = {"action": "execute_deployment", "params": {}}
        with mock_call_llm(return_value="Deployment script"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "execute_deployment"
        assert "deploy_script" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_verify_deployment(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Verify deploy")
        ctx.store_artifact("deploy_script", "Deploy script")
        step = {"action": "verify_deployment", "params": {}}
        with mock_call_llm(return_value="Verification steps"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "verify_deployment"
        assert "verification" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_post_deployment_report(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Post deploy")
        ctx.store_artifact("pre_deploy_checklist", "check")
        step = {"action": "post_deployment_report", "params": {}}
        with mock_call_llm(return_value="Deployment report"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "post_deployment_report"
        assert "report" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_plan_execution(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Plan execution")
        ctx.store_artifact("assessment", "Assessment result")
        step = {"action": "plan_execution", "params": {}}
        with mock_call_llm(return_value="Execution plan"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "plan_execution"
        assert "execution_plan" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_execute_operations(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Execute ops")
        ctx.store_artifact("execution_plan", "Plan steps")
        step = {"action": "execute_operations", "params": {}}
        with mock_call_llm(return_value="Ops script"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "execute_operations"
        assert "ops_script" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_verify_results(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Verify ops")
        step = {"action": "verify_results", "params": {}}
        with mock_call_llm(return_value="Verification result"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "verify_results"
        assert "ops_verification" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_document_operations(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Document ops")
        step = {"action": "document_operations", "params": {}}
        with mock_call_llm(return_value="Documentation"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "document_operations"
        assert "report" in ctx.artifacts

    # Monitoring steps
    @pytest.mark.asyncio
    async def test_assess_monitoring_scope(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Monitor system")
        step = {"action": "assess_monitoring_scope", "params": {"task": "Monitor system"}}
        with mock_call_llm(return_value="Monitoring scope"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "assess_monitoring_scope"

    @pytest.mark.asyncio
    async def test_check_system_health(self, mock_call_llm, mock_use_tool):
        agent = OperatorAgent()
        ctx = AgentContext(task="Check health")
        step = {"action": "check_system_health", "params": {}}
        with mock_call_llm(return_value="Health script"):
            with mock_use_tool(return_value={"output": "All healthy"}):
                result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "check_system_health"
        assert "health_script" in ctx.artifacts
        assert "health_result" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_analyze_metrics(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Analyze metrics")
        ctx.store_artifact("health_result", {"cpu": 80, "mem": 60})
        step = {"action": "analyze_metrics", "params": {}}
        with mock_call_llm(return_value="Metrics analysis"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "analyze_metrics"
        assert "metrics_analysis" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_generate_health_report(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Health report")
        ctx.store_artifact("metrics_analysis", "Analysis")
        ctx.store_artifact("health_result", {"cpu": 80})
        step = {"action": "generate_health_report", "params": {}}
        with mock_call_llm(return_value="Health report"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "generate_health_report"
        assert "report" in ctx.artifacts

    # Incident steps
    @pytest.mark.asyncio
    async def test_triage_incident(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Incident: DB down")
        step = {"action": "triage_incident", "params": {"task": "Incident: DB down"}}
        with mock_call_llm(return_value="Triage result"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "triage_incident"
        assert "triage" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_diagnose_root_cause(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Diagnose incident")
        ctx.store_artifact("triage", "Triage data")
        step = {"action": "diagnose_root_cause", "params": {}}
        with mock_call_llm(return_value="Root cause analysis"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "diagnose_root_cause"
        assert "diagnosis" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_implement_mitigation(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Mitigate incident")
        ctx.store_artifact("diagnosis", "Root cause found")
        step = {"action": "implement_mitigation", "params": {}}
        with mock_call_llm(return_value="Mitigation steps"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "implement_mitigation"
        assert "mitigation" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_verify_resolution(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Verify resolution")
        ctx.store_artifact("mitigation", "Applied fix")
        step = {"action": "verify_resolution", "params": {}}
        with mock_call_llm(return_value="Verified resolved"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "verify_resolution"
        assert "resolution_verification" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_post_incident_report(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Post-incident")
        ctx.store_artifact("triage", "Triage")
        ctx.store_artifact("diagnosis", "Diagnosis")
        ctx.store_artifact("mitigation", "Mitigation")
        step = {"action": "post_incident_report", "params": {}}
        with mock_call_llm(return_value="Incident report"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "post_incident_report"
        assert "report" in ctx.artifacts

    # Automation steps
    @pytest.mark.asyncio
    async def test_analyze_automation_target(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Analyze automation for backups")
        step = {"action": "analyze_automation_target", "params": {"task": "Analyze automation for backups"}}
        with mock_call_llm(return_value="Automation analysis"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "analyze_automation_target"
        assert "automation_analysis" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_design_automation(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Design automation")
        ctx.store_artifact("automation_analysis", "Analysis")
        step = {"action": "design_automation", "params": {}}
        with mock_call_llm(return_value="Automation design"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "design_automation"
        assert "automation_design" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_implement_automation(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Implement automation")
        ctx.store_artifact("automation_design", "Design doc")
        step = {"action": "implement_automation", "params": {}}
        with mock_call_llm(return_value="import os"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "implement_automation"
        assert "automation_code" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_test_automation(self, mock_use_tool):
        agent = OperatorAgent()
        ctx = AgentContext(task="Test automation")
        ctx.store_artifact("automation_code", "print('test')")
        step = {"action": "test_automation", "params": {}}
        with mock_use_tool(return_value={"output": "test passed"}):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "test_automation"
        assert "automation_test" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_deploy_automation(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Deploy automation")
        step = {"action": "deploy_automation", "params": {}}
        with mock_call_llm(return_value="Deploy instructions"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "deploy_automation"
        assert "deploy_instructions" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_generic_ops_step(self, mock_call_llm):
        agent = OperatorAgent()
        ctx = AgentContext(task="Generic ops")
        step = {"action": "unknown_ops_action", "params": {}}
        with mock_call_llm(return_value="Generic result"):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is True
        assert result["action"] == "unknown_ops_action"

    @pytest.mark.asyncio
    async def test_execute_step_error(self):
        agent = OperatorAgent()
        ctx = AgentContext(task="Test")
        step = {"action": "assess_request", "params": {"task": "Test"}}
        with patch.object(agent, "_call_llm", new_callable=AsyncMock, side_effect=RuntimeError("fail")):
            result = await agent.execute_step(step, ctx)
        assert result["success"] is False
        assert "error" in result


class TestOperatorAgentReflect:
    """Tests for OperatorAgent.reflect()."""

    @pytest.mark.asyncio
    async def test_report_done(self):
        agent = OperatorAgent()
        ctx = AgentContext(task="Ops")
        ctx.store_artifact("report", "Operations report")
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is False
        assert "complete" in reflection["assessment"]

    @pytest.mark.asyncio
    async def test_verification_done(self):
        agent = OperatorAgent()
        ctx = AgentContext(task="Ops")
        ctx.store_artifact("verification", "Verified")
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is True
        assert reflection["adjustments"]["next_action"] == "report"

    @pytest.mark.asyncio
    async def test_resolution_verification_done(self):
        agent = OperatorAgent()
        ctx = AgentContext(task="Ops")
        ctx.store_artifact("resolution_verification", "Resolved")
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is True
        assert reflection["adjustments"]["next_action"] == "report"

    @pytest.mark.asyncio
    async def test_in_progress(self):
        agent = OperatorAgent()
        ctx = AgentContext(task="Ops")
        reflection = await agent.reflect(ctx)
        assert reflection["should_continue"] is True
        assert "in progress" in reflection["assessment"].lower()
