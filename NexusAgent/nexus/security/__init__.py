"""
NEXUS Security Module — Comprehensive security layer.

Components:
  - sandbox: Sandboxed code execution (local + Docker)
  - audit: Immutable audit trail for all actions
  - guardrails: Input/output safety validation
  - rate_limiter: Token bucket rate limiting
  - secrets: Secure secrets management
"""

from nexus.security.sandbox import LocalSandbox, DockerSandbox, SandboxResult, get_sandbox
from nexus.security.audit import AuditLogger, AuditCategory, AuditLevel
from nexus.security.guardrails import (
    GuardrailManager,
    PromptInjectionGuardrail,
    PIIGuardrail,
    ContentModerationGuardrail,
    OutputValidationGuardrail,
    GuardrailResult,
    GuardrailAction,
)
from nexus.security.rate_limiter import RateLimiter, RateLimitExceededError
from nexus.security.secrets import SecretsManager

__all__ = [
    "LocalSandbox",
    "DockerSandbox",
    "SandboxResult",
    "get_sandbox",
    "AuditLogger",
    "AuditCategory",
    "AuditLevel",
    "GuardrailManager",
    "PromptInjectionGuardrail",
    "PIIGuardrail",
    "ContentModerationGuardrail",
    "OutputValidationGuardrail",
    "GuardrailResult",
    "GuardrailAction",
    "RateLimiter",
    "RateLimitExceededError",
    "SecretsManager",
]
