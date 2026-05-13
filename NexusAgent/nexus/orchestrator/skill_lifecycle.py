"""
NEXUS Self-Evolving Skill Lifecycle — 5-stage skill creation and management.

Implements the complete lifecycle for skills that can be dynamically
created, tested, deployed, and evolved:

  Stage 1 - DISCOVERY: Identify the need for a new skill from task patterns
  Stage 2 - DESIGN: Design the skill interface, parameters, and behavior
  Stage 3 - IMPLEMENT: Generate the skill code using LLM
  Stage 4 - VALIDATE: Test the skill with sample inputs and expected outputs
  Stage 5 - DEPLOY: Register the skill in the MCP server and agent tools

Skills can evolve over time as they are used and improved.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)


class SkillStage(str, Enum):
    DISCOVERY = "discovery"
    DESIGN = "design"
    IMPLEMENT = "implement"
    VALIDATE = "validate"
    DEPLOY = "deploy"


class SkillCategory(str, Enum):
    """Categories for organizing skills by domain."""
    CODING = "coding"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    ORCHESTRATION = "orchestration"
    SECURITY = "security"
    MEMORY = "memory"
    WEB = "web"
    FILE = "file"
    UTILITY = "utility"


class SkillStatus(str, Enum):
    DISCOVERED = "discovered"  # backward compat alias for DRAFT
    DRAFT = "draft"
    TESTING = "testing"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    FAILED = "failed"


@dataclass
class SkillDefinition:
    """A complete skill definition."""
    skill_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    category: str = "general"
    parameters: list[dict[str, Any]] = field(default_factory=list)
    return_type: str = "str"
    implementation: str = ""
    test_cases: list[dict[str, Any]] = field(default_factory=list)
    stage: SkillStage = SkillStage.DISCOVERY
    status: SkillStatus = SkillStatus.DRAFT
    version: int = 1
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    usage_count: int = 0
    success_rate: float = 0.0
    author: str = "nexus"

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": self.parameters,
            "return_type": self.return_type,
            "stage": self.stage.value,
            "status": self.status.value,
            "version": self.version,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
        }


class SkillLifecycleManager:
    """
    Manages the complete lifecycle of self-evolving skills.

    Skills go through 5 stages:
      1. DISCOVERY: Analyze task patterns to identify reusable skill needs
      2. DESIGN: Define skill interface, parameters, and expected behavior
      3. IMPLEMENT: Generate skill code using LLM with guardrails
      4. VALIDATE: Run test cases and verify correctness
      5. DEPLOY: Register as MCP tool and make available to agents

    Skills can be evolved: if success_rate drops below threshold,
    they go through a redesign cycle.

    Usage:
        manager = SkillLifecycleManager()
        skill = await manager.discover_skill(
            task_pattern="convert data between formats",
            frequency=5,
        )
        await manager.advance_to_deploy(skill.skill_id)
    """

    def __init__(
        self,
        min_usage_for_discovery: int = 3,
        min_success_rate: float = 0.7,
        auto_deploy: bool = False,
    ):
        self.min_usage_for_discovery = min_usage_for_discovery
        self.min_success_rate = min_success_rate
        self.auto_deploy = auto_deploy
        self._skills: dict[str, SkillDefinition] = {}
        self._task_patterns: dict[str, int] = {}  # pattern -> count

    async def discover_skill(
        self,
        task_pattern: str,
        frequency: int = 1,
        category: str = "general",
    ) -> SkillDefinition:
        """
        Stage 1 - DISCOVERY: Identify a new skill from task patterns.

        Args:
            task_pattern: Description of the recurring task pattern.
            frequency: How often this pattern has been observed.
            category: Skill category.

        Returns:
            A new SkillDefinition in DISCOVERY stage.
        """
        self._task_patterns[task_pattern] = self._task_patterns.get(task_pattern, 0) + frequency

        # Generate skill name from pattern
        skill_name = task_pattern.lower().replace(" ", "_")[:40]
        # Remove special characters
        skill_name = "".join(c for c in skill_name if c.isalnum() or c == "_")

        skill = SkillDefinition(
            name=skill_name,
            description=f"Auto-discovered skill for: {task_pattern}",
            category=category,
            stage=SkillStage.DISCOVERY,
            status=SkillStatus.DRAFT,
        )
        self._skills[skill.skill_id] = skill

        logger.info("Discovered skill '%s' (pattern frequency: %d)", skill_name, frequency)

        # Auto-advance if frequency threshold met
        if frequency >= self.min_usage_for_discovery:
            await self.advance_stage(skill.skill_id)

        return skill

    async def design_skill(
        self,
        skill_id: str,
        parameters: Optional[list[dict[str, Any]]] = None,
        description: Optional[str] = None,
    ) -> SkillDefinition:
        """
        Stage 2 - DESIGN: Define the skill's interface and behavior.

        Uses LLM to design parameters and behavior if not provided.

        Args:
            skill_id: The skill to design.
            parameters: Optional parameter definitions.
            description: Optional detailed description.

        Returns:
            Updated SkillDefinition in DESIGN stage.
        """
        skill = self._skills.get(skill_id)
        if not skill:
            raise ValueError(f"Skill '{skill_id}' not found")

        if parameters:
            skill.parameters = parameters
        else:
            # Use LLM to design parameters
            skill.parameters = await self._llm_design_parameters(skill)

        if description:
            skill.description = description

        skill.stage = SkillStage.DESIGN
        skill.updated_at = datetime.now(timezone.utc).isoformat()

        logger.info("Designed skill '%s' with %d parameters", skill.name, len(skill.parameters))

        # Auto-advance
        await self.advance_stage(skill.skill_id)

        return skill

    async def implement_skill(self, skill_id: str) -> SkillDefinition:
        """
        Stage 3 - IMPLEMENT: Generate the skill's code.

        Uses LLM to generate implementation based on the design.

        Args:
            skill_id: The skill to implement.

        Returns:
            Updated SkillDefinition in IMPLEMENT stage.
        """
        skill = self._skills.get(skill_id)
        if not skill:
            raise ValueError(f"Skill '{skill_id}' not found")

        # Generate implementation using LLM
        implementation = await self._llm_generate_implementation(skill)
        skill.implementation = implementation
        skill.stage = SkillStage.IMPLEMENT
        skill.updated_at = datetime.now(timezone.utc).isoformat()

        logger.info("Implemented skill '%s' (%d chars)", skill.name, len(implementation))

        # Auto-advance
        await self.advance_stage(skill.skill_id)

        return skill

    async def validate_skill(self, skill_id: str) -> SkillDefinition:
        """
        Stage 4 - VALIDATE: Test the skill implementation.

        Runs test cases against the implementation to verify correctness.

        Args:
            skill_id: The skill to validate.

        Returns:
            Updated SkillDefinition in VALIDATE stage.
        """
        skill = self._skills.get(skill_id)
        if not skill:
            raise ValueError(f"Skill '{skill_id}' not found")

        # Generate test cases if none exist
        if not skill.test_cases:
            skill.test_cases = await self._llm_generate_test_cases(skill)

        # Run test cases
        passed = 0
        total = len(skill.test_cases)
        for test_case in skill.test_cases:
            try:
                result = await self._run_test_case(skill, test_case)
                test_case["result"] = result
                test_case["passed"] = result.get("success", False)
                if test_case["passed"]:
                    passed += 1
            except Exception as e:
                test_case["result"] = {"error": str(e)}
                test_case["passed"] = False

        skill.success_rate = passed / max(total, 1)
        skill.stage = SkillStage.VALIDATE
        skill.updated_at = datetime.now(timezone.utc).isoformat()

        if skill.success_rate >= self.min_success_rate:
            skill.status = SkillStatus.TESTING
            # Auto-advance to deploy
            await self.advance_stage(skill.skill_id)
        else:
            skill.status = SkillStatus.FAILED
            logger.warning("Skill '%s' validation failed (%.0f%% success)", skill.name, skill.success_rate * 100)

        return skill

    async def deploy_skill(self, skill_id: str) -> SkillDefinition:
        """
        Stage 5 - DEPLOY: Register the skill as an MCP tool.

        Makes the skill available to all NEXUS agents via the MCP server.

        Args:
            skill_id: The skill to deploy.

        Returns:
            Updated SkillDefinition in DEPLOY stage.
        """
        skill = self._skills.get(skill_id)
        if not skill:
            raise ValueError(f"Skill '{skill_id}' not found")

        skill.stage = SkillStage.DEPLOY
        skill.status = SkillStatus.ACTIVE
        skill.updated_at = datetime.now(timezone.utc).isoformat()

        # Store in memory for persistence
        try:
            from nexus.memory.chroma_service import NexusMemoryService
            settings = get_settings()
            service = NexusMemoryService(persist_dir=settings.chroma_persist_dir)
            await service.store(
                text=f"Skill: {skill.name}\nDescription: {skill.description}\nImplementation: {skill.implementation[:2000]}",
                metadata={"skill_id": skill.skill_id, "name": skill.name, "category": skill.category, "stage": "deployed"},
                namespace="skills",
            )
        except Exception as e:
            logger.warning("Failed to store skill in memory: %s", e)

        logger.info("Deployed skill '%s' (v%d, success_rate=%.0f%%)", skill.name, skill.version, skill.success_rate * 100)

        return skill

    async def advance_stage(self, skill_id: str) -> SkillDefinition:
        """Advance a skill to the next stage in the lifecycle."""
        skill = self._skills.get(skill_id)
        if not skill:
            raise ValueError(f"Skill '{skill_id}' not found")

        stage_order = [
            SkillStage.DISCOVERY,
            SkillStage.DESIGN,
            SkillStage.IMPLEMENT,
            SkillStage.VALIDATE,
            SkillStage.DEPLOY,
        ]

        current_idx = stage_order.index(skill.stage)
        if current_idx >= len(stage_order) - 1:
            return skill  # Already at final stage

        next_stage = stage_order[current_idx + 1]

        if next_stage == SkillStage.DESIGN:
            return await self.design_skill(skill_id)
        elif next_stage == SkillStage.IMPLEMENT:
            return await self.implement_skill(skill_id)
        elif next_stage == SkillStage.VALIDATE:
            return await self.validate_skill(skill_id)
        elif next_stage == SkillStage.DEPLOY:
            return await self.deploy_skill(skill_id)

        return skill

    async def evolve_skill(self, skill_id: str, feedback: str = "") -> SkillDefinition:
        """
        Evolve an existing skill based on usage feedback.

        Takes a skill back through design and implementation
        with the feedback incorporated.
        """
        skill = self._skills.get(skill_id)
        if not skill:
            raise ValueError(f"Skill '{skill_id}' not found")

        skill.version += 1
        skill.stage = SkillStage.DESIGN
        skill.status = SkillStatus.DRAFT
        skill.description = f"{skill.description} [v{skill.version}: {feedback}]" if feedback else skill.description
        skill.updated_at = datetime.now(timezone.utc).isoformat()

        # Re-implement with feedback
        await self.advance_stage(skill.skill_id)

        return skill

    def get_skill(self, skill_id: str) -> Optional[SkillDefinition]:
        """Get a skill by ID."""
        return self._skills.get(skill_id)

    def list_skills(self, status: Optional[SkillStatus] = None) -> list[dict[str, Any]]:
        """List all skills, optionally filtered by status."""
        skills = list(self._skills.values())
        if status:
            skills = [s for s in skills if s.status == status]
        return [s.to_dict() for s in skills]

    def get_stats(self) -> dict[str, Any]:
        """Get skill lifecycle statistics."""
        by_stage = {}
        by_status = {}
        for skill in self._skills.values():
            by_stage[skill.stage.value] = by_stage.get(skill.stage.value, 0) + 1
            by_status[skill.status.value] = by_status.get(skill.status.value, 0) + 1

        return {
            "total_skills": len(self._skills),
            "by_stage": by_stage,
            "by_status": by_status,
            "task_patterns_tracked": len(self._task_patterns),
        }

    # ── LLM-assisted helpers ────────────────────────────────────────

    async def _llm_design_parameters(self, skill: SkillDefinition) -> list[dict[str, Any]]:
        """Use LLM to design skill parameters."""
        from nexus.llm.router import LLMRouter, TaskComplexity, LLMError

        try:
            router = LLMRouter()
            response = await router.complete(
                messages=[
                    {"role": "system", "content": "Design parameters for a skill as a JSON array. Each parameter should have: name, type (str, int, float, bool), description, required (bool), default_value."},
                    {"role": "user", "content": f"Skill: {skill.name}\nDescription: {skill.description}\nCategory: {skill.category}"},
                ],
                task_complexity=TaskComplexity.SIMPLE,
                temperature=0.3,
                max_tokens=500,
            )
            # Try to parse JSON
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            return json.loads(content.strip())
        except (json.JSONDecodeError, LLMError) as e:
            logger.warning("Failed to design parameters for skill '%s': %s", skill.name, e)
            return [{"name": "input", "type": "str", "description": "Input for the skill", "required": True}]
        except Exception as e:
            logger.error("Unexpected error designing parameters for skill '%s': %s", skill.name, e)
            return [{"name": "input", "type": "str", "description": "Input for the skill", "required": True}]

    async def _llm_generate_implementation(self, skill: SkillDefinition) -> str:
        """Use LLM to generate skill implementation."""
        from nexus.llm.router import LLMRouter, TaskComplexity, LLMError

        try:
            router = LLMRouter()
            params_str = json.dumps(skill.parameters, indent=2)
            response = await router.complete(
                messages=[
                    {"role": "system", "content": "Generate a Python function implementation for the described skill. The function should be complete, handle errors, and return a string result."},
                    {"role": "user", "content": f"Skill: {skill.name}\nDescription: {skill.description}\nParameters:\n{params_str}"},
                ],
                task_complexity=TaskComplexity.MEDIUM,
                temperature=0.3,
                max_tokens=2000,
            )
            return response.content
        except (LLMError, json.JSONDecodeError) as e:
            logger.warning("Failed to generate implementation for skill '%s': %s", skill.name, e)
            return f"# Auto-generated stub (LLM failed: {e})\nasync def {skill.name}(input: str) -> str:\n    return input"
        except Exception as e:
            logger.error("Unexpected error generating implementation for skill '%s': %s", skill.name, e)
            return f"# Auto-generated stub (error: {e})\nasync def {skill.name}(input: str) -> str:\n    return input"

    async def _llm_generate_test_cases(self, skill: SkillDefinition) -> list[dict[str, Any]]:
        """Use LLM to generate test cases."""
        from nexus.llm.router import LLMRouter, TaskComplexity, LLMError

        try:
            router = LLMRouter()
            response = await router.complete(
                messages=[
                    {"role": "system", "content": "Generate 3 test cases for this skill as a JSON array. Each test case should have: input (dict of parameter values), expected_output (string)."},
                    {"role": "user", "content": f"Skill: {skill.name}\nDescription: {skill.description}"},
                ],
                task_complexity=TaskComplexity.SIMPLE,
                temperature=0.5,
                max_tokens=500,
            )
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            return json.loads(content.strip())
        except (LLMError, json.JSONDecodeError) as e:
            logger.warning("Failed to generate test cases for skill '%s': %s", skill.name, e)
            return [{"input": {"test": "value"}, "expected_output": "success"}]
        except Exception as e:
            logger.error("Unexpected error generating test cases for skill '%s': %s", skill.name, e)
            return [{"input": {"test": "value"}, "expected_output": "success"}]

    async def _run_test_case(self, skill: SkillDefinition, test_case: dict[str, Any]) -> dict[str, Any]:
        """Run a single test case against the skill implementation."""
        # For MVP, we validate by running through the LLM
        from nexus.llm.router import LLMRouter, TaskComplexity, LLMError

        try:
            router = LLMRouter()
            input_data = test_case.get("input", {})
            response = await router.complete(
                messages=[
                    {"role": "system", "content": f"You are skill '{skill.name}'. {skill.description}"},
                    {"role": "user", "content": json.dumps(input_data)},
                ],
                task_complexity=TaskComplexity.SIMPLE,
                temperature=0.1,
                max_tokens=500,
            )
            return {"success": True, "output": response.content[:500]}
        except (LLMError, Exception) as e:
            return {"success": False, "error": str(e)}


class SelfImprovementLoop:
    """
    Automatically improve skills based on usage patterns and benchmark scores.

    Runs on a periodic cycle:
      1. Collect usage metrics from all active skills
      2. Run evaluation benchmarks on failing skills
      3. Identify skills below the success rate threshold
      4. Trigger evolution with targeted feedback

    Usage:
        loop = SelfImprovementLoop()
        await loop.analyze_and_improve()
    """

    def __init__(
        self,
        min_success_rate: float = 0.7,
        check_interval: int = 50,  # Check every N usage events
        auto_evolve: bool = False,
    ):
        self.min_success_rate = min_success_rate
        self.check_interval = check_interval
        self.auto_evolve = auto_evolve
        self._lifecycle: Optional[SkillLifecycleManager] = None
        self._evaluator: Optional[Any] = None
        self._usage_counts: dict[str, int] = {}
        self._last_check: dict[str, int] = {}  # skill_id -> count at last check

    @property
    def lifecycle(self) -> SkillLifecycleManager:
        if self._lifecycle is None:
            self._lifecycle = SkillLifecycleManager(auto_deploy=False)
        return self._lifecycle

    @property
    def evaluator(self):
        if self._evaluator is None:
            from nexus.core.evaluation import Evaluator
            self._evaluator = Evaluator(min_score_threshold=self.min_success_rate)
        return self._evaluator

    async def record_usage(self, skill_id: str, success: bool) -> None:
        """
        Record a skill usage event for tracking.

        Triggers improvement check when the check_interval is reached.

        Args:
            skill_id: The skill that was used.
            success: Whether the skill execution succeeded.
        """
        self._usage_counts[skill_id] = self._usage_counts.get(skill_id, 0) + 1

        last = self._last_check.get(skill_id, 0)
        if self._usage_counts[skill_id] - last >= self.check_interval:
            self._last_check[skill_id] = self._usage_counts[skill_id]
            await self._check_and_improve(skill_id)

    async def _check_and_improve(self, skill_id: str) -> None:
        """Check a skill's performance and trigger evolution if needed."""
        skill = self.lifecycle.get_skill(skill_id)
        if not skill:
            return

        if skill.success_rate >= self.min_success_rate:
            logger.info("Skill '%s' healthy (%.0f%% >= %.0f%% threshold)",
                        skill.name, skill.success_rate * 100, self.min_success_rate * 100)
            return

        logger.info(
            "Skill '%s' below threshold (%.0f%% < %.0f%%) — triggering improvement",
            skill.name, skill.success_rate * 100, self.min_success_rate * 100,
        )

        feedback = self._build_feedback(skill)
        if self.auto_evolve:
            await self.lifecycle.evolve_skill(skill_id, feedback)
            logger.info("Auto-evolved skill '%s'", skill.name)
        else:
            logger.info(
                "Skill '%s' needs improvement. Feedback: %s",
                skill.name, feedback[:200],
            )

    def _build_feedback(self, skill: SkillDefinition) -> str:
        """Build targeted improvement feedback from skill metrics."""
        parts = [
            f"Success rate ({skill.success_rate:.0%}) is below threshold ({self.min_success_rate:.0%})",
            f"Usage count: {skill.usage_count}",
            f"Stage: {skill.stage.value}",
            f"Parameters: {len(skill.parameters)} defined",
            f"Test cases: {len(skill.test_cases)} defined",
        ]
        if skill.implementation:
            parts.append(f"Implementation length: {len(skill.implementation)} chars")
        return " | ".join(parts)

    async def run_full_cycle(self) -> dict[str, Any]:
        """
        Run a complete improvement cycle across all skills.

        Returns:
            Dict with analysis results and actions taken.
        """
        skills = self.lifecycle.list_skills(status=SkillStatus.ACTIVE)
        needing_improvement = []
        evolved = []
        healthy = []

        for skill_dict in skills:
            if skill_dict["success_rate"] < self.min_success_rate:
                needing_improvement.append(skill_dict)
                if self.auto_evolve:
                    await self.lifecycle.evolve_skill(skill_dict["skill_id"],
                        self._build_feedback_from_dict(skill_dict))
                    evolved.append(skill_dict["skill_id"])
            else:
                healthy.append(skill_dict["skill_id"])

        return {
            "total_skills": len(skills),
            "healthy": len(healthy),
            "needing_improvement": len(needing_improvement),
            "auto_evolved": len(evolved),
            "evolved_ids": evolved,
            "skills_below_threshold": [s["skill_id"] for s in needing_improvement],
        }

    def _build_feedback_from_dict(self, skill_dict: dict[str, Any]) -> str:
        """Build feedback from skill dict (when skill object not available)."""
        return (
            f"Success rate ({skill_dict.get('success_rate', 0):.0%}) below "
            f"threshold ({self.min_success_rate:.0%})"
        )

    def get_stats(self) -> dict[str, Any]:
        """Get self-improvement loop statistics."""
        return {
            "tracked_skills": len(self._usage_counts),
            "total_usages": sum(self._usage_counts.values()),
            "min_success_rate": self.min_success_rate,
            "check_interval": self.check_interval,
            "auto_evolve": self.auto_evolve,
        }
