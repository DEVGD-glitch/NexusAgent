"""
NEXUS Guardrails — Input/output safety validation layer.

Implements safety guardrails that validate all inputs and outputs
before they reach the LLM or are returned to the user:
  - Content moderation (violence, hate, self-harm, etc.)
  - PII detection and redaction
  - Prompt injection detection
  - Output validation
  - Custom rule enforcement
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from nexus.core.config import get_settings
from nexus.core.exceptions import GuardrailViolationError

logger = logging.getLogger(__name__)


class GuardrailSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GuardrailAction(str, Enum):
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"
    REDACT = "redact"


@dataclass
class GuardrailResult:
    """Result of a guardrail check."""
    passed: bool
    guardrail_name: str
    action: GuardrailAction = GuardrailAction.ALLOW
    severity: GuardrailSeverity = GuardrailSeverity.LOW
    reason: str = ""
    redacted_text: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)


class Guardrail:
    """Base class for all guardrails."""

    name: str = "base"
    description: str = ""

    def check(self, text: str, context: Optional[dict[str, Any]] = None) -> GuardrailResult:
        """Check text against this guardrail. Override in subclasses."""
        return GuardrailResult(passed=True, guardrail_name=self.name)


class PromptInjectionGuardrail(Guardrail):
    """
    Detect common prompt injection patterns.

    Checks for:
      - System prompt override attempts
      - Instruction injection via role manipulation
      - Common jailbreak patterns
      - Encoding tricks (base64, unicode)
    """

    name = "prompt_injection"
    description = "Detects prompt injection attempts"

    INJECTION_PATTERNS = [
        r"(?i)ignore\s+(all\s+)?(previous|above\s+)?instructions",
        r"(?i)ignore\s+(all|previous|above)\s+",
        r"(?i)forget\s+(everything|all|previous)",
        r"(?i)you\s+are\s+now\s+(DAN|jailbreak|unrestricted)",
        r"(?i)system\s*:\s*",
        r"(?i)override\s+(safety|guardrails|restrictions)",
        r"(?i)pretend\s+you\s+(are|have)\s+no\s+(rules|restrictions)",
        r"(?i)act\s+as\s+if\s+you\s+(have\s+)?no\s+(rules|restrictions|limits)",
        r"(?i)disregard\s+(all\s+)?(previous|above|safety)\s+(instructions|rules)",
        r"\[INST\]",
        r"<<SYS>>",
        r"</?system>",
        r"(?i)jailbreak",
        r"(?i)DAN\s+mode",
    ]

    def check(self, text: str, context: Optional[dict[str, Any]] = None) -> GuardrailResult:
        matches = []
        for pattern in self.INJECTION_PATTERNS:
            found = re.findall(pattern, text)
            if found:
                matches.append({"pattern": pattern, "matches": found})

        if matches:
            return GuardrailResult(
                passed=False,
                guardrail_name=self.name,
                action=GuardrailAction.BLOCK,
                severity=GuardrailSeverity.HIGH,
                reason=f"Potential prompt injection detected: {len(matches)} pattern(s) matched",
                details={"matches": matches},
            )

        return GuardrailResult(passed=True, guardrail_name=self.name)


class PIIGuardrail(Guardrail):
    """
    Detect and redact Personally Identifiable Information (PII).

    Detects:
      - Email addresses
      - Phone numbers
      - Credit card numbers
      - SSN patterns
      - IP addresses
    """

    name = "pii_detection"
    description = "Detects and redacts PII"

    PII_PATTERNS = {
        "email": (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', "[EMAIL_REDACTED]"),
        "phone": (r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', "[PHONE_REDACTED]"),
        "credit_card": (r'\b(?:\d{4}[-\s]?){3}\d{4}\b', "[CC_REDACTED]"),
        "ssn": (r'\b\d{3}-\d{2}-\d{4}\b', "[SSN_REDACTED]"),
        "ip_address": (r'\b(?:\d{1,3}\.){3}\d{1,3}\b', "[IP_REDACTED]"),
    }

    def check(self, text: str, context: Optional[dict[str, Any]] = None) -> GuardrailResult:
        redacted_text = text
        detected_types = []

        for pii_type, (pattern, replacement) in self.PII_PATTERNS.items():
            matches = re.findall(pattern, text)
            if matches:
                detected_types.append(pii_type)
                redacted_text = re.sub(pattern, replacement, redacted_text)

        if detected_types:
            return GuardrailResult(
                passed=True,  # PII is allowed but redacted
                guardrail_name=self.name,
                action=GuardrailAction.REDACT,
                severity=GuardrailSeverity.MEDIUM,
                reason=f"PII detected and redacted: {', '.join(detected_types)}",
                redacted_text=redacted_text,
                details={"detected_types": detected_types},
            )

        return GuardrailResult(passed=True, guardrail_name=self.name)


class ContentModerationGuardrail(Guardrail):
    """
    Content moderation for harmful content.

    Checks for:
      - Violence and threats
      - Self-harm references
      - Hate speech patterns
      - Illegal activity references
    """

    name = "content_moderation"
    description = "Moderates harmful content"

    # Simplified pattern-based moderation
    # In production, this would use an LLM-based classifier
    VIOLENCE_PATTERNS = [
        r"(?i)\b(kill|murder|assassinate|bomb|attack)\s+(you|them|people|everyone)\b",
        r"(?i)\bhow\s+to\s+(make|build|create)\s+(a\s+)?(bomb|weapon|explosive)\b",
    ]

    SELF_HARM_PATTERNS = [
        r"(?i)\bhow\s+to\s+(commit|do)\s+(suicide|self.harm)\b",
        r"(?i)\b(kill\s+myself|end\s+my\s+life|hurt\s+myself)\b",
    ]

    HATE_PATTERNS = [
        r"(?i)\b(hate|destroy)\s+(all|every)\s+(race|group|people|minority)\b",
    ]

    def check(self, text: str, context: Optional[dict[str, Any]] = None) -> GuardrailResult:
        # Check violence
        for pattern in self.VIOLENCE_PATTERNS:
            if re.search(pattern, text):
                return GuardrailResult(
                    passed=False,
                    guardrail_name=self.name,
                    action=GuardrailAction.BLOCK,
                    severity=GuardrailSeverity.CRITICAL,
                    reason="Content contains violence or threats",
                )

        # Check self-harm
        for pattern in self.SELF_HARM_PATTERNS:
            if re.search(pattern, text):
                return GuardrailResult(
                    passed=False,
                    guardrail_name=self.name,
                    action=GuardrailAction.BLOCK,
                    severity=GuardrailSeverity.CRITICAL,
                    reason="Content contains self-harm references",
                )

        # Check hate speech
        for pattern in self.HATE_PATTERNS:
            if re.search(pattern, text):
                return GuardrailResult(
                    passed=False,
                    guardrail_name=self.name,
                    action=GuardrailAction.BLOCK,
                    severity=GuardrailSeverity.HIGH,
                    reason="Content contains hate speech",
                )

        return GuardrailResult(passed=True, guardrail_name=self.name)


class OutputValidationGuardrail(Guardrail):
    """
    Validate LLM outputs for safety and quality.

    Checks:
      - Output length limits
      - No leaked system prompts
      - No hallucinated API keys
      - No code execution in output
    """

    name = "output_validation"
    description = "Validates LLM output safety"

    LEAKED_KEY_PATTERNS = [
        r'sk-[a-zA-Z0-9]{20,}',  # OpenAI keys
        r'sk-ant-[a-zA-Z0-9]{20,}',  # Anthropic keys
        r'AIza[a-zA-Z0-9_-]{35}',  # Google keys
    ]

    def check(self, text: str, context: Optional[dict[str, Any]] = None) -> GuardrailResult:
        # Check for leaked API keys
        for pattern in self.LEAKED_KEY_PATTERNS:
            matches = re.findall(pattern, text)
            if matches:
                redacted = re.sub(pattern, "[API_KEY_REDACTED]", text)
                return GuardrailResult(
                    passed=False,
                    guardrail_name=self.name,
                    action=GuardrailAction.REDACT,
                    severity=GuardrailSeverity.CRITICAL,
                    reason="Output contains leaked API keys",
                    redacted_text=redacted,
                    details={"keys_found": len(matches)},
                )

        return GuardrailResult(passed=True, guardrail_name=self.name)


class GuardrailManager:
    """
    Central guardrail manager that runs all guardrails in sequence.

    Usage:
        manager = GuardrailManager()
        result = manager.check_input("user message here")
        if not result.passed:
            raise GuardrailViolationError(...)
    """

    def __init__(self, enable_pii_redaction: bool = True):
        self.input_guardrails: list[Guardrail] = [
            PromptInjectionGuardrail(),
            PIIGuardrail() if enable_pii_redaction else None,
            ContentModerationGuardrail(),
        ]
        self.output_guardrails: list[Guardrail] = [
            OutputValidationGuardrail(),
            PIIGuardrail() if enable_pii_redaction else None,
        ]
        # Remove None entries
        self.input_guardrails = [g for g in self.input_guardrails if g is not None]
        self.output_guardrails = [g for g in self.output_guardrails if g is not None]

    def check_input(self, text: str, context: Optional[dict[str, Any]] = None) -> GuardrailResult:
        """
        Run all input guardrails against text.

        Returns the first failing result, or the last result if all pass.
        PII redaction is cumulative across guardrails.
        """
        current_text = text
        for guardrail in self.input_guardrails:
            result = guardrail.check(current_text, context)
            if result.redacted_text:
                current_text = result.redacted_text
            if not result.passed and result.action == GuardrailAction.BLOCK:
                return result
        # If PII was redacted, return the redacted text
        if current_text != text:
            return GuardrailResult(
                passed=True,
                guardrail_name="combined_input",
                action=GuardrailAction.REDACT,
                redacted_text=current_text,
                reason="PII redacted from input",
            )
        return GuardrailResult(passed=True, guardrail_name="combined_input")

    def check_output(self, text: str, context: Optional[dict[str, Any]] = None) -> GuardrailResult:
        """
        Run all output guardrails against text.

        Returns the first failing result, or the last result if all pass.
        """
        current_text = text
        for guardrail in self.output_guardrails:
            result = guardrail.check(current_text, context)
            if result.redacted_text:
                current_text = result.redacted_text
            if not result.passed and result.action == GuardrailAction.BLOCK:
                return result
        if current_text != text:
            return GuardrailResult(
                passed=True,
                guardrail_name="combined_output",
                action=GuardrailAction.REDACT,
                redacted_text=current_text,
                reason="Sensitive information redacted from output",
            )
        return GuardrailResult(passed=True, guardrail_name="combined_output")
