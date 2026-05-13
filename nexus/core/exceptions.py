"""
NEXUS Hierarchical Exception System.

Every NEXUS module raises specific exceptions, never bare Exception.
Each exception carries structured context for debugging and audit.
"""

from __future__ import annotations

from typing import Any, Optional


class NexusError(Exception):
    """Base exception for all NEXUS errors."""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code or "NEXUS_ERROR"
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


# ── Configuration Errors ──────────────────────────────────────

class ConfigurationError(NexusError):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="CONFIG_ERROR", details=details)


class MissingAPIKeyError(ConfigurationError):
    """Raised when a required API key is not configured."""

    def __init__(self, provider: str, env_var: str):
        super().__init__(
            message=f"Missing API key for provider '{provider}'. Set {env_var} in .env",
            details={"provider": provider, "env_var": env_var},
        )
        self.code = "MISSING_API_KEY"


# ── Memory Errors ─────────────────────────────────────────────

class NexusMemoryError(NexusError):
    """Base exception for memory operations.

    Named NexusMemoryError to avoid masking Python's built-in MemoryError.
    """

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="MEMORY_ERROR", details=details)


class MemoryStoreError(NexusMemoryError):
    """Raised when storing to memory fails."""

    def __init__(self, namespace: str, reason: str):
        super().__init__(
            message=f"Failed to store in namespace '{namespace}': {reason}",
            details={"namespace": namespace, "reason": reason},
        )
        self.code = "MEMORY_STORE_ERROR"


class MemorySearchError(NexusMemoryError):
    """Raised when searching memory fails."""

    def __init__(self, namespace: str, reason: str):
        super().__init__(
            message=f"Failed to search namespace '{namespace}': {reason}",
            details={"namespace": namespace, "reason": reason},
        )
        self.code = "MEMORY_SEARCH_ERROR"


class MemoryNamespaceError(NexusMemoryError):
    """Raised when accessing an invalid namespace."""

    def __init__(self, namespace: str, valid_namespaces: list[str]):
        super().__init__(
            message=f"Invalid namespace '{namespace}'. Valid: {valid_namespaces}",
            details={"namespace": namespace, "valid_namespaces": valid_namespaces},
        )
        self.code = "MEMORY_NAMESPACE_ERROR"


# ── LLM Errors ────────────────────────────────────────────────

class LLMError(NexusError):
    """Base exception for LLM operations."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="LLM_ERROR", details=details)


class LLMProviderError(LLMError):
    """Raised when a specific LLM provider fails."""

    def __init__(self, provider: str, reason: str, model: Optional[str] = None):
        super().__init__(
            message=f"Provider '{provider}' failed: {reason}",
            details={"provider": provider, "reason": reason, "model": model},
        )
        self.code = "LLM_PROVIDER_ERROR"


class LLMRateLimitError(LLMError):
    """Raised when LLM provider rate limit is hit."""

    def __init__(self, provider: str, retry_after: Optional[int] = None):
        super().__init__(
            message=f"Rate limit hit for provider '{provider}'",
            details={"provider": provider, "retry_after": retry_after},
        )
        self.code = "LLM_RATE_LIMIT"


class LLMAllProvidersFailedError(LLMError):
    """Raised when all LLM providers in fallback chain fail."""

    def __init__(self, providers_tried: list[str], errors: list[str]):
        super().__init__(
            message=f"All LLM providers failed: {providers_tried}",
            details={"providers_tried": providers_tried, "errors": errors},
        )
        self.code = "LLM_ALL_PROVIDERS_FAILED"


# ── Orchestrator Errors ───────────────────────────────────────

class OrchestratorError(NexusError):
    """Base exception for orchestrator operations."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="ORCHESTRATOR_ERROR", details=details)


class MaxIterationsError(OrchestratorError):
    """Raised when the orchestrator exceeds maximum iterations."""

    def __init__(self, max_iterations: int, task: str):
        super().__init__(
            message=f"Exceeded max iterations ({max_iterations}) for task: {task[:100]}",
            details={"max_iterations": max_iterations, "task_preview": task[:200]},
        )
        self.code = "MAX_ITERATIONS_EXCEEDED"


class AgentSpawnError(OrchestratorError):
    """Raised when spawning a sub-agent fails."""

    def __init__(self, agent_type: str, reason: str):
        super().__init__(
            message=f"Failed to spawn agent of type '{agent_type}': {reason}",
            details={"agent_type": agent_type, "reason": reason},
        )
        self.code = "AGENT_SPAWN_ERROR"


# ── Agent Errors ──────────────────────────────────────────────

class AgentError(NexusError):
    """Base exception for agent operations."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="AGENT_ERROR", details=details)


class AgentTimeoutError(AgentError):
    """Raised when an agent operation times out."""

    def __init__(self, agent_type: str, timeout_seconds: int):
        super().__init__(
            message=f"Agent '{agent_type}' timed out after {timeout_seconds}s",
            details={"agent_type": agent_type, "timeout_seconds": timeout_seconds},
        )
        self.code = "AGENT_TIMEOUT"


# ── Vault Errors ──────────────────────────────────────────────

class VaultError(NexusError):
    """Raised when secrets vault operations fail."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="VAULT_ERROR", details=details)


# ── MCP Errors ────────────────────────────────────────────────

class MCPError(NexusError):
    """Base exception for MCP protocol operations."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="MCP_ERROR", details=details)


class MCPToolError(MCPError):
    """Raised when an MCP tool execution fails."""

    def __init__(self, tool_name: str, reason: str):
        super().__init__(
            message=f"MCP tool '{tool_name}' failed: {reason}",
            details={"tool_name": tool_name, "reason": reason},
        )
        self.code = "MCP_TOOL_ERROR"


# ── Security Errors ───────────────────────────────────────────

class SecurityError(NexusError):
    """Base exception for security violations."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="SECURITY_ERROR", details=details)


class GuardrailViolationError(SecurityError):
    """Raised when a guardrail is violated."""

    def __init__(self, guardrail_name: str, reason: str, severity: str = "high"):
        super().__init__(
            message=f"Guardrail '{guardrail_name}' violated: {reason}",
            details={"guardrail_name": guardrail_name, "reason": reason, "severity": severity},
        )
        self.code = "GUARDRAIL_VIOLATION"


class SandboxError(SecurityError):
    """Raised when sandboxed execution fails."""

    def __init__(self, reason: str, command: Optional[str] = None):
        super().__init__(
            message=f"Sandbox error: {reason}",
            details={"reason": reason, "command": command},
        )
        self.code = "SANDBOX_ERROR"


class RateLimitExceededError(SecurityError):
    """Raised when request rate exceeds configured limits."""

    def __init__(self, limit: int, window: str):
        super().__init__(
            message=f"Rate limit exceeded: {limit} requests per {window}",
            details={"limit": limit, "window": window},
        )
        self.code = "RATE_LIMIT_EXCEEDED"


# ── Browser Errors ────────────────────────────────────────────

class BrowserError(NexusError):
    """Base exception for browser automation operations."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="BROWSER_ERROR", details=details)


class BrowserServiceUnavailableError(BrowserError):
    """Raised when the browser micro-service is unreachable."""

    def __init__(self, url: str):
        super().__init__(
            message=f"Browser service unavailable at {url}",
            details={"url": url},
        )
        self.code = "BROWSER_SERVICE_UNAVAILABLE"
