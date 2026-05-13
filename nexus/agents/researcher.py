"""
NEXUS Researcher Agent — Specialized in information gathering and synthesis.

The Researcher excels at:
  - Web search across multiple engines
  - Document analysis and fact extraction
  - Deep research with iterative refinement
  - Source verification and citation
  - Knowledge graph enrichment
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from nexus.agents.base import BaseAgent, AgentContext, AgentCapability
from nexus.core.registry import AgentCapability as Cap

logger = logging.getLogger(__name__)


class ResearcherAgent(BaseAgent):
    """
    Research Agent for information gathering and synthesis.

    Uses a structured research methodology:
      1. Decompose the research question into sub-queries
      2. Search multiple sources for each sub-query
      3. Evaluate and cross-reference findings
      4. Synthesize into a coherent answer with citations
      5. Verify key claims against additional sources

    Tools: web_search, deep_research, rag_pipeline, knowledge_graph,
           document_analysis, fact_checking
    """

    def __init__(self):
        super().__init__(
            agent_type="researcher",
            description="Research agent for information gathering and synthesis",
            skills=[
                "web_search", "document_analysis", "fact_checking",
                "deep_research", "knowledge_graph_query", "rag_pipeline",
                "source_verification", "citation_tracking",
            ],
        )
        self._research_depth: str = "standard"  # quick, standard, deep

    @property
    def system_prompt(self) -> str:
        return (
            "You are NEXUS Researcher, a specialized research agent. Your role is to:\n"
            "1. Decompose complex research questions into focused sub-queries\n"
            "2. Search multiple authoritative sources for each sub-query\n"
            "3. Cross-reference and verify findings across sources\n"
            "4. Synthesize information into clear, well-cited answers\n"
            "5. Flag contradictions, uncertainties, and gaps in available data\n\n"
            "Research methodology:\n"
            "- Start broad, then narrow down to specifics\n"
            "- Always cite sources with URLs when available\n"
            "- Distinguish between facts, expert opinions, and speculation\n"
            "- Note the date/currency of information\n"
            "- When sources conflict, present multiple perspectives\n\n"
            "Use tools: web_search for finding information, deep_research for "
            "complex multi-step investigations, knowledge_graph for structured data, "
            "rag_pipeline for document analysis."
        )

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [Cap.RESEARCH, Cap.BROWSING, Cap.REASONING]

    async def plan(self, context: AgentContext) -> list[dict[str, Any]]:
        """
        Create a research plan by decomposing the task.

        Steps:
        1. Analyze the research question
        2. Generate sub-queries
        3. Search for each sub-query
        4. Cross-reference findings
        5. Synthesize final answer
        """
        task = context.task

        # Use LLM to decompose the research question
        decomposition_messages = [
            {"role": "system", "content": (
                "Decompose the following research question into 3-5 focused sub-queries. "
                "Return a JSON array of objects with 'sub_query' and 'rationale' fields."
            )},
            {"role": "user", "content": task},
        ]

        try:
            response = await self._call_llm(decomposition_messages, temperature=0.3)
            context.store_artifact("decomposition", response)
        except Exception as e:
            logger.warning("Decomposition failed, using task as single query: %s", e)
            response = task

        # Determine research depth based on task complexity
        depth_indicators = {
            "deep": ["comprehensive", "exhaustive", "in-depth", "thorough", "complete analysis"],
            "quick": ["quick", "brief", "simple", "fast", "just"],
        }
        task_lower = task.lower()
        for depth, indicators in depth_indicators.items():
            if any(ind in task_lower for ind in indicators):
                self._research_depth = depth
                break

        # Build research plan
        plan = [
            {
                "action": "analyze_question",
                "params": {"task": task, "decomposition": response},
                "description": "Analyze and decompose the research question",
            },
            {
                "action": "web_search",
                "params": {"query": task, "num_results": 10},
                "description": "Initial broad search on the main question",
            },
            {
                "action": "deep_research",
                "params": {"query": task, "iterations": 3 if self._research_depth == "deep" else 2},
                "description": "Conduct deep research with iterative refinement",
            },
            {
                "action": "cross_reference",
                "params": {},
                "description": "Cross-reference findings and verify claims",
            },
            {
                "action": "synthesize",
                "params": {},
                "description": "Synthesize findings into a coherent answer with citations",
            },
        ]

        return plan

    async def execute_step(self, step: dict[str, Any], context: AgentContext) -> dict[str, Any]:
        """Execute a research step."""
        action = step.get("action", "")
        params = step.get("params", {})

        try:
            if action == "analyze_question":
                result = await self._analyze_question(params, context)
            elif action == "web_search":
                result = await self._do_web_search(params, context)
            elif action == "deep_research":
                result = await self._do_deep_research(params, context)
            elif action == "cross_reference":
                result = await self._cross_reference(params, context)
            elif action == "synthesize":
                result = await self._synthesize_findings(params, context)
            else:
                result = await self._generic_step(action, params, context)

            return {"success": True, "result": result, "action": action}

        except Exception as e:
            logger.error("Research step '%s' failed: %s", action, e)
            return {"success": False, "error": str(e), "action": action}

    async def _analyze_question(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Analyze the research question and extract key entities/topics."""
        task = params.get("task", context.task)

        messages = [
            {"role": "system", "content": (
                "Analyze this research question. Identify:\n"
                "1. Key entities and concepts\n"
                "2. Type of information needed (factual, analytical, comparative)\n"
                "3. Temporal scope (current, historical, future projections)\n"
                "4. Domain (technology, science, business, etc.)\n"
                "Return a structured analysis."
            )},
            {"role": "user", "content": task},
        ]

        analysis = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("question_analysis", analysis)
        context.add_message("assistant", f"Question analysis complete: {analysis[:500]}")

        return {"analysis": analysis}

    async def _do_web_search(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Perform web search."""
        query = params.get("query", context.task)
        num = params.get("num_results", 10)

        search_result = await self._use_tool("web_search", {"query": query, "num": num})
        context.store_artifact("search_results", search_result)
        context.add_message("assistant", f"Found search results for: {query}")

        return {"query": query, "results": search_result, "tool_used": "web_search"}

    async def _do_deep_research(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Conduct deep research using the deep_research module."""
        query = params.get("query", context.task)
        iterations = params.get("iterations", 2)

        try:
            from nexus.knowledge.deep_research import DeepResearch
            engine = DeepResearch()
            depth = "quick" if iterations <= 1 else "deep" if iterations >= 3 else "medium"
            result = await engine.investigate(topic=query, depth=depth)
            context.store_artifact("deep_research", result)
            context.add_message("assistant", f"Deep research completed: {str(result)[:500]}")
            return {"research": result, "tool_used": "deep_research"}
        except Exception as e:
            logger.warning("Deep research failed, falling back to web search: %s", e)
            return await self._do_web_search({"query": query}, context)

    async def _cross_reference(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Cross-reference findings from multiple sources."""
        findings = context.artifacts.get("search_results", [])
        deep_findings = context.artifacts.get("deep_research", {})

        messages = [
            {"role": "system", "content": (
                "You are cross-referencing research findings. Identify:\n"
                "1. Points of agreement across sources\n"
                "2. Contradictions between sources\n"
                "3. Gaps in the available information\n"
                "4. Most reliable and authoritative sources\n"
                "Provide a structured cross-reference analysis."
            )},
            {"role": "user", "content": (
                f"Search results: {str(findings)[:2000]}\n\n"
                f"Deep research findings: {str(deep_findings)[:2000]}"
            )},
        ]

        analysis = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("cross_reference", analysis)

        return {"cross_reference": analysis}

    async def _synthesize_findings(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Synthesize all findings into a coherent answer."""
        all_artifacts = {
            k: str(v)[:1500] for k, v in context.artifacts.items()
            if k in ("search_results", "deep_research", "cross_reference", "question_analysis")
        }

        messages = [
            {"role": "system", "content": (
                "Synthesize the following research into a comprehensive answer. "
                "Include citations where available. Structure your answer with "
                "clear sections. Distinguish between established facts and "
                "areas of uncertainty."
            )},
            {"role": "user", "content": (
                f"Original question: {context.task}\n\n"
                f"Research data:\n{str(all_artifacts)}"
            )},
        ]

        synthesis = await self._call_llm(messages, temperature=0.3)
        context.store_artifact("synthesis", synthesis)
        context.add_message("assistant", synthesis)

        return {"synthesis": synthesis}

    async def _generic_step(self, action: str, params: dict, context: AgentContext) -> dict[str, Any]:
        """Handle generic/unknown steps using LLM."""
        messages = [
            {"role": "system", "content": f"You are performing the research step: {action}"},
            {"role": "user", "content": f"Task: {context.task}\nStep: {action}\nParams: {params}"},
        ]
        result = await self._call_llm(messages, temperature=0.3)
        return {"result": result}

    async def reflect(self, context: AgentContext) -> dict[str, Any]:
        """
        Reflect on research progress.

        Evaluates whether we have enough information to answer the question
        or if more research is needed.
        """
        artifacts_count = len([k for k in context.artifacts if k in (
            "search_results", "deep_research", "cross_reference", "synthesis"
        )])

        # If we've synthesized, we're done
        if "synthesis" in context.artifacts:
            return {
                "should_continue": False,
                "assessment": "Research synthesis complete. Answer is ready.",
            }

        # If we have cross-referenced findings, move to synthesis
        if "cross_reference" in context.artifacts:
            return {
                "should_continue": True,
                "assessment": "Cross-reference complete. Ready to synthesize.",
                "adjustments": {"next_action": "synthesize"},
            }

        # Otherwise continue research
        if artifacts_count < 2:
            return {
                "should_continue": True,
                "assessment": "Need more research data. Continuing.",
            }

        return {
            "should_continue": True,
            "assessment": "Sufficient data gathered. Moving to cross-reference.",
        }
