"""
NEXUS CrewAI Engine — Multi-agent orchestration via CrewAI.

Integrates the CrewAI framework for role-based multi-agent collaboration.
CrewAI agents have defined roles, goals, and backstories that shape
their behavior and expertise.

Components:
  - CrewAIEngine: Main engine for creating and running CrewAI crews
  - Agent definitions with roles, goals, and backstories
  - Task definitions with expected outputs and agent assignments
  - Process types: Sequential and Hierarchical
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from nexus.core.config import get_settings
from nexus.core.exceptions import OrchestratorError

logger = logging.getLogger(__name__)


@dataclass
class CrewAIAgentDef:
    """Definition of a CrewAI agent."""
    role: str
    goal: str
    backstory: str
    allow_delegation: bool = False
    verbose: bool = True
    tools: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "goal": self.goal,
            "backstory": self.backstory,
            "allow_delegation": self.allow_delegation,
            "tools": self.tools,
        }


@dataclass
class CrewAITaskDef:
    """Definition of a CrewAI task."""
    description: str
    expected_output: str
    agent_role: str
    async_execution: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "expected_output": self.expected_output,
            "agent_role": self.agent_role,
            "async_execution": self.async_execution,
        }


# Pre-defined agent templates
AGENT_TEMPLATES = {
    "researcher": CrewAIAgentDef(
        role="Senior Research Analyst",
        goal="Uncover cutting-edge developments and provide thorough, factual research",
        backstory="You are a world-class research analyst with decades of experience across multiple domains. You have a talent for finding relevant information, identifying patterns, and synthesizing complex data into clear insights. Your research is always well-sourced and reliable.",
        tools=["web_search", "search_memory", "store_memory"],
    ),
    "developer": CrewAIAgentDef(
        role="Senior Software Engineer",
        goal="Write clean, efficient, well-tested code that solves problems effectively",
        backstory="You are an expert software engineer with deep knowledge of multiple programming languages, frameworks, and best practices. You write clean, maintainable code and always consider edge cases, performance, and security.",
        tools=["execute_code", "read_file", "write_file", "search_files"],
    ),
    "analyst": CrewAIAgentDef(
        role="Data Analyst",
        goal="Extract meaningful insights from data through rigorous analysis",
        backstory="You are a skilled data analyst who excels at finding patterns, trends, and anomalies in data. You use statistical methods and visualization to communicate findings clearly. You always validate your conclusions.",
        tools=["execute_code", "read_file", "knowledge_query"],
    ),
    "writer": CrewAIAgentDef(
        role="Technical Writer",
        goal="Create clear, well-structured documentation and reports",
        backstory="You are an experienced technical writer who can explain complex concepts in simple terms. You create well-organized, comprehensive documentation that serves both technical and non-technical audiences.",
        tools=["read_file", "write_file", "search_memory"],
    ),
    "manager": CrewAIAgentDef(
        role="Project Manager",
        goal="Coordinate team efforts and ensure tasks are completed on time and to specification",
        backstory="You are an experienced project manager who excels at breaking down complex projects into manageable tasks, coordinating team members, and ensuring quality delivery. You communicate clearly and make data-driven decisions.",
        allow_delegation=True,
        tools=["spawn_agent", "list_agents", "agent_status"],
    ),
}


class CrewAIEngine:
    """
    CrewAI integration engine for NEXUS.

    Provides:
      - Agent creation from templates or custom definitions
      - Task assignment and execution
      - Sequential and hierarchical crew processes
      - Integration with NEXUS LLM router and memory

    Usage:
        engine = CrewAIEngine()
        result = await engine.run_crew(
            agents=["researcher", "writer"],
            tasks=[
                {"description": "Research AI agents", "expected_output": "Report", "agent_role": "researcher"},
                {"description": "Write summary", "expected_output": "Article", "agent_role": "writer"},
            ],
        )
    """

    def __init__(self):
        self.settings = get_settings()
        self._crews_run = 0

    async def run_crew(
        self,
        agents: list[str],
        tasks: list[dict[str, str]],
        process: str = "sequential",
        verbose: bool = True,
    ) -> dict[str, Any]:
        """
        Run a CrewAI crew with the specified agents and tasks.

        Tries to use the CrewAI library directly. Falls back to a
        NEXUS-native simulation using the LLM router.

        Args:
            agents: List of agent role names (from templates or custom).
            tasks: List of task definitions.
            process: Process type (sequential, hierarchical).
            verbose: Whether to print crew execution details.

        Returns:
            Dict with crew execution results.
        """
        self._crews_run += 1

        # Try native CrewAI first
        try:
            return await self._run_native_crew(agents, tasks, process, verbose)
        except ImportError:
            logger.info("CrewAI library not available, using NEXUS-native crew execution")
        except Exception as e:
            logger.warning("Native CrewAI execution failed: %s, falling back to NEXUS-native", e)

        # Fallback: NEXUS-native crew execution
        return await self._run_native_crew_fallback(agents, tasks, process)

    async def _run_native_crew(
        self,
        agents: list[str],
        tasks: list[dict[str, str]],
        process: str,
        verbose: bool,
    ) -> dict[str, Any]:
        """Run crew using the actual CrewAI library."""
        from crewai import Agent, Task, Crew, Process

        # Create agents
        crew_agents = []
        agent_map = {}
        for role_name in agents:
            template = AGENT_TEMPLATES.get(role_name, CrewAIAgentDef(
                role=role_name, goal=f"Complete tasks as {role_name}",
                backstory=f"You are an expert {role_name}.",
            ))
            agent = Agent(
                role=template.role,
                goal=template.goal,
                backstory=template.backstory,
                allow_delegation=template.allow_delegation,
                verbose=verbose,
            )
            crew_agents.append(agent)
            agent_map[role_name] = agent

        # Create tasks
        crew_tasks = []
        for task_def in tasks:
            agent = agent_map.get(task_def.get("agent_role", ""), crew_agents[0] if crew_agents else None)
            task = Task(
                description=task_def["description"],
                expected_output=task_def.get("expected_output", "Task completion"),
                agent=agent,
            )
            crew_tasks.append(task)

        # Create and run crew
        crew_process = Process.sequential if process == "sequential" else Process.hierarchical
        crew = Crew(
            agents=crew_agents,
            tasks=crew_tasks,
            process=crew_process,
            verbose=verbose,
        )

        result = await asyncio.to_thread(crew.kickoff)

        return {
            "status": "completed",
            "engine": "crewai_native",
            "agents_used": agents,
            "task_count": len(tasks),
            "result": str(result),
        }

    async def _run_native_crew_fallback(
        self,
        agents: list[str],
        tasks: list[dict[str, str]],
        process: str,
    ) -> dict[str, Any]:
        """Fallback crew execution using NEXUS LLM router."""
        results = []
        agent_contexts = {role: "" for role in agents}

        for task_def in tasks:
            role = task_def.get("agent_role", agents[0] if agents else "general")
            template = AGENT_TEMPLATES.get(role, CrewAIAgentDef(
                role=role, goal=f"Complete task as {role}",
                backstory=f"You are an expert {role}.",
            ))

            try:
                from nexus.llm.router import LLMRouter, TaskComplexity
                router = LLMRouter()

                context = agent_contexts.get(role, "")
                messages = [
                    {"role": "system", "content": f"Role: {template.role}\nGoal: {template.goal}\nBackstory: {template.backstory}"},
                    {"role": "user", "content": f"Task: {task_def['description']}\nExpected output: {task_def.get('expected_output', 'Complete the task')}\nContext from previous work: {context[:500] if context else 'None'}"},
                ]

                response = await router.complete(
                    messages=messages,
                    task_complexity=TaskComplexity.MEDIUM,
                    temperature=0.5,
                )

                result_text = response.content
                agent_contexts[role] = result_text[:2000]
                results.append({
                    "agent_role": role,
                    "task": task_def["description"][:100],
                    "result": result_text,
                    "status": "completed",
                })

            except Exception as e:
                results.append({
                    "agent_role": role,
                    "task": task_def["description"][:100],
                    "result": f"Error: {str(e)}",
                    "status": "failed",
                })

        completed = sum(1 for r in results if r["status"] == "completed")
        return {
            "status": "completed" if completed == len(tasks) else "partial",
            "engine": "nexus_native_fallback",
            "agents_used": agents,
            "task_count": len(tasks),
            "completed_tasks": completed,
            "results": results,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        return {
            "engine": "crewai",
            "crews_run": self._crews_run,
            "agent_templates": list(AGENT_TEMPLATES.keys()),
            "native_available": self._check_native_available(),
        }

    def _check_native_available(self) -> bool:
        """Check if the CrewAI library is available."""
        try:
            import crewai
            return True
        except ImportError:
            return False
