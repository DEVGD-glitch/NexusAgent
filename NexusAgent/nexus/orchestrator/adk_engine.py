"""
NEXUS ADK Engine — Google Agent Development Kit integration.

Integrates Google's ADK (Agent Development Kit) for building
production-grade agents with tool use, memory, and orchestration.

Components:
  - ADKEngine: Main engine for creating and running ADK agents
  - Agent builder with tool configuration
  - Session management and memory integration
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
class ADKAgentConfig:
    """Configuration for an ADK agent."""
    name: str
    description: str
    model: str = "gemini-2.0-flash"
    instruction: str = ""
    tools: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "model": self.model,
            "instruction": self.instruction,
            "tools": self.tools,
        }


class ADKEngine:
    """
    Google ADK integration engine for NEXUS.

    Provides:
      - Agent creation using ADK patterns
      - Tool registration and execution
      - Session management
      - Sequential and parallel agent execution

    Usage:
        engine = ADKEngine()
        result = await engine.run_agent(
            agent_config=ADKAgentConfig(
                name="research_agent",
                description="Research agent using Gemini",
                instruction="You are a research assistant",
            ),
            task="Find recent advances in AI",
        )
    """

    def __init__(self):
        self.settings = get_settings()
        self._agents_run = 0
        self._sessions: dict[str, dict[str, Any]] = {}

    async def run_agent(
        self,
        agent_config: ADKAgentConfig,
        task: str,
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Run an ADK agent for a specific task.

        Tries the native Google ADK library first, then falls back
        to NEXUS-native execution using the LLM router.

        Args:
            agent_config: Agent configuration.
            task: Task description.
            session_id: Optional session ID for continuity.

        Returns:
            Dict with agent execution results.
        """
        self._agents_run += 1

        # Try native ADK first
        try:
            return await self._run_native_adk(agent_config, task, session_id)
        except ImportError:
            logger.info("Google ADK not available, using NEXUS-native ADK execution")
        except Exception as e:
            logger.warning("Native ADK execution failed: %s, falling back", e)

        # Fallback: NEXUS-native execution
        return await self._run_native_fallback(agent_config, task, session_id)

    async def _run_native_adk(
        self,
        agent_config: ADKAgentConfig,
        task: str,
        session_id: Optional[str],
    ) -> dict[str, Any]:
        """Run agent using the actual Google ADK library."""
        from google.adk import Agent, Runner

        # Build ADK agent
        agent = Agent(
            name=agent_config.name,
            description=agent_config.description,
            model=agent_config.model,
            instruction=agent_config.instruction,
        )

        # Create runner
        runner = Runner(agent=agent)

        # Run the agent
        result = await asyncio.to_thread(runner.run, task)

        return {
            "status": "completed",
            "engine": "adk_native",
            "agent_name": agent_config.name,
            "result": str(result),
        }

    async def _run_native_fallback(
        self,
        agent_config: ADKAgentConfig,
        task: str,
        session_id: Optional[str],
    ) -> dict[str, Any]:
        """Fallback ADK execution using NEXUS LLM router."""
        # Build context from session
        session_context = ""
        if session_id and session_id in self._sessions:
            session_context = self._sessions[session_id].get("context", "")

        try:
            from nexus.llm.router import LLMRouter, TaskComplexity
            router = LLMRouter()

            messages = [
                {"role": "system", "content": (
                    f"You are agent '{agent_config.name}'.\n"
                    f"Description: {agent_config.description}\n"
                    f"Instructions: {agent_config.instruction}\n"
                    f"Available tools: {', '.join(agent_config.tools) if agent_config.tools else 'standard NEXUS tools'}"
                )},
            ]

            if session_context:
                messages.append({"role": "system", "content": f"Previous context:\n{session_context[:1000]}"})

            messages.append({"role": "user", "content": task})

            response = await router.complete(
                messages=messages,
                task_complexity=TaskComplexity.MEDIUM,
                temperature=0.5,
            )

            result_text = response.content

            # Update session
            if session_id:
                self._sessions[session_id] = {
                    "context": result_text[:2000],
                    "last_task": task[:200],
                }

            return {
                "status": "completed",
                "engine": "nexus_native_fallback",
                "agent_name": agent_config.name,
                "result": result_text,
                "model_used": response.model,
                "provider": response.provider.value,
            }

        except Exception as e:
            return {
                "status": "failed",
                "engine": "nexus_native_fallback",
                "agent_name": agent_config.name,
                "result": f"Error: {str(e)}",
            }

    async def run_multi_agent(
        self,
        agents: list[ADKAgentConfig],
        tasks: list[str],
        parallel: bool = False,
    ) -> dict[str, Any]:
        """
        Run multiple ADK agents either sequentially or in parallel.

        Args:
            agents: List of agent configurations.
            tasks: List of tasks (one per agent).
            parallel: Whether to run agents in parallel.

        Returns:
            Dict with multi-agent execution results.
        """
        results = []

        if parallel and len(agents) > 1:
            coros = [self.run_agent(agent, task) for agent, task in zip(agents, tasks)]
            results = await asyncio.gather(*coros, return_exceptions=True)
            results = [r if not isinstance(r, Exception) else {"status": "failed", "error": str(r)} for r in results]
        else:
            for agent, task in zip(agents, tasks):
                result = await self.run_agent(agent, task)
                results.append(result)

        return {
            "status": "completed",
            "engine": "adk_multi_agent",
            "agents_count": len(agents),
            "parallel": parallel,
            "results": results,
        }

    def create_session(self) -> str:
        """Create a new session and return its ID."""
        import uuid
        session_id = uuid.uuid4().hex[:12]
        self._sessions[session_id] = {"context": "", "last_task": ""}
        return session_id

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        """Get session data."""
        return self._sessions.get(session_id)

    def get_stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        return {
            "engine": "adk",
            "agents_run": self._agents_run,
            "active_sessions": len(self._sessions),
            "native_available": self._check_native_available(),
        }

    def _check_native_available(self) -> bool:
        """Check if the Google ADK library is available."""
        try:
            import google.adk
            return True
        except ImportError:
            return False
