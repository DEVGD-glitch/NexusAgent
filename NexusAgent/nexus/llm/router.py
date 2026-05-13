"""
NEXUS Multi-LLM Router — Intelligent provider selection with fallback chains.

Routes LLM requests to the optimal provider based on task requirements,
cost, latency, and availability. Supports 5 providers:
  - OpenAI (GPT-4o, GPT-4o-mini)
  - Anthropic (Claude 3.5 Sonnet, Claude 3 Opus)
  - Google (Gemini 2.5 Pro, Gemini 2.0 Flash)
  - GLM (GLM-5 via ZAI API) — first-class provider
  - Ollama (local models via http://127.0.0.1:11434)

Key features:
  - Automatic fallback chain when providers fail
  - LiteLLM as unified interface
  - Cost-aware routing
  - Rate limit handling with retry-after
  - Streaming support
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Optional

import httpx

from nexus.core.config import get_settings
from nexus.core.exceptions import (
    LLMAllProvidersFailedError,
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
)

logger = logging.getLogger(__name__)


class Provider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    GLM = "glm"
    OLLAMA = "ollama"
    POLLINATIONS = "pollinations"
    G4F = "g4f"
    DEEPINFRA = "deepinfra"
    GROQ = "groq"
    OPENROUTER = "openrouter"
    NVIDIA = "nvidia"
    CEREBRAS = "cerebras"
    TOGETHER = "together"


class TaskComplexity(str, Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


# Provider → default model mapping
PROVIDER_DEFAULT_MODELS = {
    Provider.OPENAI: "gpt-4o",
    Provider.ANTHROPIC: "claude-3-5-sonnet-20241022",
    Provider.GEMINI: "gemma-4-31b-it",
    Provider.GLM: "glm-4-flash",  # Free model as default
    Provider.OLLAMA: "llama3.1:8b",
    Provider.POLLINATIONS: "openai",
    Provider.G4F: "gpt-4o-mini",
    Provider.DEEPINFRA: "meta-llama/Llama-4-Maverick-17B",
    Provider.GROQ: "llama-3.3-70b-versatile",
    Provider.OPENROUTER: "openrouter/auto",
    Provider.NVIDIA: "nvidia/llama-3.1-nemotron-70b-instruct",
    Provider.CEREBRAS: "llama3.1-8b",
    Provider.TOGETHER: "meta-llama/Llama-3.3-70B-Instruct-Turbo",
}

# Models that support function calling via LiteLLM with gemini/ prefix
GEMINI_FUNCTION_CALLING_MODELS = {
    "gemma-4-31b-it",
    "gemma-4-27b-it",
    "gemma-3-27b-it",
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-3-flash",
    "gemini-3-pro",
}

# Task complexity → recommended provider order
COMPLEXITY_ROUTING = {
    TaskComplexity.SIMPLE: [Provider.POLLINATIONS, Provider.G4F, Provider.DEEPINFRA, Provider.GROQ, Provider.CEREBRAS, Provider.GEMINI, Provider.OPENAI, Provider.ANTHROPIC],
    TaskComplexity.MEDIUM: [Provider.GEMINI, Provider.GROQ, Provider.OPENROUTER, Provider.NVIDIA, Provider.CEREBRAS, Provider.OPENAI, Provider.ANTHROPIC, Provider.TOGETHER, Provider.GLM],
    TaskComplexity.COMPLEX: [Provider.GEMINI, Provider.OPENROUTER, Provider.NVIDIA, Provider.ANTHROPIC, Provider.OPENAI, Provider.GLM, Provider.TOGETHER],
}


@dataclass
class LLMResponse:
    """Structured response from an LLM provider."""
    content: str
    provider: Provider
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0
    finish_reason: str = ""
    raw_response: Optional[Any] = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "provider": self.provider.value,
            "model": self.model,
            "usage": self.usage,
            "latency_ms": self.latency_ms,
            "finish_reason": self.finish_reason,
        }


class LLMRouter:
    """
    Multi-LLM Router with intelligent provider selection and fallback.

    Uses LiteLLM as the unified interface for all providers, with
    direct API calls as fallback when LiteLLM is unavailable.

    Usage:
        router = LLMRouter()
        response = await router.complete(
            messages=[{"role": "user", "content": "Hello"}],
            provider="openai",
        )
        print(response.content)
    """

    def __init__(self):
        self.settings = get_settings()
        self._provider_status: dict[str, dict[str, Any]] = {}

    def _get_api_key(self, provider: Provider) -> Optional[str]:
        """Get the API key for a provider from settings."""
        key_map = {
            Provider.OPENAI: self.settings.openai_api_key,
            Provider.ANTHROPIC: self.settings.anthropic_api_key,
            Provider.GEMINI: self.settings.google_api_key,
            Provider.GLM: self.settings.zai_api_key,
            Provider.GROQ: self.settings.groq_api_key,
            Provider.OPENROUTER: self.settings.openrouter_api_key,
            Provider.NVIDIA: self.settings.nvidia_api_key,
            Provider.CEREBRAS: self.settings.cerebras_api_key,
            Provider.TOGETHER: self.settings.together_api_key,
            Provider.OLLAMA: "local",
        }
        return key_map.get(provider)

    NO_KEY_PROVIDERS = {Provider.OLLAMA, Provider.POLLINATIONS, Provider.G4F, Provider.DEEPINFRA}

    def _is_provider_available(self, provider: Provider) -> bool:
        """Check if a provider has its API key configured."""
        key = self._get_api_key(provider)
        if provider in self.NO_KEY_PROVIDERS:
            return True
        return key is not None and len(key) > 0

    def select_provider(
        self,
        task_complexity: TaskComplexity = TaskComplexity.MEDIUM,
        preferred_provider: Optional[str] = None,
    ) -> list[Provider]:
        """
        Select the ordered list of providers to try based on task complexity.

        Args:
            task_complexity: Estimated task complexity.
            preferred_provider: User-specified preferred provider.

        Returns:
            Ordered list of providers to try.
        """
        if preferred_provider:
            try:
                pref = Provider(preferred_provider)
                if self._is_provider_available(pref):
                    # When explicitly specified, use ONLY that provider (no fallback to others)
                    return [pref]
            except ValueError:
                pass

        preferred = COMPLEXITY_ROUTING.get(task_complexity, COMPLEXITY_ROUTING[TaskComplexity.MEDIUM])
        return [p for p in preferred if self._is_provider_available(p)]

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        provider: Optional[str] = None,
        task_complexity: TaskComplexity = TaskComplexity.MEDIUM,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Complete a chat completion request.

        Single Provider Mode (when provider is specified):
        - NO automatic fallback to other providers
        - Retry with exponential backoff for rate limits and transient errors
        - Maximum 5 retries per request

        Auto Routing Mode (when provider is None):
        - Tries providers in order based on task complexity
        - Falls back to next provider on failure

        Args:
            messages: List of message dicts [{"role": "user", "content": "..."}].
            model: Specific model to use.
            provider: Specific provider to use (enables single provider mode).
            task_complexity: Task complexity for routing (only used when provider is None).
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            stream: Whether to use streaming.
            tools: Tool definitions for function calling.

        Returns:
            LLMResponse with the completion.

        Raises:
            LLMAllProvidersFailedError: If all providers in the chain fail.
        """
        is_single_provider_mode = provider is not None
        providers = self.select_provider(task_complexity, provider)

        if not providers:
            raise LLMError("No LLM providers available. Configure API keys in .env")

        errors = []
        current_messages = list(messages)
        max_tool_turns = 10
        max_retries = 5 if is_single_provider_mode else 1

        for turn in range(max_tool_turns):
            for prov in providers:
                use_model = model or PROVIDER_DEFAULT_MODELS.get(prov, "gpt-4o")
                start = time.monotonic()

                # Retry loop for single provider mode
                for retry in range(max_retries + 1):
                    try:
                        if stream:
                            content = await self._call_provider_streaming(
                                provider=prov, model=use_model, messages=current_messages,
                                temperature=temperature, max_tokens=max_tokens,
                            )
                            usage = {}
                            finish_reason = "stop"
                            tool_calls = []
                        else:
                            content, usage, finish_reason, tool_calls = await self._call_provider(
                                provider=prov, model=use_model, messages=current_messages,
                                temperature=temperature, max_tokens=max_tokens,
                                tools=tools if turn < max_tool_turns else None,
                            )

                        latency = (time.monotonic() - start) * 1000
                        self._record_provider_status(prov, success=True, latency_ms=latency)

                        logger.info(
                            "LLM complete: provider=%s model=%s latency=%.0fms tokens=%s tool_calls=%d",
                            prov.value, use_model, latency, usage, len(tool_calls),
                        )

                        if not tool_calls:
                            return LLMResponse(
                                content=content,
                                provider=prov,
                                model=use_model,
                                usage=usage or {},
                                latency_ms=latency,
                                finish_reason=finish_reason or "stop",
                                tool_calls=[],
                            )

                        return LLMResponse(
                            content=content or f"[Tool calls requested: {len(tool_calls)} tools]",
                            provider=prov,
                            model=use_model,
                            usage=usage or {},
                            latency_ms=latency,
                            finish_reason=finish_reason or "tool_calls",
                            tool_calls=tool_calls,
                        )

                    except LLMRateLimitError as e:
                        # Rate limit: wait and retry (single provider mode) or skip (auto routing)
                        if is_single_provider_mode and retry < max_retries:
                            wait_time = min(2 ** retry * 4.0, 60.0)  # 4s, 8s, 16s, 32s, 64s max
                            logger.warning(
                                "Rate limited on %s (retry %d/%d), waiting %.1fs...",
                                prov.value, retry + 1, max_retries + 1, wait_time,
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            logger.warning("Rate limited on %s: %s", prov.value, e)
                            errors.append(f"{prov.value}: rate_limited")
                            self._record_provider_status(prov, success=False, error="rate_limited")
                            if is_single_provider_mode:
                                raise LLMAllProvidersFailedError(
                                    providers_tried=[prov.value],
                                    errors=[f"rate_limited after {retry + 1} retries"],
                                )
                            break  # Try next provider in auto routing mode

                    except LLMProviderError as e:
                        # Provider error: retry for transient errors in single provider mode
                        if is_single_provider_mode and retry < max_retries and self._is_transient_error(e):
                            wait_time = min(2 ** retry * 2.0, 30.0)
                            logger.warning(
                                "Provider %s error (retry %d/%d): %s, waiting %.1fs...",
                                prov.value, retry + 1, max_retries + 1, e.message, wait_time,
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            logger.warning("Provider %s failed: %s", prov.value, e)
                            errors.append(f"{prov.value}: {e.message}")
                            self._record_provider_status(prov, success=False, error=e.message)
                            if is_single_provider_mode:
                                raise LLMAllProvidersFailedError(
                                    providers_tried=[prov.value],
                                    errors=[e.message],
                                )
                            break  # Try next provider in auto routing mode

                    except Exception as e:
                        logger.warning("Unexpected error from %s: %s", prov.value, e)
                        errors.append(f"{prov.value}: {str(e)}")
                        self._record_provider_status(prov, success=False, error=str(e))
                        if is_single_provider_mode:
                            raise LLMAllProvidersFailedError(
                                providers_tried=[prov.value],
                                errors=[str(e)],
                            )
                        break  # Try next provider in auto routing mode

            # Only reach here in auto routing mode (multiple providers)
            if is_single_provider_mode:
                raise LLMAllProvidersFailedError(
                    providers_tried=[p.value for p in providers],
                    errors=errors,
                )

        raise LLMError(f"Max tool turns ({max_tool_turns}) exceeded")

    def _is_transient_error(self, error: LLMProviderError) -> bool:
        """Check if an error is transient (worth retrying)."""
        if not error.message:
            return False
        msg_lower = error.message.lower()
        transient_patterns = ["500", "internal error", "service unavailable", "timeout", "timed out"]
        return any(p in msg_lower for p in transient_patterns)

    async def _call_provider(
        self,
        provider: Provider,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> tuple[str, dict[str, int], str, list[dict[str, Any]]]:
        """
        Make a non-streaming completion call to a specific provider.

        Returns:
            Tuple of (content, usage_dict, finish_reason, tool_calls)
        """
        # Gemini uses direct API (bypasses LiteLLM for reliability)
        if provider == Provider.GEMINI:
            return await self._call_gemini_direct(model, messages, temperature, max_tokens, tools)

        # Other providers: try LiteLLM first
        try:
            return await self._call_via_litellm(provider, model, messages, temperature, max_tokens, tools)
        except ImportError:
            logger.debug("LiteLLM not available, using direct API")
        except Exception as e:
            logger.debug("LiteLLM failed for %s: %s, trying direct API", provider.value, e)

        # Fallback to direct API
        direct_config = {
            Provider.GLM: (self.settings.zai_base_url, self.settings.zai_api_key),
            Provider.OLLAMA: (self.settings.ollama_base_url + "/v1", "ollama"),
            Provider.GROQ: ("https://api.groq.com/openai/v1", self.settings.groq_api_key),
            Provider.OPENROUTER: ("https://openrouter.ai/api/v1", self.settings.openrouter_api_key),
            Provider.NVIDIA: ("https://integrate.api.nvidia.com/v1", self.settings.nvidia_api_key),
            Provider.CEREBRAS: ("https://api.cerebras.ai/v1", self.settings.cerebras_api_key),
            Provider.TOGETHER: ("https://api.together.xyz/v1", self.settings.together_api_key),
        }
        if provider in direct_config and direct_config[provider][1]:
            base_url, api_key = direct_config[provider]
            return await self._call_openai_compatible_direct(
                base_url, api_key, provider.value, model, messages, temperature, max_tokens, tools,
            )

        raise LLMProviderError(
            provider=provider.value,
            reason="Neither LiteLLM nor direct API available",
            model=model,
        )

    async def _call_via_litellm(
        self,
        provider: Provider,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        tools: Optional[list[dict[str, Any]]] = None,
        max_retries: int = 3,
    ) -> tuple[str, dict[str, int], str, list[dict[str, Any]]]:
        """Call provider via LiteLLM with automatic retry for transient errors."""
        import litellm

        # Map provider to LiteLLM model prefix
        litellm_model_map = {
            Provider.OPENAI: f"openai/{model}",
            Provider.ANTHROPIC: f"anthropic/{model}",
            Provider.GEMINI: f"gemini/{model}",
            Provider.GROQ: f"groq/{model}",
            Provider.OPENROUTER: f"openrouter/{model}",
            Provider.NVIDIA: f"nvidia/{model}",
            Provider.CEREBRAS: f"cerebras/{model}",
            Provider.TOGETHER: f"together_ai/{model}",
        }

        litellm_model = litellm_model_map.get(provider, model)

        # Build call kwargs
        call_kwargs = {
            "model": litellm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": self.settings.llm_timeout_seconds,
        }

        # Pass API key directly to avoid env var issues on Windows
        api_key_passthrough = {
            Provider.GEMINI: self.settings.google_api_key,
            Provider.GROQ: self.settings.groq_api_key,
            Provider.OPENROUTER: self.settings.openrouter_api_key,
            Provider.NVIDIA: self.settings.nvidia_api_key,
            Provider.CEREBRAS: self.settings.cerebras_api_key,
            Provider.TOGETHER: self.settings.together_api_key,
        }
        if provider in api_key_passthrough and api_key_passthrough[provider]:
            call_kwargs["api_key"] = api_key_passthrough[provider]

        if tools:
            call_kwargs["tools"] = tools

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = await asyncio.to_thread(
                    litellm.completion,
                    **call_kwargs,
                )

                content = response.choices[0].message.content or ""
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                }
                finish_reason = response.choices[0].finish_reason or "stop"

                # Extract tool calls
                tool_calls = []
                raw_tool_calls = getattr(response.choices[0].message, "tool_calls", None)
                if raw_tool_calls:
                    for tc in raw_tool_calls:
                        tc_dict = {
                            "id": getattr(tc, "id", ""),
                            "type": getattr(tc, "type", "function"),
                            "function": {
                                "name": tc.function.name if hasattr(tc, "function") else "",
                                "arguments": tc.function.arguments if hasattr(tc, "function") else "{}",
                            }
                        }
                        tool_calls.append(tc_dict)

                return content, usage, finish_reason, tool_calls

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check if it's a transient error (500, timeout, etc.)
                is_transient = any(x in error_str for x in [
                    "500", "internal server error", "timeout", "timed out",
                    "service unavailable", "502", "503", "504"
                ])

                if is_transient and attempt < max_retries:
                    delay = min(2 ** attempt * 1.0, 10.0)
                    logger.warning(
                        "Transient error from %s (attempt %d/%d): %s. Retrying in %.1fs...",
                        provider.value, attempt + 1, max_retries + 1, str(e)[:100], delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                # Rate limit
                if "rate" in error_str or "429" in error_str:
                    raise LLMRateLimitError(provider=provider.value)

                raise LLMProviderError(provider=provider.value, reason=str(e), model=model)

    async def _call_gemini_direct(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        tools: Optional[list[dict[str, Any]]] = None,
        max_retries: int = 3,
    ) -> tuple[str, dict[str, int], str, list[dict[str, Any]]]:
        """
        Call Gemini/Gemma models via OpenAI-compatible endpoint.
        This bypasses LiteLLM which has intermittent 500 errors.
        Retries with exponential backoff for transient errors.
        """
        api_key = self.settings.google_api_key
        if not api_key:
            raise LLMProviderError(provider="gemini", reason="GOOGLE_API_KEY not configured", model=model)

        url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
                    response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 429:
                    raise LLMRateLimitError(provider="gemini")

                # Retry on 500 errors (transient server errors)
                if response.status_code >= 500 and attempt < max_retries:
                    delay = min(2 ** attempt * 2.0, 30.0)
                    logger.warning(
                        "Gemini 500 error (attempt %d/%d): %s. Retrying in %.1fs...",
                        attempt + 1, max_retries + 1, response.text[:100], delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                if response.status_code != 200:
                    error_msg = response.text[:200]
                    raise LLMProviderError(provider="gemini", reason=f"HTTP {response.status_code}: {error_msg}", model=model)

                data = response.json()
                choice = data["choices"][0]
                content = choice.get("message", {}).get("content") or ""

                # Gemma models return <thought> tags with internal reasoning
                # Strip them to get the clean response
                if "<thought>" in content:
                    parts = content.split("</thought>")
                    content = parts[-1].strip() if len(parts) > 1 else content.strip()

                # Extract tool calls
                tool_calls = []
                raw_tcs = choice.get("message", {}).get("tool_calls", [])
                for tc in raw_tcs:
                    tc_dict = {
                        "id": tc.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": tc.get("function", {}).get("name", ""),
                            "arguments": tc.get("function", {}).get("arguments", "{}"),
                        }
                    }
                    tool_calls.append(tc_dict)

                usage = data.get("usage", {})
                finish_reason = choice.get("finish_reason", "stop")

                return content, usage, finish_reason, tool_calls

            except (LLMRateLimitError, LLMProviderError):
                raise
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    delay = min(2 ** attempt * 2.0, 30.0)
                    logger.warning("Gemini error (attempt %d/%d): %s. Retrying...", attempt + 1, max_retries + 1, str(e)[:100])
                    await asyncio.sleep(delay)
                    continue
                raise LLMProviderError(provider="gemini", reason=str(last_error), model=model)

    async def _call_openai_compatible_direct(
        self,
        base_url: str,
        api_key: str,
        provider_name: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        tools: Optional[list[dict[str, Any]]] = None,
        max_retries: int = 3,
    ) -> tuple[str, dict[str, int], str, list[dict[str, Any]]]:
        """Generic direct caller for any OpenAI-compatible API."""
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
                    response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 429:
                    raise LLMRateLimitError(provider=provider_name)
                if response.status_code >= 500 and attempt < max_retries:
                    delay = min(2 ** attempt * 2.0, 30.0)
                    await asyncio.sleep(delay)
                    continue
                if response.status_code != 200:
                    raise LLMProviderError(provider=provider_name, reason=f"HTTP {response.status_code}: {response.text[:200]}", model=model)

                data = response.json()
                choice = data["choices"][0]
                content = choice.get("message", {}).get("content") or ""
                usage = data.get("usage", {})
                finish_reason = choice.get("finish_reason", "stop")

                tool_calls = []
                raw_tcs = choice.get("message", {}).get("tool_calls", [])
                for tc in raw_tcs:
                    tool_calls.append({
                        "id": tc.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": tc.get("function", {}).get("name", ""),
                            "arguments": tc.get("function", {}).get("arguments", "{}"),
                        }
                    })
                return content, usage, finish_reason, tool_calls

            except (LLMRateLimitError, LLMProviderError):
                raise
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    delay = min(2 ** attempt * 2.0, 30.0)
                    await asyncio.sleep(delay)
                    continue
                raise LLMProviderError(provider=provider_name, reason=str(last_error), model=model)

    async def _call_provider_streaming(
        self,
        provider: Provider,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Handle streaming response (returns accumulated content for MVP)."""
        # For MVP, just do a regular call
        content, usage, finish_reason, tool_calls = await self._call_provider(
            provider=provider, model=model, messages=messages,
            temperature=temperature, max_tokens=max_tokens,
        )
        return content

    def _record_provider_status(
        self,
        provider: Provider,
        success: bool,
        latency_ms: float = 0.0,
        error: Optional[str] = None,
    ):
        """Record provider call result for monitoring."""
        self._provider_status[provider.value] = {
            "last_call": time.time(),
            "success": success,
            "latency_ms": latency_ms,
            "error": error,
        }

    def get_provider_status(self) -> dict[str, Any]:
        """Get status of all providers."""
        all_providers = {}
        for prov in Provider:
            all_providers[prov.value] = {
                "available": self._is_provider_available(prov),
                "default_model": PROVIDER_DEFAULT_MODELS.get(prov, "unknown"),
                "last_status": self._provider_status.get(prov.value, {}),
            }
        return all_providers
