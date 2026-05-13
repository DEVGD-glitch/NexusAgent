"""
NEXUS Developer Agent — Specialized in software development and code.

The Developer excels at:
  - Code generation in multiple languages
  - Debugging and error resolution
  - Code review and optimization
  - Test writing
  - Git operations and project management
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from nexus.agents.base import BaseAgent, AgentContext, AgentCapability
from nexus.core.registry import AgentCapability as Cap

logger = logging.getLogger(__name__)


class DeveloperAgent(BaseAgent):
    """
    Software Development Agent for writing, debugging, and reviewing code.

    Uses a systematic development methodology:
      1. Understand requirements and constraints
      2. Design solution architecture
      3. Implement code with best practices
      4. Test and verify
      5. Refine and optimize

    Tools: code_execute, file_read, file_write, git_integration,
           code_review, debugging, testing
    """

    def __init__(self):
        super().__init__(
            agent_type="developer",
            description="Software development agent for writing and debugging code",
            skills=[
                "code_generation", "debugging", "code_review", "testing",
                "refactoring", "documentation", "git_integration",
            ],
        )

    @property
    def system_prompt(self) -> str:
        return (
            "You are NEXUS Developer, a specialized software development agent. Your role is to:\n"
            "1. Understand software requirements and technical constraints\n"
            "2. Design clean, maintainable solutions\n"
            "3. Write production-quality code following best practices\n"
            "4. Debug and fix errors systematically\n"
            "5. Write comprehensive tests\n"
            "6. Review code for quality, security, and performance\n\n"
            "Development methodology:\n"
            "- Always understand the problem before coding\n"
            "- Write self-documenting code with clear names\n"
            "- Follow SOLID principles and design patterns where appropriate\n"
            "- Include error handling and input validation\n"
            "- Write tests for critical paths\n"
            "- Consider edge cases and failure modes\n\n"
            "Use tools: code_execute for running code, file_read/file_write for file operations, "
            "git_integration for version control, memory_recall for accessing past solutions."
        )

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [Cap.CODING, Cap.FILE_OPS, Cap.REASONING]

    async def plan(self, context: AgentContext) -> list[dict[str, Any]]:
        """
        Create a development plan.

        Steps:
        1. Analyze requirements
        2. Design solution
        3. Implement code
        4. Execute and test
        5. Review and refine
        """
        task = context.task

        # Analyze the task to determine the development approach
        plan = [
            {
                "action": "analyze_requirements",
                "params": {"task": task},
                "description": "Analyze requirements and constraints",
            },
            {
                "action": "design_solution",
                "params": {},
                "description": "Design solution architecture and approach",
            },
            {
                "action": "implement_code",
                "params": {"task": task},
                "description": "Write the implementation code",
            },
            {
                "action": "execute_and_test",
                "params": {},
                "description": "Execute code and run tests",
            },
            {
                "action": "review_and_refine",
                "params": {},
                "description": "Review code quality and optimize if needed",
            },
        ]

        # Check if this is a debugging task
        task_lower = task.lower()
        if any(kw in task_lower for kw in ["debug", "fix", "error", "bug", "broken", "crash"]):
            plan = [
                {
                    "action": "analyze_error",
                    "params": {"task": task},
                    "description": "Analyze the error or bug report",
                },
                {
                    "action": "locate_issue",
                    "params": {},
                    "description": "Locate the root cause in the codebase",
                },
                {
                    "action": "implement_fix",
                    "params": {},
                    "description": "Implement the fix",
                },
                {
                    "action": "verify_fix",
                    "params": {},
                    "description": "Verify the fix resolves the issue",
                },
            ]

        # Check if this is a code review task
        elif any(kw in task_lower for kw in ["review", "audit", "check code", "improve"]):
            plan = [
                {
                    "action": "read_code",
                    "params": {},
                    "description": "Read and understand the code to review",
                },
                {
                    "action": "analyze_quality",
                    "params": {},
                    "description": "Analyze code quality, security, and performance",
                },
                {
                    "action": "provide_feedback",
                    "params": {},
                    "description": "Provide detailed review feedback with suggestions",
                },
            ]

        return plan

    async def execute_step(self, step: dict[str, Any], context: AgentContext) -> dict[str, Any]:
        """Execute a development step."""
        action = step.get("action", "")
        params = step.get("params", {})

        try:
            handler = getattr(self, f"_step_{action}", None)
            if handler:
                result = await handler(params, context)
            else:
                result = await self._generic_dev_step(action, params, context)

            return {"success": True, "result": result, "action": action}

        except Exception as e:
            logger.error("Developer step '%s' failed: %s", action, e)
            return {"success": False, "error": str(e), "action": action}

    async def _step_analyze_requirements(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Analyze software requirements."""
        task = params.get("task", context.task)

        messages = [
            {"role": "system", "content": (
                "Analyze the following software development request. Identify:\n"
                "1. Core functionality required\n"
                "2. Programming language and framework preferences\n"
                "3. Input/output specifications\n"
                "4. Constraints (performance, security, compatibility)\n"
                "5. Dependencies and integrations needed\n"
                "6. Testing requirements\n"
                "Return a structured requirements analysis."
            )},
            {"role": "user", "content": task},
        ]

        analysis = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("requirements", analysis)
        context.add_message("assistant", f"Requirements analysis complete: {analysis[:500]}")

        return {"analysis": analysis}

    async def _step_design_solution(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Design the solution architecture."""
        requirements = context.artifacts.get("requirements", context.task)

        messages = [
            {"role": "system", "content": (
                "Design a solution architecture for the following requirements. Include:\n"
                "1. High-level architecture (modules, classes, functions)\n"
                "2. Data flow and state management\n"
                "3. Error handling strategy\n"
                "4. Key design decisions and trade-offs\n"
                "Return a structured design document."
            )},
            {"role": "user", "content": str(requirements)[:3000]},
        ]

        design = await self._call_llm(messages, temperature=0.3)
        context.store_artifact("design", design)
        context.add_message("assistant", f"Solution design complete: {design[:500]}")

        return {"design": design}

    async def _step_implement_code(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Write the implementation code."""
        design = context.artifacts.get("design", context.task)
        requirements = context.artifacts.get("requirements", "")

        messages = [
            {"role": "system", "content": (
                "Write complete, production-quality code based on the design. "
                "Include:\n"
                "- Proper imports and dependencies\n"
                "- Type hints / annotations\n"
                "- Error handling and validation\n"
                "- Docstrings and comments for complex logic\n"
                "- A simple test or usage example\n"
                "Write the COMPLETE implementation, not pseudocode."
            )},
            {"role": "user", "content": (
                f"Requirements:\n{str(requirements)[:2000]}\n\n"
                f"Design:\n{str(design)[:2000]}"
            )},
        ]

        code = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("code", code)
        context.add_message("assistant", f"Code implementation written ({len(code)} chars)")

        return {"code": code, "tool_used": "code_generation"}

    async def _step_execute_and_test(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Execute the code and run tests."""
        code = context.artifacts.get("code", "")

        if not code:
            return {"error": "No code to execute"}

        # Try to execute the code in a sandbox
        result = await self._use_tool("code_execute", {
            "code": code,
            "language": "python",
            "timeout": 30,
        })

        context.store_artifact("execution_result", result)
        context.add_message("assistant", f"Code executed: {str(result)[:500]}")

        return {"execution": result, "tool_used": "code_execute"}

    async def _step_review_and_refine(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Review code quality and suggest refinements."""
        code = context.artifacts.get("code", "")
        execution = context.artifacts.get("execution_result", {})

        messages = [
            {"role": "system", "content": (
                "Review the following code and execution results. Check for:\n"
                "1. Correctness: Does it solve the stated problem?\n"
                "2. Code quality: Clean, readable, maintainable?\n"
                "3. Security: Any vulnerabilities or unsafe patterns?\n"
                "4. Performance: Any obvious bottlenecks?\n"
                "5. Edge cases: Are failure modes handled?\n"
                "Provide specific improvement suggestions or confirm the code is ready."
            )},
            {"role": "user", "content": (
                f"Code:\n{code[:3000]}\n\n"
                f"Execution result:\n{str(execution)[:1000]}"
            )},
        ]

        review = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("review", review)

        return {"review": review}

    async def _step_analyze_error(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Analyze a bug or error report."""
        task = params.get("task", context.task)

        messages = [
            {"role": "system", "content": (
                "Analyze the following error/bug report. Identify:\n"
                "1. The error type and symptoms\n"
                "2. Likely root causes (rank by probability)\n"
                "3. Affected components\n"
                "4. Reproduction steps if not provided\n"
                "Return a structured error analysis."
            )},
            {"role": "user", "content": task},
        ]

        analysis = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("error_analysis", analysis)

        return {"analysis": analysis}

    async def _step_locate_issue(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Locate the root cause of a bug in code."""
        error_analysis = context.artifacts.get("error_analysis", "")

        messages = [
            {"role": "system", "content": (
                "Based on the error analysis, identify the specific code locations "
                "that need to be modified. Provide:\n"
                "1. File and function/line references if known\n"
                "2. The problematic code pattern\n"
                "3. Why this code causes the error\n"
            )},
            {"role": "user", "content": str(error_analysis)[:3000]},
        ]

        location = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("issue_location", location)

        return {"location": location}

    async def _step_implement_fix(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Implement a fix for the identified bug."""
        error_analysis = context.artifacts.get("error_analysis", "")
        issue_location = context.artifacts.get("issue_location", "")

        messages = [
            {"role": "system", "content": (
                "Write a fix for the identified bug. The fix should:\n"
                "1. Address the root cause, not just symptoms\n"
                "2. Not introduce new bugs or break existing functionality\n"
                "3. Include a test that verifies the fix\n"
                "Provide the complete corrected code section."
            )},
            {"role": "user", "content": (
                f"Error analysis:\n{str(error_analysis)[:2000]}\n\n"
                f"Issue location:\n{str(issue_location)[:2000]}"
            )},
        ]

        fix = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("fix", fix)

        return {"fix": fix, "tool_used": "code_generation"}

    async def _step_verify_fix(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Verify that the fix resolves the issue."""
        fix = context.artifacts.get("fix", "")

        result = await self._use_tool("code_execute", {
            "code": fix,
            "language": "python",
            "timeout": 30,
        })

        context.store_artifact("fix_verification", result)

        return {"verification": result, "tool_used": "code_execute"}

    async def _step_read_code(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Read code for review."""
        # If a file path is mentioned, try to read it
        import re
        path_match = re.search(r'[\w/\-\.]+\.\w+', context.task)
        if path_match:
            result = await self._use_tool("file_read", {"path": path_match.group()})
            context.store_artifact("code_under_review", result)
            return result

        # Otherwise use the task description as the code
        context.store_artifact("code_under_review", context.task)
        return {"code": context.task}

    async def _step_analyze_quality(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Analyze code quality."""
        code = context.artifacts.get("code_under_review", "")

        messages = [
            {"role": "system", "content": (
                "Perform a comprehensive code review. Analyze:\n"
                "1. Correctness and logic errors\n"
                "2. Security vulnerabilities (injection, XSS, auth bypass)\n"
                "3. Performance issues and bottlenecks\n"
                "4. Code style and readability\n"
                "5. Error handling completeness\n"
                "6. Test coverage gaps\n"
                "Rate each category 1-5 and provide specific findings."
            )},
            {"role": "user", "content": str(code)[:4000]},
        ]

        review = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("quality_review", review)

        return {"review": review}

    async def _step_provide_feedback(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Provide review feedback with specific suggestions."""
        review = context.artifacts.get("quality_review", "")

        messages = [
            {"role": "system", "content": (
                "Based on the code review, provide actionable feedback with:\n"
                "1. Critical issues that must be fixed\n"
                "2. Recommended improvements\n"
                "3. Code snippets showing suggested changes\n"
                "4. Best practice recommendations\n"
                "Be specific and constructive."
            )},
            {"role": "user", "content": str(review)[:3000]},
        ]

        feedback = await self._call_llm(messages, temperature=0.3)
        context.store_artifact("feedback", feedback)

        return {"feedback": feedback}

    async def _generic_dev_step(self, action: str, params: dict, context: AgentContext) -> dict[str, Any]:
        """Handle generic development steps using LLM."""
        messages = [
            {"role": "system", "content": f"You are performing the development step: {action}"},
            {"role": "user", "content": f"Task: {context.task}\nStep: {action}\nParams: {params}"},
        ]
        result = await self._call_llm(messages, temperature=0.3)
        return {"result": result}

    async def reflect(self, context: AgentContext) -> dict[str, Any]:
        """
        Reflect on development progress.

        Evaluates whether the code is working correctly and if
        further refinement is needed.
        """
        # If review is done, we're done
        if "review" in context.artifacts or "feedback" in context.artifacts:
            return {
                "should_continue": False,
                "assessment": "Code review complete. Feedback provided.",
            }

        # If fix was verified
        if "fix_verification" in context.artifacts:
            verification = context.artifacts.get("fix_verification", {})
            has_errors = isinstance(verification, dict) and verification.get("error")
            if not has_errors:
                return {
                    "should_continue": False,
                    "assessment": "Fix verified successfully.",
                }

        # If code executed successfully
        execution = context.artifacts.get("execution_result", {})
        if execution and not (isinstance(execution, dict) and execution.get("error")):
            # Need to do review still
            if "review" not in context.artifacts:
                return {
                    "should_continue": True,
                    "assessment": "Code executed successfully. Moving to review.",
                }

        return {
            "should_continue": True,
            "assessment": "Development in progress. Continuing.",
        }
