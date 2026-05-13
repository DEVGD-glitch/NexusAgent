"""
NEXUS Code Engine — Code generation, review, and refactoring engine.

Supports:
  - Multi-language code generation (Python, JS/TS, Rust, Go, SQL)
  - LLM-powered code generation with provider fallback
  - Automated code review (linting, formatting, security)
  - Code refactoring suggestions
  - Test generation
  - CodeAct pattern (actions expressed as executable Python code)
  - Integration with CodeExecutor for safe code execution
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from nexus.core.config import get_settings
from nexus.dev.code_executor import CodeExecutor, ExecutionResult

logger = logging.getLogger(__name__)


class Language(str, Enum):
    """Supported programming languages."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    GO = "go"
    SQL = "sql"
    BASH = "bash"


class ReviewCategory(str, Enum):
    """Code review categories."""
    CORRECTNESS = "correctness"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    MAINTAINABILITY = "maintainability"
    TESTING = "testing"


@dataclass
class CodeReviewFinding:
    """A single finding from a code review."""
    category: ReviewCategory
    severity: str  # "critical", "warning", "info"
    message: str
    line: Optional[int] = None
    suggestion: Optional[str] = None


@dataclass
class CodeReviewResult:
    """Result of a code review."""
    findings: list[CodeReviewFinding] = field(default_factory=list)
    overall_score: float = 0.0  # 0-10
    summary: str = ""
    language: str = "python"
    reviewed_at: float = 0.0

    @property
    def has_critical(self) -> bool:
        return any(f.severity == "critical" for f in self.findings)

    @property
    def passed(self) -> bool:
        return not self.has_critical and self.overall_score >= 5.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "summary": self.summary,
            "passed": self.passed,
            "findings": [
                {
                    "category": f.category.value,
                    "severity": f.severity,
                    "message": f.message,
                    "line": f.line,
                    "suggestion": f.suggestion,
                }
                for f in self.findings
            ],
        }


@dataclass
class GenerationResult:
    """Result of a code generation operation."""
    code: str
    language: str
    description: str = ""
    generation_time_ms: float = 0.0
    provider_used: str = ""
    model_used: str = ""


class CodeEngine:
    """
    Code generation, review, and refactoring engine.

    Provides multi-language code generation with LLM integration,
    automated code review, refactoring suggestions, and test generation.
    Supports the CodeAct pattern where actions are expressed as
    executable Python code.

    Usage:
        engine = CodeEngine()
        result = await engine.generate("Sort a list using merge sort", language="python")
        review = await engine.review(result.code, language="python")
    """

    # Language-specific security patterns to flag in review
    SECURITY_PATTERNS: dict[str, list[tuple[str, str]]] = {
        "python": [
            (r"eval\s*\(", "Use of eval() is a security risk — prefer ast.literal_eval()"),
            (r"exec\s*\(", "Use of exec() is a security risk"),
            (r"__import__\s*\(", "Dynamic imports can be dangerous"),
            (r"subprocess\.call\s*\(.*shell\s*=\s*True", "shell=True in subprocess is a security risk"),
            (r"os\.system\s*\(", "os.system() is prone to injection — use subprocess"),
            (r"pickle\.load", "pickle.load() on untrusted data is a security risk"),
            (r"yaml\.load\s*\([^)]*\)(?!.*Loader)", "yaml.load() without Loader is unsafe — use yaml.safe_load()"),
        ],
        "javascript": [
            (r"eval\s*\(", "Use of eval() is a security risk"),
            (r"innerHTML\s*=", "Direct innerHTML assignment is an XSS risk"),
            (r"document\.write\s*\(", "document.write() is an XSS risk"),
            (r"new Function\s*\(", "Dynamic function construction is a security risk"),
        ],
        "sql": [
            (r"f['\"].*SELECT.*{", "String formatting in SQL queries — use parameterized queries"),
            (r"\.format\s*\(.*SELECT", "String formatting in SQL queries — use parameterized queries"),
            (r"%s.*SELECT|SELECT.*%s", "String interpolation in SQL — use parameterized queries"),
        ],
    }

    # Language-specific style/linting patterns
    LINT_PATTERNS: dict[str, list[tuple[str, str]]] = {
        "python": [
            (r"^ *\t", "Use spaces instead of tabs for indentation"),
            (r"except\s*:", "Bare except catches all exceptions — be specific"),
            (r"==\s*True|==\s*False", "Use 'if x:' instead of 'if x == True'"),
            (r"print\s*\(", "Print statement found — consider using logging"),
        ],
    }

    # CodeAct system prompt
    CODEACT_SYSTEM_PROMPT = (
        "You are a CodeAct agent. You express actions as executable Python code.\n"
        "Every action you take is a Python code snippet that will be executed in a sandbox.\n"
        "You can:\n"
        "- Read files: open('path').read()\n"
        "- Write files: open('path', 'w').write(content)\n"
        "- Run shell commands: subprocess.run(['cmd', 'arg'])\n"
        "- Import standard library modules\n"
        "- Define and call functions\n\n"
        "Rules:\n"
        "1. Always wrap code in ```python blocks\n"
        "2. Use only standard library modules unless specified\n"
        "3. Handle errors gracefully\n"
        "4. Print results for the user to see\n"
        "5. Be concise — write minimal code to accomplish the task\n"
    )

    def __init__(self, executor: Optional[CodeExecutor] = None):
        """
        Initialize the CodeEngine.

        Args:
            executor: Optional CodeExecutor instance. If not provided,
                      a default one is created.
        """
        self.settings = get_settings()
        self.executor = executor or CodeExecutor()
        self._router = None

    def _get_router(self):
        """Lazily initialize the LLM router."""
        if self._router is None:
            from nexus.llm.router import LLMRouter
            self._router = LLMRouter()
        return self._router

    async def generate(
        self,
        prompt: str,
        language: str = "python",
        context: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> GenerationResult:
        """
        Generate code from a natural language prompt.

        Args:
            prompt: Natural language description of the code to generate.
            language: Target programming language.
            context: Optional additional context or constraints.
            max_tokens: Maximum tokens for the generated code.
            temperature: Sampling temperature (lower = more deterministic).

        Returns:
            GenerationResult with the generated code and metadata.
        """
        start = time.monotonic()
        lang = Language(language)

        system_prompt = self._build_generation_prompt(lang)
        user_content = prompt
        if context:
            user_content = f"{prompt}\n\nAdditional context:\n{context}"

        router = self._get_router()
        from nexus.llm.router import TaskComplexity

        response = await router.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            task_complexity=TaskComplexity.MEDIUM,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Extract code from the response
        code = self._extract_code(response.content, language)

        return GenerationResult(
            code=code,
            language=language,
            description=prompt,
            generation_time_ms=(time.monotonic() - start) * 1000,
            provider_used=response.provider.value,
            model_used=response.model,
        )

    async def review(
        self,
        code: str,
        language: str = "python",
        focus: Optional[list[str]] = None,
    ) -> CodeReviewResult:
        """
        Perform an automated code review.

        Combines static analysis (pattern-based) with LLM-powered
        semantic review for comprehensive feedback.

        Args:
            code: The code to review.
            language: Programming language of the code.
            focus: Optional list of review categories to focus on.

        Returns:
            CodeReviewResult with findings and overall score.
        """
        start_time = time.monotonic()
        findings: list[CodeReviewFinding] = []

        # Phase 1: Static analysis (pattern-based)
        static_findings = self._static_review(code, language)
        findings.extend(static_findings)

        # Phase 2: LLM-powered semantic review
        try:
            llm_findings = await self._llm_review(code, language, focus)
            findings.extend(llm_findings)
        except Exception as e:
            logger.warning("LLM review failed, returning static results only: %s", e)

        # Calculate overall score
        score = self._calculate_review_score(findings)

        # Generate summary
        summary = self._generate_review_summary(findings, score)

        return CodeReviewResult(
            findings=findings,
            overall_score=score,
            summary=summary,
            language=language,
            reviewed_at=time.monotonic() - start_time,
        )

    async def refactor(
        self,
        code: str,
        language: str = "python",
        goal: str = "improve readability and maintainability",
    ) -> GenerationResult:
        """
        Suggest refactored code.

        Args:
            code: The code to refactor.
            language: Programming language.
            goal: Refactoring goal description.

        Returns:
            GenerationResult with the refactored code.
        """
        start = time.monotonic()

        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a code refactoring assistant for {language}. "
                    "Refactor the provided code to improve its quality while preserving "
                    "its behavior. Focus on: readability, maintainability, performance, "
                    "and adherence to best practices. Return ONLY the refactored code, "
                    "no explanations."
                ),
            },
            {
                "role": "user",
                "content": f"Refactoring goal: {goal}\n\nCode to refactor:\n```\n{code}\n```",
            },
        ]

        router = self._get_router()
        from nexus.llm.router import TaskComplexity

        response = await router.complete(
            messages=messages,
            task_complexity=TaskComplexity.MEDIUM,
            temperature=0.2,
            max_tokens=4096,
        )

        refactored = self._extract_code(response.content, language)

        return GenerationResult(
            code=refactored,
            language=language,
            description=f"Refactored: {goal}",
            generation_time_ms=(time.monotonic() - start) * 1000,
            provider_used=response.provider.value,
            model_used=response.model,
        )

    async def generate_tests(
        self,
        code: str,
        language: str = "python",
        framework: Optional[str] = None,
    ) -> GenerationResult:
        """
        Generate tests for the given code.

        Args:
            code: The code to generate tests for.
            language: Programming language.
            framework: Test framework to use (e.g., "pytest", "unittest", "jest").
                       Auto-detected if not specified.

        Returns:
            GenerationResult with the generated test code.
        """
        start = time.monotonic()

        # Auto-detect framework
        if framework is None:
            framework_map = {
                "python": "pytest",
                "javascript": "jest",
                "typescript": "jest",
                "rust": "builtin (#[test])",
                "go": "testing",
            }
            framework = framework_map.get(language, "generic")

        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a test generation assistant. Generate comprehensive tests "
                    f"for the given {language} code using the {framework} framework.\n\n"
                    "Guidelines:\n"
                    "- Test all public functions/methods\n"
                    "- Include edge cases and boundary conditions\n"
                    "- Test error handling paths\n"
                    "- Use descriptive test names\n"
                    "- Include setup/teardown if needed\n"
                    "Return ONLY the test code, no explanations."
                ),
            },
            {
                "role": "user",
                "content": f"Code to test:\n```\n{code}\n```",
            },
        ]

        router = self._get_router()
        from nexus.llm.router import TaskComplexity

        response = await router.complete(
            messages=messages,
            task_complexity=TaskComplexity.MEDIUM,
            temperature=0.3,
            max_tokens=4096,
        )

        test_code = self._extract_code(response.content, language)

        return GenerationResult(
            code=test_code,
            language=language,
            description=f"Tests for code (framework: {framework})",
            generation_time_ms=(time.monotonic() - start) * 1000,
            provider_used=response.provider.value,
            model_used=response.model,
        )

    async def codeact(
        self,
        task: str,
        context: Optional[dict[str, Any]] = None,
        max_iterations: int = 5,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """
        Execute a task using the CodeAct pattern.

        The CodeAct pattern expresses actions as executable Python code.
        The LLM generates code, which is executed in the sandbox,
        and the output is fed back for the next iteration.

        Args:
            task: The task description.
            context: Optional context dictionary.
            max_iterations: Maximum number of code-execute cycles.
            timeout: Execution timeout per iteration in seconds.

        Returns:
            Dict with the final result, code history, and execution logs.
        """
        messages = [
            {"role": "system", "content": self.CODEACT_SYSTEM_PROMPT},
            {"role": "user", "content": task},
        ]

        if context:
            context_str = json.dumps(context, indent=2, default=str)
            messages.append({
                "role": "user",
                "content": f"Context data:\n{context_str}",
            })

        code_history: list[str] = []
        execution_logs: list[dict[str, Any]] = []

        router = self._get_router()
        from nexus.llm.router import TaskComplexity

        for iteration in range(max_iterations):
            # Generate code
            response = await router.complete(
                messages=messages,
                task_complexity=TaskComplexity.MEDIUM,
                temperature=0.2,
                max_tokens=4096,
            )

            generated_code = self._extract_code(response.content, "python")

            if not generated_code.strip():
                messages.append({
                    "role": "assistant",
                    "content": response.content,
                })
                continue

            code_history.append(generated_code)

            # Execute the code
            result: ExecutionResult = await self.executor.execute(
                code=generated_code,
                language="python",
                timeout=timeout,
            )

            execution_logs.append({
                "iteration": iteration + 1,
                "code": generated_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.exit_code,
                "timed_out": result.timed_out,
            })

            # Feed execution results back
            exec_feedback = (
                f"Execution result (exit_code={result.exit_code}):\n"
                f"--- stdout ---\n{result.stdout}\n"
            )
            if result.stderr:
                exec_feedback += f"--- stderr ---\n{result.stderr}\n"
            if result.timed_out:
                exec_feedback += "--- TIMEOUT ---\n"

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": exec_feedback})

            # Check if task appears complete
            if result.exit_code == 0 and not result.timed_out:
                # If the LLM signals completion, break
                if "TASK_COMPLETE" in result.stdout or "done" in result.stdout.lower():
                    break

        return {
            "task": task,
            "iterations": len(execution_logs),
            "code_history": code_history,
            "execution_logs": execution_logs,
            "final_stdout": execution_logs[-1]["stdout"] if execution_logs else "",
            "final_exit_code": execution_logs[-1]["exit_code"] if execution_logs else -1,
        }

    async def execute_code(
        self,
        code: str,
        language: str = "python",
        timeout: int = 30,
        env_vars: Optional[dict[str, str]] = None,
    ) -> ExecutionResult:
        """
        Execute code using the integrated CodeExecutor.

        Args:
            code: Code to execute.
            language: Programming language.
            timeout: Execution timeout in seconds.
            env_vars: Additional environment variables.

        Returns:
            ExecutionResult with output and metadata.
        """
        return await self.executor.execute(
            code=code,
            language=language,
            timeout=timeout,
            env_vars=env_vars,
        )

    # ── Private Helpers ──────────────────────────────────────────────

    def _build_generation_prompt(self, language: Language) -> str:
        """Build the system prompt for code generation."""
        lang_specific = {
            Language.PYTHON: (
                "Write Python 3.11+ code with type hints, docstrings, and proper error handling. "
                "Follow PEP 8 style. Use dataclasses or Pydantic models where appropriate."
            ),
            Language.JAVASCRIPT: (
                "Write modern JavaScript (ES2022+) code with JSDoc comments. "
                "Use const/let, arrow functions, and async/await."
            ),
            Language.TYPESCRIPT: (
                "Write TypeScript 5.x code with full type annotations. "
                "Use interfaces, type guards, and generic types where appropriate."
            ),
            Language.RUST: (
                "Write idiomatic Rust code with proper error handling (Result/Option). "
                "Include derive macros and documentation comments."
            ),
            Language.GO: (
                "Write idiomatic Go code with proper error handling. "
                "Follow Go naming conventions and include godoc comments."
            ),
            Language.SQL: (
                "Write standard SQL (PostgreSQL-compatible). "
                "Include proper indexing hints and use CTEs for readability."
            ),
            Language.BASH: (
                "Write portable bash scripts with proper error handling (set -euo pipefail). "
                "Include help text and argument parsing."
            ),
        }

        return (
            f"You are an expert {language.value} developer. "
            f"{lang_specific.get(language, 'Write clean, well-documented code.')}\n\n"
            "Rules:\n"
            "1. Return ONLY code inside a ```code block\n"
            "2. Include necessary imports/dependencies\n"
            "3. Add error handling for all fallible operations\n"
            "4. Write self-documenting code with clear names\n"
            "5. Include docstrings/comments for complex logic\n"
        )

    def _extract_code(self, text: str, language: str) -> str:
        """Extract code from an LLM response, handling markdown code blocks."""
        # Try to find a fenced code block
        # Match ```lang or just ```
        lang_patterns = [language, ""]
        for lang in lang_patterns:
            pattern = rf"```{lang}\s*\n(.*?)```"
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(1).strip()

        # Try generic code block
        pattern = r"```\w*\s*\n(.*?)```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # If no code blocks found, return the text as-is if it looks like code
        stripped = text.strip()
        if any(keyword in stripped for keyword in ["def ", "function ", "fn ", "func ", "SELECT ", "class "]):
            return stripped

        return stripped

    def _static_review(self, code: str, language: str) -> list[CodeReviewFinding]:
        """Perform static analysis review using pattern matching."""
        findings: list[CodeReviewFinding] = []

        # Security patterns
        security_patterns = self.SECURITY_PATTERNS.get(language, [])
        for pattern, message in security_patterns:
            for match in re.finditer(pattern, code, re.IGNORECASE | re.MULTILINE):
                line_num = code[:match.start()].count("\n") + 1
                findings.append(CodeReviewFinding(
                    category=ReviewCategory.SECURITY,
                    severity="critical",
                    message=message,
                    line=line_num,
                ))

        # Lint patterns
        lint_patterns = self.LINT_PATTERNS.get(language, [])
        for pattern, message in lint_patterns:
            for match in re.finditer(pattern, code, re.MULTILINE):
                line_num = code[:match.start()].count("\n") + 1
                findings.append(CodeReviewFinding(
                    category=ReviewCategory.STYLE,
                    severity="warning",
                    message=message,
                    line=line_num,
                ))

        # Generic checks
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.rstrip()
            if len(stripped) > 120:
                findings.append(CodeReviewFinding(
                    category=ReviewCategory.STYLE,
                    severity="info",
                    message=f"Line exceeds 120 characters ({len(stripped)})",
                    line=i,
                ))

        # Check for TODO/FIXME/HACK
        for i, line in enumerate(lines, 1):
            if re.search(r"\b(TODO|FIXME|HACK|XXX)\b", line, re.IGNORECASE):
                findings.append(CodeReviewFinding(
                    category=ReviewCategory.MAINTAINABILITY,
                    severity="info",
                    message=f"Code comment marker found: {line.strip()}",
                    line=i,
                ))

        return findings

    async def _llm_review(
        self,
        code: str,
        language: str,
        focus: Optional[list[str]] = None,
    ) -> list[CodeReviewFinding]:
        """Perform LLM-powered semantic code review."""
        focus_str = ""
        if focus:
            focus_str = f"Focus especially on: {', '.join(focus)}.\n"

        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a code reviewer for {language} code. "
                    "Analyze the code and return a JSON array of findings.\n\n"
                    "Each finding must be a JSON object with:\n"
                    '- "category": one of "correctness", "security", "performance", '
                    '"style", "maintainability", "testing"\n'
                    '- "severity": one of "critical", "warning", "info"\n'
                    '- "message": description of the issue\n'
                    '- "line": line number (if applicable)\n'
                    '- "suggestion": suggested fix (if applicable)\n\n'
                    f"{focus_str}"
                    "Return ONLY the JSON array, no other text."
                ),
            },
            {
                "role": "user",
                "content": f"Review this {language} code:\n```\n{code}\n```",
            },
        ]

        router = self._get_router()
        from nexus.llm.router import TaskComplexity

        response = await router.complete(
            messages=messages,
            task_complexity=TaskComplexity.MEDIUM,
            temperature=0.1,
            max_tokens=2048,
        )

        # Parse the JSON response
        findings: list[CodeReviewFinding] = []
        try:
            content = response.content.strip()
            # Try to extract JSON from the response
            json_match = re.search(r"\[.*\]", content, re.DOTALL)
            if json_match:
                items = json.loads(json_match.group())
                for item in items:
                    try:
                        findings.append(CodeReviewFinding(
                            category=ReviewCategory(item.get("category", "correctness")),
                            severity=item.get("severity", "info"),
                            message=item.get("message", ""),
                            line=item.get("line"),
                            suggestion=item.get("suggestion"),
                        ))
                    except (ValueError, KeyError):
                        continue
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning("Failed to parse LLM review response: %s", e)

        return findings

    def _calculate_review_score(self, findings: list[CodeReviewFinding]) -> float:
        """Calculate an overall review score (0-10) based on findings."""
        score = 10.0
        severity_deduction = {
            "critical": 3.0,
            "warning": 1.0,
            "info": 0.2,
        }
        for finding in findings:
            deduction = severity_deduction.get(finding.severity, 0.0)
            score -= deduction
        return max(0.0, min(10.0, score))

    def _generate_review_summary(self, findings: list[CodeReviewFinding], score: float) -> str:
        """Generate a human-readable review summary."""
        critical = sum(1 for f in findings if f.severity == "critical")
        warnings = sum(1 for f in findings if f.severity == "warning")
        info = sum(1 for f in findings if f.severity == "info")

        parts = [f"Score: {score:.1f}/10"]
        if critical:
            parts.append(f"{critical} critical issue(s)")
        if warnings:
            parts.append(f"{warnings} warning(s)")
        if info:
            parts.append(f"{info} info note(s)")
        if not findings:
            parts.append("No issues found — code looks good!")

        return " | ".join(parts)
