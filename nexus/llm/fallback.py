"""
NEXUS LLM Fallback Chain — Multi-provider failover management.

Manages ordered lists of LLM providers with automatic failover
when a provider is unavailable. Tracks provider health status,
supports configurable retry policies, and logs all fallback
events for observability.

Integrates with the existing LLMRouter to provide a higher-level
abstraction for managing fallback chains per task type.

Usage:
    from nexus.llm.fallback import FallbackChain

    chain = FallbackChain(providers=["openai", "anthropic", "gemini", "ollama"])
    result = await chain.complete(messages=[...])
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from nexus.core.config import get_settings
from nexus.core.exceptions import (
    LLMAllProvidersFailedError,
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
)
from nexus.core.observability import get_observability

logger = logging.getLogger(__name__)


# ── Enums ─────────────────────────────────────────────────────────

class ProviderHealth(str, Enum):
    """Health status of an LLM provider."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class RetryPolicy(str, Enum):
    """Retry policy types."""
    NONE = "none"           # No retries
    FIXED = "fixed"         # Fixed delay between retries
    EXPONENTIAL = "exponential"  # Exponential backoff


# ── Data Structures ───────────────────────────────────────────────

@dataclass
class ProviderHealthRecord:
    """Health record for a single provider."""
    provider: str
    status: ProviderHealth = ProviderHealth.UNKNOWN
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_success_time: Optional[float] = None
    last_failure_time: Optional[float] = None
    last_error: Optional[str] = None
    total_requests: int = 0
    total_successes: int = 0
    total_failures: int = 0
    avg_latency_ms: float = 0.0
    _latency_samples: list[float] = field(default_factory=list)

    def record_success(self, latency_ms: float):
        """Record a successful request."""
        self.consecutive_failures = 0
        self.consecutive_successes += 1
        self.last_success_time = time.time()
        self.total_requests += 1
        self.total_successes += 1
        self._latency_samples.append(latency_ms)

        # Keep only the last 100 samples
        if len(self._latency_samples) > 100:
            self._latency_samples = self._latency_samples[-100:]

        self.avg_latency_ms = (
            sum(self._latency_samples) / len(self._latency_samples)
        )

        # Update health status
        if self.consecutive_successes >= 3:
            self.status = ProviderHealth.HEALTHY
        elif self.consecutive_successes >= 1:
            self.status = ProviderHealth.DEGRADED

    def record_failure(self, error: str):
        """Record a failed request."""
        self.consecutive_successes = 0
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        self.last_error = error
        self.total_requests += 1
        self.total_failures += 1

        # Update health status based on failures
        if self.consecutive_failures >= 3:
            self.status = ProviderHealth.UNHEALTHY
        elif self.consecutive_failures >= 1:
            self.status = ProviderHealth.DEGRADED

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status.value,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "total_requests": self.total_requests,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "last_error": self.last_error,
        }


@dataclass
class FallbackEvent:
    """Record of a fallback event (provider switch)."""
    from_provider: str
    to_provider: str
    reason: str
    task_preview: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_provider": self.from_provider,
            "to_provider": self.to_provider,
            "reason": self.reason,
            "task_preview": self.task_preview[:100],
            "timestamp": self.timestamp,
        }


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    policy: RetryPolicy = RetryPolicy.EXPONENTIAL
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    backoff_factor: float = 2.0

    def get_delay(self, attempt: int) -> float:
        """
        Calculate the delay before the next retry.

        Args:
            attempt: The current attempt number (0-indexed).

        Returns:
            Delay in seconds.
        """
        if self.policy == RetryPolicy.NONE:
            return 0.0
        elif self.policy == RetryPolicy.FIXED:
            return self.base_delay_seconds
        elif self.policy == RetryPolicy.EXPONENTIAL:
            delay = self.base_delay_seconds * (self.backoff_factor ** attempt)
            return min(delay, self.max_delay_seconds)
        return 0.0


# ── Fallback Chain ────────────────────────────────────────────────

class FallbackChain:
    """
    Manages an ordered list of LLM providers with automatic failover.

    Features:
      - Ordered provider list with configurable priority
      - Automatic failover on provider failure
      - Provider health tracking and scoring
      - Configurable retry policies (none, fixed, exponential backoff)
      - Fallback event logging for observability
      - Integration with LLMRouter for actual API calls
      - Circuit breaker pattern (skip unhealthy providers)

    Usage:
        chain = FallbackChain(
            providers=["openai", "anthropic", "gemini", "ollama"],
            retry_config=RetryConfig(policy=RetryPolicy.EXPONENTIAL),
        )
        result = await chain.complete(
            messages=[{"role": "user", "content": "Hello"}],
        )
    """

    def __init__(
        self,
        providers: Optional[list[str]] = None,
        retry_config: Optional[RetryConfig] = None,
        circuit_breaker_threshold: int = 3,
        circuit_breaker_recovery_seconds: float = 60.0,
    ):
        """
        Initialize the fallback chain.

        Args:
            providers: Ordered list of provider names.
            retry_config: Retry configuration.
            circuit_breaker_threshold: Consecutive failures before marking unhealthy.
            circuit_breaker_recovery_seconds: Seconds before retrying an unhealthy provider.
        """
        self.settings = get_settings()

        # Default providers from settings
        if providers is None:
            providers = self.settings.fallback_providers

        self._providers = providers
        self._retry_config = retry_config or RetryConfig()
        self._circuit_breaker_threshold = circuit_breaker_threshold
        self._circuit_breaker_recovery_seconds = circuit_breaker_recovery_seconds

        # Provider health records
        self._health: dict[str, ProviderHealthRecord] = {
            p: ProviderHealthRecord(provider=p) for p in providers
        }

        # Fallback event log
        self._fallback_log: list[FallbackEvent] = []

    @property
    def providers(self) -> list[str]:
        """Get the current provider list in order."""
        return self._providers

    def _is_provider_available(self, provider: str) -> bool:
        """Check if a provider is available (has API key configured)."""
        key_map = {
            "openai": self.settings.openai_api_key,
            "anthropic": self.settings.anthropic_api_key,
            "gemini": self.settings.google_api_key,
            "glm": self.settings.zai_api_key,
            "groq": self.settings.groq_api_key,
            "openrouter": self.settings.openrouter_api_key,
            "nvidia": self.settings.nvidia_api_key,
            "cerebras": self.settings.cerebras_api_key,
            "together": self.settings.together_api_key,
            "ollama": "local",
        }
        no_key_providers = {"ollama", "pollinations", "g4f", "deepinfra"}
        key = key_map.get(provider)
        if provider in no_key_providers:
            return True
        return key is not None and len(key) > 0

    def _is_provider_healthy(self, provider: str) -> bool:
        """
        Check if a provider is healthy enough to use.

        Applies circuit breaker logic: if a provider has had too many
        consecutive failures, it's marked unhealthy and skipped until
        the recovery period has passed.
        """
        health = self._health.get(provider)
        if health is None:
            return False

        # If healthy or degraded, allow
        if health.status in (ProviderHealth.HEALTHY, ProviderHealth.DEGRADED, ProviderHealth.UNKNOWN):
            return True

        # If unhealthy, check if recovery period has passed
        if health.status == ProviderHealth.UNHEALTHY:
            if health.last_failure_time is not None:
                elapsed = time.time() - health.last_failure_time
                if elapsed >= self._circuit_breaker_recovery_seconds:
                    logger.info(
                        "Provider %s recovery period elapsed (%.0fs), retrying",
                        provider, elapsed,
                    )
                    # Allow one retry to test recovery
                    return True
            return False

        return True

    def get_ordered_providers(self) -> list[str]:
        """
        Get providers in priority order, skipping unavailable and unhealthy ones.

        Returns:
            Ordered list of available, healthy provider names.
        """
        ordered = []
        for provider in self._providers:
            if self._is_provider_available(provider) and self._is_provider_healthy(provider):
                ordered.append(provider)
        return ordered

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        preferred_provider: Optional[str] = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Complete an LLM request with automatic fallback.

        Iterates through the provider chain, falling back to the next
        provider on failure. Applies retry policy before falling back.

        Args:
            messages: List of message dicts.
            model: Specific model to use.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            preferred_provider: Override the chain with a specific provider.
            **kwargs: Additional parameters.

        Returns:
            Dict with the completion result and metadata.

        Raises:
            LLMAllProvidersFailedError: If all providers fail.
        """
        from nexus.llm.router import LLMRouter, Provider, TaskComplexity

        # Build the provider order
        if preferred_provider:
            providers = [preferred_provider]
            remaining = [p for p in self.get_ordered_providers() if p != preferred_provider]
            providers.extend(remaining)
        else:
            providers = self.get_ordered_providers()

        if not providers:
            raise LLMError("No LLM providers available in the fallback chain")

        errors = []
        start_time = time.monotonic()

        for provider_name in providers:
            # Apply retry policy per provider
            for attempt in range(self._retry_config.max_retries + 1):
                try:
                    router = LLMRouter()
                    provider_enum = Provider(provider_name)

                    use_model = model or self._get_default_model(provider_name)

                    response = await router.complete(
                        messages=messages,
                        provider=provider_name,
                        model=use_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        task_complexity=TaskComplexity.MEDIUM,
                        **kwargs,
                    )

                    # Record success
                    health = self._health.get(provider_name)
                    if health:
                        health.record_success(response.latency_ms)

                    # Record in observability
                    try:
                        obs = get_observability()
                        obs.record_llm_call(
                            provider=provider_name,
                            model=use_model,
                            prompt_tokens=response.usage.get("prompt_tokens", 0),
                            completion_tokens=response.usage.get("completion_tokens", 0),
                            latency_ms=response.latency_ms,
                            success=True,
                        )
                    except Exception:
                        pass

                    total_latency = (time.monotonic() - start_time) * 1000

                    return {
                        "status": "completed",
                        "content": response.content,
                        "provider": provider_name,
                        "model": use_model,
                        "latency_ms": response.latency_ms,
                        "total_latency_ms": total_latency,
                        "usage": response.usage,
                        "finish_reason": response.finish_reason,
                        "attempts": attempt + 1,
                    }

                except LLMRateLimitError as e:
                    logger.warning("Rate limited on %s (attempt %d): %s", provider_name, attempt, e)
                    errors.append(f"{provider_name}: rate_limited (attempt {attempt + 1})")

                    health = self._health.get(provider_name)
                    if health:
                        health.record_failure("rate_limited")

                    # Don't retry on rate limits — move to next provider
                    break

                except LLMProviderError as e:
                    logger.warning("Provider %s failed (attempt %d): %s", provider_name, attempt, e.message)
                    errors.append(f"{provider_name}: {e.message} (attempt {attempt + 1})")

                    health = self._health.get(provider_name)
                    if health:
                        health.record_failure(e.message)

                    # Apply retry delay
                    if attempt < self._retry_config.max_retries:
                        delay = self._retry_config.get_delay(attempt)
                        if delay > 0:
                            logger.info("Retrying %s in %.1fs", provider_name, delay)
                            await asyncio.sleep(delay)
                        continue

                    # Max retries reached, fall back
                    break

                except Exception as e:
                    logger.warning("Unexpected error from %s: %s", provider_name, e)
                    errors.append(f"{provider_name}: {str(e)} (attempt {attempt + 1})")

                    health = self._health.get(provider_name)
                    if health:
                        health.record_failure(str(e))

                    # Apply retry delay
                    if attempt < self._retry_config.max_retries:
                        delay = self._retry_config.get_delay(attempt)
                        if delay > 0:
                            await asyncio.sleep(delay)
                        continue
                    break

            # If we get here, this provider failed all retries — log fallback
            next_providers = [p for p in providers if p != provider_name and self._is_provider_healthy(p)]
            if next_providers:
                fallback_event = FallbackEvent(
                    from_provider=provider_name,
                    to_provider=next_providers[0],
                    reason=errors[-1] if errors else "Unknown error",
                )
                self._fallback_log.append(fallback_event)
                logger.info(
                    "Falling back from %s to %s: %s",
                    provider_name, next_providers[0], fallback_event.reason,
                )

        # All providers failed
        raise LLMAllProvidersFailedError(
            providers_tried=providers,
            errors=errors,
        )

    def _get_default_model(self, provider: str) -> str:
        """Get the default model for a provider."""
        from nexus.llm.router import PROVIDER_DEFAULT_MODELS, Provider
        try:
            return PROVIDER_DEFAULT_MODELS.get(Provider(provider), "gpt-4o")
        except ValueError:
            return "gpt-4o"

    def update_provider_order(self, providers: list[str]):
        """Update the provider priority order."""
        self._providers = providers
        # Add health records for new providers
        for p in providers:
            if p not in self._health:
                self._health[p] = ProviderHealthRecord(provider=p)

    def get_health_status(self) -> dict[str, Any]:
        """Get health status of all providers in the chain."""
        return {
            "providers": {
                p: self._health[p].to_dict() for p in self._providers
                if p in self._health
            },
            "available_providers": self.get_ordered_providers(),
            "total_fallback_events": len(self._fallback_log),
        }

    def get_fallback_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent fallback events."""
        return [e.to_dict() for e in self._fallback_log[-limit:]]

    def reset_provider_health(self, provider: str):
        """Reset a provider's health record (e.g., after manual intervention)."""
        if provider in self._health:
            self._health[provider] = ProviderHealthRecord(provider=provider)
            logger.info("Health record reset for provider: %s", provider)

    def get_stats(self) -> dict[str, Any]:
        """Get fallback chain statistics."""
        total_requests = sum(h.total_requests for h in self._health.values())
        total_successes = sum(h.total_successes for h in self._health.values())
        total_failures = sum(h.total_failures for h in self._health.values())

        return {
            "providers": self._providers,
            "total_requests": total_requests,
            "total_successes": total_successes,
            "total_failures": total_failures,
            "success_rate": total_successes / total_requests if total_requests > 0 else 0,
            "fallback_events": len(self._fallback_log),
            "retry_policy": self._retry_config.policy.value,
            "circuit_breaker_threshold": self._circuit_breaker_threshold,
        }
