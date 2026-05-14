"""
NEXUS Google Gemini Provider — Gemini 2.5 Pro, Gemini 2.0 Flash via Google AI API.

First-class provider implementation with LiteLLM integration and direct
HTTP API fallback. Supports Gemini-specific features like grounding
and safety settings.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

from nexus.core.config import get_settings
from nexus.core.exceptions import LLMProviderError, LLMRateLimitError

logger = logging.getLogger(__name__)

GEMINI_MODELS = {
    "gemini-2.5-pro-preview-05-06": {"context": 1048576, "cost_input": 1.25, "cost_output": 10.00},
    "gemini-2.0-flash": {"context": 1048576, "cost_input": 0.10, "cost_output": 0.40},
    "gemini-2.0-flash-lite": {"context": 1048576, "cost_input": 0.025, "cost_output": 0.10},
    "gemini-1.5-pro": {"context": 2097152, "cost_input": 1.25, "cost_output": 5.00},
    "gemma-4-31b-it": {"context": 32768, "cost_input": 0.0, "cost_output": 0.0},
    "gemma-4-26b-a4b-it": {"context": 32768, "cost_input": 0.0, "cost_output": 0.0},
}

# Gemma 4 specifics:
#   thinkingLevel: "MINIMAL" or "HIGH" (NOT "LOW"/"MEDIUM" nor thinkingBudget)
#   <|think|> token in system prompt activates thinking
#   Response uses <|channel>thought...<channel|> / thought: true split


@dataclass
class GeminiResponse:
    """Structured response from Gemini provider."""
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "STOP"
    latency_ms: float = 0.0
    cost_usd: float = 0.0


class GeminiProvider:
    """
    Google Gemini LLM Provider with LiteLLM integration and direct API fallback.

    Supports:
      - Chat completions via generateContent API
      - Streaming
      - Grounding with Google Search
      - Safety settings configuration
      - Automatic cost estimation

    Usage:
        provider = GeminiProvider()
        response = await provider.complete(
            messages=[{"role": "user", "content": "Hello"}],
            model="gemini-2.0-flash",
        )
    """

    def __init__(self):
        self.settings = get_settings()
        self._call_count = 0
        self._total_cost = 0.0
        self._last_error: Optional[str] = None

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def is_available(self) -> bool:
        return bool(self.settings.google_api_key)

    def _estimate_cost(self, model: str, usage: dict[str, int]) -> float:
        model_info = GEMINI_MODELS.get(model, GEMINI_MODELS["gemini-2.0-flash"])
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        return (input_tokens / 1_000_000 * model_info["cost_input"] +
                output_tokens / 1_000_000 * model_info["cost_output"])

    def _convert_messages_to_gemini(self, messages: list[dict[str, str]]) -> list[dict[str, Any]]:
        """Convert OpenAI-format messages to Gemini format."""
        gemini_contents = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            if msg["role"] == "system":
                gemini_contents.append({
                    "role": "user",
                    "parts": [{"text": f"System instruction: {msg['content']}"}],
                })
                gemini_contents.append({
                    "role": "model",
                    "parts": [{"text": "Understood. I will follow these instructions."}],
                })
            else:
                gemini_contents.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}],
                })
        return gemini_contents

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str = "gemini-2.0-flash",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 0.95,
        grounding: bool = False,
        thinking_level: str = "MINIMAL",
        **kwargs,
    ) -> GeminiResponse:
        """
        Generate a chat completion.

        For Gemma 4 models, supports thinkingLevel ("MINIMAL" or "HIGH").
        Use <|think|> in system prompt to activate thinking on Gemma 4.
        """
        start = time.monotonic()
        is_gemma = model.startswith("gemma-")

        try:
            content, usage, finish_reason = await self._call_via_litellm(
                messages=messages, model=model, temperature=temperature,
                max_tokens=max_tokens, top_p=top_p,
            )
        except ImportError:
            content, usage, finish_reason = await self._call_direct(
                messages=messages, model=model, temperature=temperature,
                max_tokens=max_tokens, top_p=top_p, grounding=grounding,
                is_gemma=is_gemma, thinking_level=thinking_level,
            )
        except (LLMRateLimitError, LLMProviderError):
            raise
        except Exception as e:
            self._last_error = str(e)
            logger.debug("LiteLLM failed for Gemini, trying direct: %s", e)
            content, usage, finish_reason = await self._call_direct(
                messages=messages, model=model, temperature=temperature,
                max_tokens=max_tokens, top_p=top_p, grounding=grounding,
                is_gemma=is_gemma, thinking_level=thinking_level,
            )

        latency = (time.monotonic() - start) * 1000
        cost = self._estimate_cost(model, usage)
        self._call_count += 1
        self._total_cost += cost

        return GeminiResponse(
            content=content, model=model, usage=usage,
            finish_reason=finish_reason, latency_ms=latency, cost_usd=cost,
        )

    async def _call_via_litellm(
        self, messages, model, temperature, max_tokens, top_p,
    ) -> tuple[str, dict[str, int], str]:
        import litellm

        try:
            response = await asyncio.to_thread(
                litellm.completion,
                model=f"gemini/{model}",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                timeout=self.settings.llm_timeout_seconds,
            )
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str:
                self._last_error = str(e)
                raise LLMRateLimitError(provider="gemini")
            self._last_error = str(e)
            raise LLMProviderError(provider="gemini", reason=str(e), model=model)

        content = response.choices[0].message.content or ""
        usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }
        return content, usage, response.choices[0].finish_reason or "STOP"

    async def _call_direct(
        self, messages, model, temperature, max_tokens, top_p, grounding,
        is_gemma=False, thinking_level="MINIMAL",
    ) -> tuple[str, dict[str, int], str]:
        import httpx

        api_key = self.settings.google_api_key
        if not api_key:
            raise LLMProviderError(provider="gemini", reason="GOOGLE_API_KEY not configured", model=model)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        gemini_contents = self._convert_messages_to_gemini(messages)

        generation_config: dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "topP": top_p,
        }

        # Gemma 4 supports thinkingConfig (only MINIMAL or HIGH)
        if is_gemma:
            if thinking_level in ("MINIMAL", "HIGH"):
                generation_config["thinkingConfig"] = {"thinkingLevel": thinking_level}

        payload: dict[str, Any] = {
            "contents": gemini_contents,
            "generationConfig": generation_config,
        }

        # Extract system instruction from first message if present (Gemma 4 supports native system)
        if messages and messages[0].get("role") == "system":
            system_text = messages[0]["content"]
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
            # Add <|think|> token automatically for Gemma 4 thinking
            if is_gemma and thinking_level != "MINIMAL" and "<|think|>" not in system_text:
                payload["systemInstruction"]["parts"][0]["text"] = f"<|think|> {system_text}"
            gemini_contents = gemini_contents[1:]  # Remove system from contents
            payload["contents"] = gemini_contents

        if grounding:
            payload["tools"] = [{"google_search": {}}]

        headers = {"x-goog-api-key": api_key}
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload, headers=headers)

        if response.status_code == 429:
            self._last_error = "HTTP 429: Rate limited by Gemini"
            raise LLMRateLimitError(provider="gemini")
        if response.status_code != 200:
            error_reason = f"HTTP {response.status_code}: {response.text[:200]}"
            self._last_error = error_reason
            raise LLMProviderError(
                provider="gemini",
                reason=error_reason,
                model=model,
            )

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return "No response generated", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}, "SAFETY"

        # Extract content from parts (handle thought/answer split for Gemma 4)
        parts = candidates[0].get("content", {}).get("parts", [])
        content_text = ""
        thought_text = ""
        for part in parts:
            if part.get("thought"):
                thought_text += part.get("text", "")
            else:
                content_text += part.get("text", "")
        # Prefer non-thought content, fallback to all text
        content = content_text or parts[0].get("text", "") if parts else ""
        finish_reason = candidates[0].get("finishReason", "STOP")

        usage_meta = data.get("usageMetadata", {})
        usage = {
            "prompt_tokens": usage_meta.get("promptTokenCount", 0),
            "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
            "total_tokens": usage_meta.get("totalTokenCount", 0),
            "thoughts_tokens": usage_meta.get("thoughtsTokenCount", 0),
        }

        return content, usage, finish_reason

    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str = "gemini-2.0-flash",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream a chat completion from Gemini."""
        import httpx

        api_key = self.settings.google_api_key
        if not api_key:
            raise LLMProviderError(provider="gemini", reason="GOOGLE_API_KEY not configured", model=model)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse"

        gemini_contents = self._convert_messages_to_gemini(messages)

        payload = {
            "contents": gemini_contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        headers = {"x-goog-api-key": api_key}
        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    error_reason = f"HTTP {response.status_code}"
                    self._last_error = error_reason
                    raise LLMProviderError(provider="gemini", reason=error_reason, model=model)
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            event = json.loads(line[6:])
                            parts = event.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                            for part in parts:
                                if "text" in part:
                                    yield part["text"]
                        except (json.JSONDecodeError, IndexError):
                            continue

    async def close(self) -> None:
        """Cleanup resources."""
        # Gemini uses google-genai SDK which doesn't require cleanup

    def get_stats(self) -> dict[str, Any]:
        return {
            "provider": "gemini",
            "available": self.is_available,
            "call_count": self._call_count,
            "total_cost_usd": round(self._total_cost, 6),
            "last_error": self._last_error,
            "models": list(GEMINI_MODELS.keys()),
        }
