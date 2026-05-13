"""
NEXUS Analyst Agent — Specialized in data analysis and insights.

The Analyst excels at:
  - Data analysis and statistical interpretation
  - Visualization and reporting
  - Trend identification and forecasting
  - Comparative analysis and benchmarking
  - Decision support with evidence-based recommendations
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from nexus.agents.base import BaseAgent, AgentContext, AgentCapability
from nexus.core.registry import AgentCapability as Cap

logger = logging.getLogger(__name__)


class AnalystAgent(BaseAgent):
    """
    Data Analysis Agent for insights, reporting, and decision support.

    Uses a structured analytical methodology:
      1. Define the analytical question
      2. Gather and prepare data
      3. Perform analysis (statistical, comparative, trend)
      4. Generate insights and conclusions
      5. Create visualizations and reports

    Tools: data_analysis, visualization, reporting, web_search,
           knowledge_graph, code_execute
    """

    def __init__(self):
        super().__init__(
            agent_type="analyst",
            description="Data analysis agent for insights and reporting",
            skills=[
                "data_analysis", "visualization", "reporting",
                "statistical_analysis", "trend_forecasting",
                "comparative_analysis", "benchmarking",
            ],
        )

    @property
    def system_prompt(self) -> str:
        return (
            "You are NEXUS Analyst, a specialized data analysis agent. Your role is to:\n"
            "1. Define clear analytical questions and hypotheses\n"
            "2. Identify, collect, and prepare relevant data\n"
            "3. Apply appropriate analytical methods (statistical, comparative, trend)\n"
            "4. Generate actionable insights from data\n"
            "5. Create clear visualizations and reports\n"
            "6. Provide evidence-based recommendations\n\n"
            "Analytical methodology:\n"
            "- Start with a clear question or hypothesis\n"
            "- Verify data quality before analysis\n"
            "- Use appropriate statistical methods\n"
            "- Acknowledge limitations and uncertainties\n"
            "- Present findings visually when possible\n"
            "- Connect insights to actionable decisions\n\n"
            "Use tools: code_execute for data processing and analysis, "
            "web_search for gathering external data, knowledge_graph for structured data, "
            "memory for accessing historical analyses."
        )

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [Cap.ANALYSIS, Cap.REASONING]

    async def plan(self, context: AgentContext) -> list[dict[str, Any]]:
        """Create an analysis plan."""
        task = context.task

        plan = [
            {
                "action": "define_question",
                "params": {"task": task},
                "description": "Define the analytical question and scope",
            },
            {
                "action": "gather_data",
                "params": {},
                "description": "Gather and prepare relevant data",
            },
            {
                "action": "perform_analysis",
                "params": {},
                "description": "Execute the core analysis",
            },
            {
                "action": "generate_insights",
                "params": {},
                "description": "Extract insights and conclusions",
            },
            {
                "action": "create_report",
                "params": {},
                "description": "Create final report with visualizations",
            },
        ]

        # Adjust for comparative analysis
        task_lower = task.lower()
        if any(kw in task_lower for kw in ["compare", "versus", "vs", "benchmark", "contrast"]):
            plan.insert(2, {
                "action": "comparative_analysis",
                "params": {},
                "description": "Perform comparative analysis",
            })

        return plan

    async def execute_step(self, step: dict[str, Any], context: AgentContext) -> dict[str, Any]:
        """Execute an analysis step."""
        action = step.get("action", "")
        params = step.get("params", {})

        try:
            handler = getattr(self, f"_step_{action}", None)
            if handler:
                result = await handler(params, context)
            else:
                result = await self._generic_analysis_step(action, params, context)

            return {"success": True, "result": result, "action": action}

        except Exception as e:
            logger.error("Analyst step '%s' failed: %s", action, e)
            return {"success": False, "error": str(e), "action": action}

    async def _step_define_question(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Define the analytical question and scope."""
        task = params.get("task", context.task)

        messages = [
            {"role": "system", "content": (
                "Define the analytical question from the following request. Specify:\n"
                "1. Primary question to answer\n"
                "2. Key metrics or variables of interest\n"
                "3. Scope and boundaries of analysis\n"
                "4. Required data sources\n"
                "5. Expected output format\n"
                "Return a structured analytical brief."
            )},
            {"role": "user", "content": task},
        ]

        brief = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("analytical_brief", brief)

        return {"brief": brief}

    async def _step_gather_data(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Gather and prepare relevant data."""
        brief = context.artifacts.get("analytical_brief", context.task)

        # Try web search for external data
        search_result = await self._use_tool("web_search", {
            "query": f"data statistics {context.task[:100]}",
            "num": 5,
        })
        context.store_artifact("external_data", search_result)

        # Use LLM to structure available data
        messages = [
            {"role": "system", "content": (
                "Based on the analytical brief and available data, prepare a data inventory:\n"
                "1. List available data points\n"
                "2. Identify data gaps\n"
                "3. Note data quality concerns\n"
                "4. Suggest proxy metrics where direct data is unavailable\n"
            )},
            {"role": "user", "content": str(brief)[:3000]},
        ]

        data_inventory = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("data_inventory", data_inventory)

        return {"data_inventory": data_inventory, "tool_used": "web_search"}

    async def _step_perform_analysis(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Execute the core analysis."""
        brief = context.artifacts.get("analytical_brief", "")
        data = context.artifacts.get("data_inventory", "")

        # Generate analysis code
        messages = [
            {"role": "system", "content": (
                "Write Python code to perform the analysis described in the brief. "
                "Use standard libraries (pandas, numpy, scipy, matplotlib). "
                "Include:\n"
                "1. Data loading and preparation\n"
                "2. Statistical calculations\n"
                "3. Key findings as print statements\n"
                "4. Any necessary visualizations\n"
                "Write COMPLETE, executable code."
            )},
            {"role": "user", "content": (
                f"Analytical brief:\n{str(brief)[:2000]}\n\n"
                f"Data inventory:\n{str(data)[:2000]}"
            )},
        ]

        analysis_code = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("analysis_code", analysis_code)

        # Execute the analysis code
        result = await self._use_tool("code_execute", {
            "code": analysis_code,
            "language": "python",
            "timeout": 60,
        })
        context.store_artifact("analysis_result", result)

        return {"analysis": result, "tool_used": "code_execute"}

    async def _step_comparative_analysis(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Perform comparative analysis between entities."""
        brief = context.artifacts.get("analytical_brief", context.task)

        messages = [
            {"role": "system", "content": (
                "Perform a comparative analysis. For each entity:\n"
                "1. Identify key comparison dimensions\n"
                "2. Score/rate each entity on each dimension\n"
                "3. Identify strengths and weaknesses\n"
                "4. Provide an overall comparison summary\n"
                "Return a structured comparative analysis."
            )},
            {"role": "user", "content": str(brief)[:3000]},
        ]

        comparison = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("comparative_analysis", comparison)

        return {"comparison": comparison}

    async def _step_generate_insights(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Extract insights from the analysis."""
        analysis_result = context.artifacts.get("analysis_result", {})
        comparison = context.artifacts.get("comparative_analysis", "")

        messages = [
            {"role": "system", "content": (
                "Extract key insights from the analysis results. For each insight:\n"
                "1. State the finding clearly\n"
                "2. Provide supporting evidence (data point, statistic)\n"
                "3. Explain the implication\n"
                "4. Rate confidence level (high/medium/low)\n"
                "Also identify:\n"
                "- Surprising or counter-intuitive findings\n"
                "- Limitations of the analysis\n"
                "- Areas needing further investigation\n"
            )},
            {"role": "user", "content": (
                f"Analysis results:\n{str(analysis_result)[:2000]}\n\n"
                f"Comparative analysis:\n{str(comparison)[:2000]}"
            )},
        ]

        insights = await self._call_llm(messages, temperature=0.3)
        context.store_artifact("insights", insights)

        return {"insights": insights}

    async def _step_create_report(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Create the final analytical report."""
        brief = context.artifacts.get("analytical_brief", "")
        insights = context.artifacts.get("insights", "")
        analysis = context.artifacts.get("analysis_result", "")

        messages = [
            {"role": "system", "content": (
                "Create a comprehensive analytical report with the following sections:\n"
                "1. Executive Summary — Key findings in 3-5 bullets\n"
                "2. Methodology — How the analysis was conducted\n"
                "3. Findings — Detailed results with data points\n"
                "4. Insights — Interpretation and implications\n"
                "5. Recommendations — Actionable next steps\n"
                "6. Limitations — Caveats and data quality notes\n"
                "Format the report in clear, professional language."
            )},
            {"role": "user", "content": (
                f"Analytical brief:\n{str(brief)[:1500]}\n\n"
                f"Insights:\n{str(insights)[:2000]}\n\n"
                f"Analysis results:\n{str(analysis)[:1500]}"
            )},
        ]

        report = await self._call_llm(messages, temperature=0.3)
        context.store_artifact("report", report)
        context.add_message("assistant", f"Analysis report generated: {report[:500]}")

        return {"report": report}

    async def _generic_analysis_step(self, action: str, params: dict, context: AgentContext) -> dict[str, Any]:
        """Handle generic analysis steps."""
        messages = [
            {"role": "system", "content": f"You are performing the analysis step: {action}"},
            {"role": "user", "content": f"Task: {context.task}\nStep: {action}\nParams: {params}"},
        ]
        result = await self._call_llm(messages, temperature=0.3)
        return {"result": result}

    async def reflect(self, context: AgentContext) -> dict[str, Any]:
        """Reflect on analysis progress."""
        # If report is done, we're done
        if "report" in context.artifacts:
            return {
                "should_continue": False,
                "assessment": "Analysis report complete.",
            }

        # If insights generated, move to report
        if "insights" in context.artifacts:
            return {
                "should_continue": True,
                "assessment": "Insights generated. Ready to create report.",
            }

        return {
            "should_continue": True,
            "assessment": "Analysis in progress. Continuing.",
        }
