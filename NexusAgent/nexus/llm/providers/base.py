"""
NEXUS LLM Provider Base — Abstract base class for all LLM providers.

Defines the contract that every provider must implement for seamless
routing by the LLMRouter and FallbackChain.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMResponse:
    """
    Unified response from any LLM provider.

    This is the canonical response type that the router expects.
    All providers must convert their native responses to this format.
    """
    content: str
    model: str
    provider: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        # Ensure usage always has the expected keys
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            if key not in self.usage:
                # Use object.__setattr__ because the dataclass is frozen
                object.__setattr__(
                    self, "usage",
                    {**self.usage, key: self.usage.get(key, 0)},
                )


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    Every provider must implement:
      - name: provider identifier string
      - is_available: whether the provider is configured and ready
      - complete: async chat completion

    Optional overrides:
      - stream: async streaming completion
      - estimate_cost: cost estimation for a given model and usage
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name (e.g., 'openai', 'anthropic', 'gemini')."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is configured (API key present, etc.)."""
        ...

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate a chat completion.

        Args:
            messages: Conversation messages in OpenAI format.
            model: Model identifier (provider-specific default if empty).
            temperature: Sampling temperature (0.0-2.0).
            max_tokens: Maximum tokens to generate.
            tools: Optional tool definitions for function calling.

        Returns:
            LLMResponse with the generated content and metadata.

        Raises:
            LLMProviderError: On API errors.
            LLMRateLimitError: On rate limiting.
        """
        ...

    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        Generate a streaming chat completion.

        Default implementation falls back to non-streaming complete().
        Providers can override for native streaming support.
        """
        response = await self.complete(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        yield response.content

    def estimate_cost(self, model: str, usage: dict[str, int]) -> float:
        """
        Estimate the cost in USD for a given model and token usage.

        Default returns 0.0. Providers should override with actual pricing.
        """
        return 0.0
