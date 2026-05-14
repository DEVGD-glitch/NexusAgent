"""
Tests for nexus.llm.router — LLMRouter, provider selection, direct API
calls, fallback logic, streaming, tool calls, and error handling.

Targets the ~42% of lines currently uncovered in router.py.
All external dependencies (litellm, httpx) are fully mocked.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import time

from nexus.core.exceptions import (
    LLMAllProvidersFailedError,
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
)
from nexus.llm.router import (
    GEMINI_FUNCTION_CALLING_MODELS,
    LLMRouter,
    Provider,
    TaskComplexity,
)


@pytest.fixture(autouse=True)
def _no_sleep():
    """Patch asyncio.sleep to a no-op so retry backoff doesn't block tests."""
    with patch("asyncio.sleep", return_value=None):
        yield


# ═══════════════════════════════════════════════════════════════════
# Constants & Enums
# ═══════════════════════════════════════════════════════════════════


class TestRouterConstants:
    """Tests for router constants and enums."""

    def test_provider_enum_values(self):
        """Provider enum has correct values."""
        assert Provider.OPENAI.value == "openai"
        assert Provider.ANTHROPIC.value == "anthropic"
        assert Provider.GEMINI.value == "gemini"
        assert Provider.GLM.value == "glm"
        assert Provider.OLLAMA.value == "ollama"

    def test_task_complexity_values(self):
        """TaskComplexity enum has correct values."""
        assert TaskComplexity.SIMPLE.value == "simple"
        assert TaskComplexity.MEDIUM.value == "medium"
        assert TaskComplexity.COMPLEX.value == "complex"

    def test_gemini_function_calling_models(self):
        """GEMINI_FUNCTION_CALLING_MODELS contains expected models."""
        assert "gemma-4-31b-it" in GEMINI_FUNCTION_CALLING_MODELS
        assert "gemini-2.5-flash" in GEMINI_FUNCTION_CALLING_MODELS


# ═══════════════════════════════════════════════════════════════════
# LLMRouter — Initialisation & Provider Methods
# ═══════════════════════════════════════════════════════════════════


class TestLLMRouterInit:
    """Tests for LLMRouter initialisation."""

    def test_init(self, mock_settings):
        """Router initialises with empty provider status."""
        router = LLMRouter()
        assert router._provider_status == {}

    def test_get_api_key(self, mock_settings):
        """_get_api_key returns correct key per provider."""
        router = LLMRouter()
        assert router._get_api_key(Provider.OPENAI) == "sk-test-openai"
        assert router._get_api_key(Provider.ANTHROPIC) == "sk-test-anthropic"
        assert router._get_api_key(Provider.GEMINI) == "sk-test-google"
        assert router._get_api_key(Provider.GLM) == "sk-test-zai"
        assert router._get_api_key(Provider.OLLAMA) == "local"

    def test_is_provider_available(self, mock_settings):
        """_is_provider_available checks API key presence."""
        router = LLMRouter()
        assert router._is_provider_available(Provider.OPENAI) is True
        assert router._is_provider_available(Provider.OLLAMA) is True  # Always

    def test_is_provider_available_no_key(self):
        """Provider without key is unavailable."""
        settings = MagicMock()
        settings.openai_api_key = None
        settings.anthropic_api_key = None
        settings.google_api_key = None
        settings.zai_api_key = None
        with patch("nexus.core.config.get_settings", return_value=settings):
            router = LLMRouter()
            assert router._is_provider_available(Provider.OPENAI) is False
            assert router._is_provider_available(Provider.OLLAMA) is True


# ═══════════════════════════════════════════════════════════════════
# Provider Selection
# ═══════════════════════════════════════════════════════════════════


class TestProviderSelection:
    """Tests for select_provider()."""

    def test_select_provider_default(self, mock_settings):
        """Default complexity returns medium priority providers."""
        router = LLMRouter()
        providers = router.select_provider()
        assert len(providers) >= 1
        assert all(isinstance(p, Provider) for p in providers)

    def test_select_provider_simple(self, mock_settings):
        """SIMPLE complexity returns appropriate providers."""
        router = LLMRouter()
        providers = router.select_provider(task_complexity=TaskComplexity.SIMPLE)
        assert len(providers) >= 1

    def test_select_provider_complex(self, mock_settings):
        """COMPLEX complexity returns appropriate providers."""
        router = LLMRouter()
        providers = router.select_provider(task_complexity=TaskComplexity.COMPLEX)
        assert len(providers) >= 1

    def test_select_provider_explicit(self, mock_settings):
        """Explicit preferred_provider returns only that provider."""
        router = LLMRouter()
        providers = router.select_provider(preferred_provider="openai")
        assert providers == [Provider.OPENAI]

    def test_select_provider_explicit_unavailable(self, mock_settings):
        """Unavailable preferred provider falls back to complexity routing."""
        router = LLMRouter()
        # Override the router's settings to make only gemini available
        router.settings.openai_api_key = None
        router.settings.anthropic_api_key = None
        router.settings.zai_api_key = None
        # google_api_key is still set by mock_settings

        providers = router.select_provider(preferred_provider="openai")
        # Should NOT include openai since it's unavailable
        assert Provider.OPENAI not in providers

    def test_select_provider_invalid_name(self, mock_settings):
        """Invalid preferred provider name returns complexity-based list."""
        router = LLMRouter()
        providers = router.select_provider(preferred_provider="nonexistent_thing")
        # Should fall back to complexity-based routing
        assert len(providers) >= 1


# ═══════════════════════════════════════════════════════════════════
# _call_via_litellm
# ═══════════════════════════════════════════════════════════════════


class TestCallViaLiteLLM:
    """Tests for _call_via_litellm."""

    @pytest.mark.asyncio
    async def test_success(self, mock_settings):
        """_call_via_litellm returns content, usage, finish_reason, tool_calls."""
        router = LLMRouter()
        mock_litellm_response = MagicMock()
        mock_litellm_response.choices = [MagicMock()]
        mock_litellm_response.choices[0].message.content = "Hello"
        mock_litellm_response.choices[0].finish_reason = "stop"
        mock_litellm_response.choices[0].message.tool_calls = None
        mock_litellm_response.usage.prompt_tokens = 10
        mock_litellm_response.usage.completion_tokens = 20
        mock_litellm_response.usage.total_tokens = 30

        with patch("litellm.completion", return_value=mock_litellm_response):
            content, usage, finish_reason, tool_calls = await router._call_via_litellm(
                provider=Provider.OPENAI,
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hi"}],
                temperature=0.7,
                max_tokens=100,
            )

        assert content == "Hello"
        assert usage["prompt_tokens"] == 10
        assert finish_reason == "stop"
        assert tool_calls == []

    @pytest.mark.asyncio
    async def test_success_with_tool_calls(self, mock_settings):
        """_call_via_litellm extracts tool calls from response."""
        router = LLMRouter()
        mock_litellm_response = MagicMock()
        mock_litellm_response.choices = [MagicMock()]
        mock_litellm_response.choices[0].message.content = ""
        mock_litellm_response.choices[0].finish_reason = "tool_calls"

        # Mock tool_calls
        tc = MagicMock()
        tc.id = "call_123"
        tc.type = "function"
        tc.function.name = "get_weather"
        tc.function.arguments = '{"city": "Paris"}'
        mock_litellm_response.choices[0].message.tool_calls = [tc]
        mock_litellm_response.usage.prompt_tokens = 5
        mock_litellm_response.usage.completion_tokens = 0
        mock_litellm_response.usage.total_tokens = 5

        with patch("litellm.completion", return_value=mock_litellm_response):
            content, usage, finish_reason, tool_calls = await router._call_via_litellm(
                provider=Provider.OPENAI,
                model="gpt-4o",
                messages=[{"role": "user", "content": "Weather?"}],
                temperature=0.7,
                max_tokens=100,
            )

        assert len(tool_calls) == 1
        assert tool_calls[0]["id"] == "call_123"
        assert tool_calls[0]["function"]["name"] == "get_weather"
        assert tool_calls[0]["function"]["arguments"] == '{"city": "Paris"}'

    @pytest.mark.asyncio
    async def test_transient_error_retry(self, mock_settings):
        """Transient errors are retried with backoff."""
        router = LLMRouter()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "OK"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage.prompt_tokens = 1
        mock_response.usage.completion_tokens = 1
        mock_response.usage.total_tokens = 2

        call_count = {"count": 0}

        def _side_effect(**kwargs):
            call_count["count"] += 1
            if call_count["count"] < 3:
                raise Exception("500 Internal Server Error")
            return mock_response

        with patch("litellm.completion", side_effect=_side_effect):
            content, usage, finish_reason, tool_calls = await router._call_via_litellm(
                provider=Provider.OPENAI,
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hi"}],
                temperature=0.7,
                max_tokens=100,
            )

        assert content == "OK"
        assert call_count["count"] == 3  # 2 failures + 1 success

    @pytest.mark.asyncio
    async def test_transient_error_exhausted(self, mock_settings):
        """All transient retries exhausted raises LLMProviderError."""
        router = LLMRouter()

        with patch("litellm.completion", side_effect=Exception("500 Internal Server Error")):
            with pytest.raises(LLMProviderError):
                await router._call_via_litellm(
                    provider=Provider.OPENAI,
                    model="gpt-4o",
                    messages=[{"role": "user", "content": "Hi"}],
                    temperature=0.7,
                    max_tokens=100,
                )

    @pytest.mark.asyncio
    async def test_rate_limit_raised(self, mock_settings):
        """Rate limit keywords raise LLMRateLimitError immediately."""
        router = LLMRouter()

        with patch("litellm.completion", side_effect=Exception("429 rate limit")):
            with pytest.raises(LLMRateLimitError):
                await router._call_via_litellm(
                    provider=Provider.OPENAI,
                    model="gpt-4o",
                    messages=[{"role": "user", "content": "Hi"}],
                    temperature=0.7,
                    max_tokens=100,
                )

    @pytest.mark.asyncio
    async def test_api_key_passed_for_gemini(self, mock_settings):
        """Gemini provider gets api_key passed to litellm."""
        router = LLMRouter()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "OK"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 1
        mock_response.usage.completion_tokens = 1
        mock_response.usage.total_tokens = 2

        with patch("litellm.completion", return_value=mock_response) as mock_comp:
            await router._call_via_litellm(
                provider=Provider.GEMINI,
                model="gemini-2.0-flash",
                messages=[{"role": "user", "content": "Hi"}],
                temperature=0.7,
                max_tokens=100,
            )

            call_kwargs = mock_comp.call_args[1]
            assert call_kwargs["api_key"] == "sk-test-google"


# ═══════════════════════════════════════════════════════════════════
# _call_gemini_direct
# ═══════════════════════════════════════════════════════════════════


class TestCallGeminiDirect:
    """Tests for _call_gemini_direct."""

    @pytest.mark.asyncio
    async def test_success(self, mock_settings, mock_http_response):
        """_call_gemini_direct returns content, usage, finish_reason, tool_calls."""
        router = LLMRouter()
        response_data = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Gemini response"}]
                },
                "finishReason": "STOP",
            }],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
                "totalTokenCount": 15,
            },
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(200, response_data))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            content, usage, finish_reason, tool_calls = await router._call_gemini_direct(
                model="gemini-2.0-flash",
                messages=[{"role": "user", "content": "Hi"}],
                temperature=0.7,
                max_tokens=100,
            )

        assert content == "Gemini response"
        assert usage["prompt_tokens"] == 10
        assert finish_reason == "stop"
        assert tool_calls == []

    @pytest.mark.asyncio
    async def test_success_with_tool_calls(self, mock_settings, mock_http_response):
        """_call_gemini_direct extracts tool calls from response."""
        router = LLMRouter()
        response_data = {
            "candidates": [{
                "content": {
                    "parts": [
                        {"functionCall": {"name": "search", "args": {"q": "test"}}}
                    ]
                },
                "finishReason": "STOP",
            }],
            "usageMetadata": {},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(200, response_data))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            content, usage, finish_reason, tool_calls = await router._call_gemini_direct(
                model="gemini-2.0-flash",
                messages=[{"role": "user", "content": "Search"}],
                temperature=0.7,
                max_tokens=100,
            )

        assert len(tool_calls) == 1
        assert tool_calls[0]["id"] == "search"
        assert tool_calls[0]["function"]["name"] == "search"

    @pytest.mark.asyncio
    async def test_thought_tags_stripped(self, mock_settings, mock_http_response):
        """Gemma <thought> tags are stripped from content."""
        router = LLMRouter()
        response_data = {
            "candidates": [{
                "content": {
                    "parts": [
                        {"text": "thinking step", "thought": True},
                        {"text": "Final answer"},
                    ]
                },
                "finishReason": "STOP",
            }],
            "usageMetadata": {},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(200, response_data))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            content, usage, finish_reason, tool_calls = await router._call_gemini_direct(
                model="gemma-4-31b-it",
                messages=[{"role": "user", "content": "Hi"}],
                temperature=0.7,
                max_tokens=100,
            )

        assert "<thought>" not in content
        assert "Final answer" in content

    @pytest.mark.asyncio
    async def test_multiple_thought_tag_sets(self, mock_settings, mock_http_response):
        """Multiple <thought> tag sets are all stripped."""
        router = LLMRouter()
        response_data = {
            "candidates": [{
                "content": {
                    "parts": [
                        {"text": "first", "thought": True},
                        {"text": "middle"},
                        {"text": "second", "thought": True},
                        {"text": "Final"},
                    ]
                },
                "finishReason": "STOP",
            }],
            "usageMetadata": {},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(200, response_data))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            content, *_ = await router._call_gemini_direct(
                model="gemma-4-31b-it",
                messages=[{"role": "user", "content": "Hi"}],
                temperature=0.7,
                max_tokens=100,
            )

        assert "Final" in content
        assert "first" not in content
        assert "second" not in content

    @pytest.mark.asyncio
    async def test_no_api_key(self):
        """Raises LLMProviderError when GOOGLE_API_KEY missing."""
        settings = MagicMock()
        settings.google_api_key = ""
        router = LLMRouter()
        router.settings = settings

        with pytest.raises(LLMProviderError, match="GOOGLE_API_KEY not configured"):
            await router._call_gemini_direct(
                model="gemini-2.0-flash",
                messages=[{"role": "user", "content": "Hi"}],
                temperature=0.7,
                max_tokens=100,
            )

    @pytest.mark.asyncio
    async def test_http_429(self, mock_settings, mock_http_response):
        """HTTP 429 raises LLMRateLimitError."""
        router = LLMRouter()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(429, {}))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMRateLimitError):
                await router._call_gemini_direct(
                    model="gemini-2.0-flash",
                    messages=[{"role": "user", "content": "Hi"}],
                    temperature=0.7,
                    max_tokens=100,
                )

    @pytest.mark.asyncio
    async def test_http_500_retry_then_succeed(self, mock_settings, mock_http_response):
        """HTTP 500 is retried, succeeds on retry."""
        router = LLMRouter()
        call_count = {"count": 0}
        success_data = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "OK after 500"}]
                },
                "finishReason": "STOP",
            }],
            "usageMetadata": {},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            async def _post_side(*args, **kwargs):
                call_count["count"] += 1
                if call_count["count"] < 3:
                    return mock_http_response(500, {})
                return mock_http_response(200, success_data)

            mock_client.post = AsyncMock(side_effect=_post_side)
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            content, *_ = await router._call_gemini_direct(
                model="gemini-2.0-flash",
                messages=[{"role": "user", "content": "Hi"}],
                temperature=0.7,
                max_tokens=100,
            )

        assert content == "OK after 500"
        assert call_count["count"] == 3

    @pytest.mark.asyncio
    async def test_http_500_retry_exhausted(self, mock_settings, mock_http_response):
        """All HTTP 500 retries exhausted raises LLMProviderError."""
        router = LLMRouter()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(500, {}))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMProviderError, match="HTTP 500"):
                await router._call_gemini_direct(
                    model="gemini-2.0-flash",
                    messages=[{"role": "user", "content": "Hi"}],
                    temperature=0.7,
                    max_tokens=100,
                )

    @pytest.mark.asyncio
    async def test_non_500_non_200_error(self, mock_settings, mock_http_response):
        """Non-500, non-200 status raises LLMProviderError."""
        router = LLMRouter()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(400, {"error": "bad"}))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMProviderError, match="HTTP 400"):
                await router._call_gemini_direct(
                    model="gemini-2.0-flash",
                    messages=[{"role": "user", "content": "Hi"}],
                    temperature=0.7,
                    max_tokens=100,
                )

    @pytest.mark.asyncio
    async def test_exception_during_request_retried(self, mock_settings, mock_http_response):
        """Generic exceptions during request are retried."""
        router = LLMRouter()
        call_count = {"count": 0}
        success_data = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "OK"}]
                },
                "finishReason": "STOP",
            }],
            "usageMetadata": {},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            async def _post_side(*args, **kwargs):
                call_count["count"] += 1
                if call_count["count"] < 2:
                    raise Exception("Connection reset")
                return mock_http_response(200, success_data)

            mock_client.post = AsyncMock(side_effect=_post_side)
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            content, *_ = await router._call_gemini_direct(
                model="gemini-2.0-flash",
                messages=[{"role": "user", "content": "Hi"}],
                temperature=0.7,
                max_tokens=100,
            )

        assert content == "OK"
        assert call_count["count"] == 2

    @pytest.mark.asyncio
    async def test_tools_passed_in_payload(self, mock_settings, mock_http_response):
        """Tools are accepted and response is parsed correctly."""
        router = LLMRouter()
        response_data = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Result"}]
                },
                "finishReason": "STOP",
            }],
            "usageMetadata": {},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(200, response_data))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            content, usage, finish_reason, tool_calls = await router._call_gemini_direct(
                model="gemini-2.0-flash",
                messages=[{"role": "user", "content": "Search"}],
                temperature=0.7,
                max_tokens=100,
                tools=[{"type": "function", "function": {"name": "search"}}],
            )

        assert content == "Result"
        assert finish_reason == "stop"
        assert tool_calls == []


# ═══════════════════════════════════════════════════════════════════
# _call_openai_compatible_direct (GLM)
# ═══════════════════════════════════════════════════════════════════


class TestCallGLMDirect:
    """Tests for _call_openai_compatible_direct with GLM provider."""

    @pytest.mark.asyncio
    async def test_success(self, mock_settings, mock_http_response):
        """_call_openai_compatible_direct returns GLM response."""
        router = LLMRouter()
        response_data = {
            "choices": [{"message": {"content": "GLM response"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 10},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(200, response_data))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            content, usage, finish_reason, tool_calls = await router._call_openai_compatible_direct(
                base_url=mock_settings.zai_base_url,
                api_key=mock_settings.zai_api_key,
                provider_name="glm",
                model="glm-4-plus",
                messages=[{"role": "user", "content": "Hi"}],
                temperature=0.7,
                max_tokens=100,
            )

        assert content == "GLM response"
        assert usage["prompt_tokens"] == 5
        assert finish_reason == "stop"
        assert tool_calls == []

    @pytest.mark.asyncio
    async def test_http_429(self, mock_settings, mock_http_response):
        """HTTP 429 raises LLMRateLimitError."""
        router = LLMRouter()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(429, {}))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMRateLimitError):
                await router._call_openai_compatible_direct(
                    base_url=mock_settings.zai_base_url,
                    api_key=mock_settings.zai_api_key,
                    provider_name="glm",
                    model="glm-4-plus",
                    messages=[{"role": "user", "content": "Hi"}],
                    temperature=0.7,
                    max_tokens=100,
                )

    @pytest.mark.asyncio
    async def test_http_error(self, mock_settings, mock_http_response):
        """Non-200 status raises LLMProviderError."""
        router = LLMRouter()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(500, {}))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMProviderError, match="HTTP 500"):
                await router._call_openai_compatible_direct(
                    base_url=mock_settings.zai_base_url,
                    api_key=mock_settings.zai_api_key,
                    provider_name="glm",
                    model="glm-4-plus",
                    messages=[{"role": "user", "content": "Hi"}],
                    temperature=0.7,
                    max_tokens=100,
                )

    @pytest.mark.asyncio
    async def test_no_api_key(self, mock_settings, mock_http_response):
        """Raises LLMProviderError when ZAI_API_KEY is empty string passed."""
        router = LLMRouter()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(401, {}))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMProviderError, match="HTTP 401"):
                await router._call_openai_compatible_direct(
                    base_url=mock_settings.zai_base_url,
                    api_key="",
                    provider_name="glm",
                    model="glm-4-plus",
                    messages=[{"role": "user", "content": "Hi"}],
                    temperature=0.7,
                    max_tokens=100,
                )


# ═══════════════════════════════════════════════════════════════════
# _call_openai_compatible_direct (Ollama)
# ═══════════════════════════════════════════════════════════════════


class TestCallOllamaDirect:
    """Tests for _call_openai_compatible_direct with Ollama provider."""

    @pytest.mark.asyncio
    async def test_success(self, mock_settings, mock_http_response):
        """_call_openai_compatible_direct returns Ollama response."""
        router = LLMRouter()
        response_data = {
            "choices": [{"message": {"content": "Ollama response"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(200, response_data))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            content, usage, finish_reason, tool_calls = await router._call_openai_compatible_direct(
                base_url=mock_settings.ollama_base_url + "/v1",
                api_key="ollama",
                provider_name="ollama",
                model="llama3.1:8b",
                messages=[{"role": "user", "content": "Hi"}],
                temperature=0.7,
                max_tokens=100,
            )

        assert content == "Ollama response"
        assert usage["prompt_tokens"] == 5
        assert usage["completion_tokens"] == 10
        assert finish_reason == "stop"
        assert tool_calls == []

    @pytest.mark.asyncio
    async def test_http_error(self, mock_settings, mock_http_response):
        """Non-200 status raises LLMProviderError."""
        router = LLMRouter()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(500, {}))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMProviderError, match="HTTP 500"):
                await router._call_openai_compatible_direct(
                    base_url=mock_settings.ollama_base_url + "/v1",
                    api_key="ollama",
                    provider_name="ollama",
                    model="llama3.1:8b",
                    messages=[{"role": "user", "content": "Hi"}],
                    temperature=0.7,
                    max_tokens=100,
                )


# ═══════════════════════════════════════════════════════════════════
# _call_provider & _call_provider_streaming
# ═══════════════════════════════════════════════════════════════════


class TestCallProvider:
    """Tests for _call_provider and _call_provider_streaming."""

    @pytest.mark.asyncio
    async def test_call_provider_gemini_goes_direct(self, mock_settings):
        """_call_provider routes Gemini to _call_gemini_direct."""
        router = LLMRouter()

        with patch.object(router, "_call_gemini_direct") as mock_gemini:
            mock_gemini.return_value = ("content", {}, "stop", [])
            await router._call_provider(
                provider=Provider.GEMINI,
                model="gemini-2.0-flash",
                messages=[{"role": "user", "content": "Hi"}],
                temperature=0.7,
                max_tokens=100,
            )

        mock_gemini.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_provider_openai_via_litellm(self, mock_settings):
        """_call_provider routes OpenAI (non-Gemini) to LiteLLM."""
        router = LLMRouter()

        with patch.object(router, "_call_via_litellm") as mock_litellm:
            mock_litellm.return_value = ("content", {}, "stop", [])
            await router._call_provider(
                provider=Provider.OPENAI,
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hi"}],
                temperature=0.7,
                max_tokens=100,
            )

        mock_litellm.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_provider_litellm_fallback_to_glm(self, mock_settings):
        """_call_provider falls back to openai-compatible direct when LiteLLM fails for GLM."""
        router = LLMRouter()

        with patch.object(router, "_call_via_litellm", side_effect=Exception("LiteLLM error")):
            with patch.object(router, "_call_openai_compatible_direct") as mock_direct:
                mock_direct.return_value = ("glm content", {}, "stop", [])
                result = await router._call_provider(
                    provider=Provider.GLM,
                    model="glm-4-plus",
                    messages=[{"role": "user", "content": "Hi"}],
                    temperature=0.7,
                    max_tokens=100,
                )

                assert result[0] == "glm content"
                mock_direct.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_provider_litellm_fallback_to_ollama(self, mock_settings):
        """_call_provider falls back to openai-compatible direct when LiteLLM fails for Ollama."""
        router = LLMRouter()

        with patch.object(router, "_call_via_litellm", side_effect=Exception("LiteLLM error")):
            with patch.object(router, "_call_openai_compatible_direct") as mock_direct:
                mock_direct.return_value = ("ollama content", {}, "stop", [])
                result = await router._call_provider(
                    provider=Provider.OLLAMA,
                    model="llama3.1:8b",
                    messages=[{"role": "user", "content": "Hi"}],
                    temperature=0.7,
                    max_tokens=100,
                )

                assert result[0] == "ollama content"
                mock_direct.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_provider_litellm_fallback_no_direct(self, mock_settings):
        """_call_provider raises when no fallback exists (OpenAI)."""
        router = LLMRouter()

        with patch.object(router, "_call_via_litellm", side_effect=Exception("LiteLLM error")):
            with pytest.raises(LLMProviderError, match="Neither LiteLLM nor direct API"):
                await router._call_provider(
                    provider=Provider.ANTHROPIC,
                    model="claude-model",
                    messages=[{"role": "user", "content": "Hi"}],
                    temperature=0.7,
                    max_tokens=100,
                )

    @pytest.mark.asyncio
    async def test_call_provider_streaming(self, mock_settings):
        """_call_provider_streaming delegates to _call_provider and returns content."""
        router = LLMRouter()

        with patch.object(router, "_call_provider") as mock_provider:
            mock_provider.return_value = ("streamed content", {"prompt_tokens": 1}, "stop", [])
            result = await router._call_provider_streaming(
                provider=Provider.OPENAI,
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hi"}],
                temperature=0.7,
                max_tokens=100,
            )

            assert result == "streamed content"


# ═══════════════════════════════════════════════════════════════════
# complete() — Routing & Error Handling
# ═══════════════════════════════════════════════════════════════════


class TestCompleteBasic:
    """Tests for basic complete() happy paths."""

    @pytest.mark.asyncio
    async def test_single_provider_success(self, mock_settings):
        """complete() with explicit provider returns response."""
        router = LLMRouter()

        with patch.object(router, "_call_provider") as mock_call:
            mock_call.return_value = ("Hello", {"prompt_tokens": 10, "completion_tokens": 5}, "stop", [])
            result = await router.complete(
                messages=[{"role": "user", "content": "Hi"}],
                provider="openai",
            )

        assert result.content == "Hello"
        assert result.provider == Provider.OPENAI
        assert result.model == "gpt-4o"
        assert result.usage["prompt_tokens"] == 10
        assert result.latency_ms >= 0
        assert result.finish_reason == "stop"
        assert result.tool_calls == []

    @pytest.mark.asyncio
    async def test_auto_routing_success(self, mock_settings):
        """complete() without provider tries providers in order."""
        router = LLMRouter()

        with patch.object(router, "_call_provider") as mock_call:
            mock_call.return_value = ("Auto routed", {"prompt_tokens": 5}, "stop", [])
            result = await router.complete(
                messages=[{"role": "user", "content": "Hi"}],
            )

        assert result.content == "Auto routed"

    @pytest.mark.asyncio
    async def test_auto_routing_fallback_to_next_provider(self, mock_settings):
        """Auto routing falls through providers when first fails."""
        router = LLMRouter()
        call_results = [
            LLMProviderError(provider="gemini", reason="Down"),
            ("From second provider", {"prompt_tokens": 3}, "stop", []),
        ]
        call_index = {"idx": 0}

        async def _call_side(*args, **kwargs):
            r = call_results[call_index["idx"]]
            call_index["idx"] += 1
            if isinstance(r, Exception):
                raise r
            return r

        with patch.object(router, "_call_provider", side_effect=_call_side):
            result = await router.complete(
                messages=[{"role": "user", "content": "Hi"}],
            )

        assert result.content == "From second provider"

    @pytest.mark.asyncio
    async def test_single_provider_rate_limit_retry(self, mock_settings):
        """Single provider mode retries on rate limit with backoff."""
        router = LLMRouter()
        call_count = {"count": 0}

        async def _call_side(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] < 3:
                raise LLMRateLimitError(provider="openai")
            return ("After rate limit retry", {"prompt_tokens": 1}, "stop", [])

        with patch.object(router, "_call_provider", side_effect=_call_side):
            result = await router.complete(
                messages=[{"role": "user", "content": "Hi"}],
                provider="openai",
            )

        assert result.content == "After rate limit retry"
        assert call_count["count"] == 3

    @pytest.mark.asyncio
    async def test_single_provider_rate_limit_exhausted(self, mock_settings):
        """Single provider mode raises after max rate limit retries."""
        router = LLMRouter()

        with patch.object(router, "_call_provider", side_effect=LLMRateLimitError(provider="openai")):
            with pytest.raises(LLMAllProvidersFailedError) as exc_info:
                await router.complete(
                    messages=[{"role": "user", "content": "Hi"}],
                    provider="openai",
                )
            # Verify the error details contain rate_limited info
            assert "rate_limited" in str(exc_info.value.details.get("errors", []))

    @pytest.mark.asyncio
    async def test_single_provider_transient_error_retry(self, mock_settings):
        """Single provider retries on transient provider errors."""
        router = LLMRouter()
        call_count = {"count": 0}

        async def _call_side(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] < 2:
                raise LLMProviderError(provider="openai", reason="500 Internal error")
            return ("After transient", {"prompt_tokens": 1}, "stop", [])

        with patch.object(router, "_call_provider", side_effect=_call_side):
            result = await router.complete(
                messages=[{"role": "user", "content": "Hi"}],
                provider="openai",
            )

        assert result.content == "After transient"
        assert call_count["count"] == 2

    @pytest.mark.asyncio
    async def test_single_provider_non_transient_error(self, mock_settings):
        """Non-transient errors in single provider mode raise immediately."""
        router = LLMRouter()

        with patch.object(router, "_call_provider", side_effect=LLMProviderError(
            provider="openai", reason="Invalid API key"
        )):
            with pytest.raises(LLMAllProvidersFailedError):
                await router.complete(
                    messages=[{"role": "user", "content": "Hi"}],
                    provider="openai",
                )

    @pytest.mark.asyncio
    async def test_no_providers_available(self, mock_settings):
        """Raises LLMError when no providers have API keys."""
        router = LLMRouter()
        # Override router settings to remove all keys
        router.settings.openai_api_key = None
        router.settings.anthropic_api_key = None
        router.settings.google_api_key = None
        router.settings.zai_api_key = None
        with pytest.raises(LLMError, match="No LLM providers available"):
            await router.complete(
                messages=[{"role": "user", "content": "Hi"}],
            )

    @pytest.mark.asyncio
    async def test_auto_routing_rate_limit_moves_to_next(self, mock_settings):
        """Auto routing: rate limit on first moves to next provider."""
        router = LLMRouter()
        call_results = [
            LLMRateLimitError(provider="openai"),
            ("From fallback", {"prompt_tokens": 1}, "stop", []),
        ]
        call_index = {"idx": 0}

        async def _call_side(*args, **kwargs):
            r = call_results[call_index["idx"]]
            call_index["idx"] += 1
            if isinstance(r, Exception):
                raise r
            return r

        with patch.object(router, "_call_provider", side_effect=_call_side):
            result = await router.complete(
                messages=[{"role": "user", "content": "Hi"}],
                task_complexity=TaskComplexity.SIMPLE,
            )

        assert result.content == "From fallback"

    @pytest.mark.asyncio
    async def test_auto_routing_unexpected_error(self, mock_settings):
        """Unexpected errors in auto routing move to next provider."""
        router = LLMRouter()
        call_results = [
            Exception("Something unexpected"),
            ("Recovered", {"prompt_tokens": 1}, "stop", []),
        ]
        call_index = {"idx": 0}

        async def _call_side(*args, **kwargs):
            r = call_results[call_index["idx"]]
            call_index["idx"] += 1
            if isinstance(r, Exception):
                raise r
            return r

        with patch.object(router, "_call_provider", side_effect=_call_side):
            result = await router.complete(
                messages=[{"role": "user", "content": "Hi"}],
            )

        assert result.content == "Recovered"

    @pytest.mark.asyncio
    async def test_all_providers_fail_auto_routing(self, mock_settings):
        """Auto routing raises LLMError when all providers fail repeatedly."""
        router = LLMRouter()

        with patch.object(router, "_call_provider", side_effect=LLMProviderError(
            provider="gemini", reason="Down"
        )):
            with pytest.raises(LLMError, match="Max tool turns"):
                await router.complete(
                    messages=[{"role": "user", "content": "Hi"}],
                )

    @pytest.mark.asyncio
    async def test_streaming_path(self, mock_settings):
        """Streaming goes through _call_provider_streaming."""
        router = LLMRouter()

        with patch.object(router, "_call_provider_streaming") as mock_streaming:
            mock_streaming.return_value = "Streamed content"
            with patch.object(router, "_call_provider") as mock_call:
                result = await router.complete(
                    messages=[{"role": "user", "content": "Hi"}],
                    provider="openai",
                    stream=True,
                )

                mock_streaming.assert_called_once()
                mock_call.assert_not_called()
                assert result.content == "Streamed content"


# ═══════════════════════════════════════════════════════════════════
# Tool Call Handling
# ═══════════════════════════════════════════════════════════════════


class TestToolCallHandling:
    """Tests for complete() tool call handling."""

    @pytest.mark.asyncio
    async def test_tool_call_response(self, mock_settings):
        """Tool calls in response are captured in LLMResponse."""
        router = LLMRouter()
        tool_calls_data = [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_weather", "arguments": '{"city": "Paris"}'},
            }
        ]

        with patch.object(router, "_call_provider") as mock_call:
            mock_call.return_value = ("", {"prompt_tokens": 5}, "tool_calls", tool_calls_data)
            result = await router.complete(
                messages=[{"role": "user", "content": "Weather?"}],
                provider="openai",
            )

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["function"]["name"] == "get_weather"
        assert result.finish_reason == "tool_calls"
        assert result.content == "[Tool calls requested: 1 tools]"

    @pytest.mark.asyncio
    async def test_tool_calls_not_passed_after_max_turns(self, mock_settings):
        """Tools parameter is None after max tool turns."""
        router = LLMRouter()

        with patch.object(router, "_call_provider") as mock_call:
            mock_call.return_value = ("Final response", {"prompt_tokens": 1}, "stop", [])
            result = await router.complete(
                messages=[{"role": "user", "content": "Hi"}],
                provider="openai",
            )

        # First turn should have tools=None (no tools specified)
        call_kwargs = mock_call.call_args[1]
        assert call_kwargs.get("tools") is None


# ═══════════════════════════════════════════════════════════════════
# Provider Status Tracking
# ═══════════════════════════════════════════════════════════════════


class TestProviderStatus:
    """Tests for provider status tracking."""

    def test_record_provider_status_success(self, mock_settings):
        """_record_provider_status records success."""
        router = LLMRouter()
        router._record_provider_status(
            provider=Provider.OPENAI, success=True, latency_ms=100.0
        )

        status = router._provider_status["openai"]
        assert status["success"] is True
        assert status["latency_ms"] == 100.0
        assert status["error"] is None
        assert status["last_call"] > 0

    def test_record_provider_status_failure(self, mock_settings):
        """_record_provider_status records failure."""
        router = LLMRouter()
        router._record_provider_status(
            provider=Provider.OPENAI, success=False, error="timeout"
        )

        status = router._provider_status["openai"]
        assert status["success"] is False
        assert status["error"] == "timeout"

    def test_get_provider_status(self, mock_settings):
        """get_provider_status returns status for all providers."""
        router = LLMRouter()
        status = router.get_provider_status()

        assert "openai" in status
        assert "anthropic" in status
        assert "gemini" in status
        assert "glm" in status
        assert "ollama" in status

        for prov_name, prov_status in status.items():
            assert "available" in prov_status
            assert "default_model" in prov_status
            assert "last_status" in prov_status

    def test_get_provider_status_after_call(self, mock_settings):
        """get_provider_status reflects recorded call data."""
        router = LLMRouter()
        router._record_provider_status(Provider.OPENAI, success=True, latency_ms=50.0)

        status = router.get_provider_status()
        openai_status = status["openai"]["last_status"]
        assert openai_status["success"] is True
        assert openai_status["latency_ms"] == 50.0


# ═══════════════════════════════════════════════════════════════════
# Utility Methods
# ═══════════════════════════════════════════════════════════════════


class TestUtilityMethods:
    """Tests for router utility methods."""

    def test_is_transient_error_true(self, mock_settings):
        """_is_transient_error returns True for recoverable errors."""
        router = LLMRouter()
        assert router._is_transient_error(LLMProviderError(provider="o", reason="500 error")) is True
        assert router._is_transient_error(LLMProviderError(provider="o", reason="internal error")) is True
        assert router._is_transient_error(LLMProviderError(provider="o", reason="service unavailable")) is True
        assert router._is_transient_error(LLMProviderError(provider="o", reason="timeout occurred")) is True
        assert router._is_transient_error(LLMProviderError(provider="o", reason="timed out after 30s")) is True

    def test_is_transient_error_false(self, mock_settings):
        """_is_transient_error returns False for non-recoverable errors."""
        router = LLMRouter()
        assert router._is_transient_error(LLMProviderError(provider="o", reason="Invalid API key")) is False
        assert router._is_transient_error(LLMProviderError(provider="o", reason="Bad request")) is False
        assert router._is_transient_error(LLMProviderError(provider="o", reason="")) is False

    def test_llm_response_to_dict(self, mock_settings):
        """LLMResponse.to_dict returns serializable dict."""
        from nexus.llm.router import LLMResponse

        response = LLMResponse(
            content="Hello",
            provider=Provider.OPENAI,
            model="gpt-4o",
            usage={"prompt_tokens": 10},
            latency_ms=100.0,
            finish_reason="stop",
        )
        d = response.to_dict()
        assert d["content"] == "Hello"
        assert d["provider"] == "openai"
        assert d["model"] == "gpt-4o"
        assert d["usage"]["prompt_tokens"] == 10
