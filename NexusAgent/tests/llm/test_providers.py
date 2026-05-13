"""
Tests for all 5 LLM providers: Anthropic, Gemini, GLM, Ollama, OpenAI.

Tests cover init, get_stats, complete (LiteLLM + direct paths),
stream, rate limit handling, and provider-specific edge cases.

No real API calls are ever made — all external dependencies are mocked.
"""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexus.core.exceptions import LLMProviderError, LLMRateLimitError


# ═══════════════════════════════════════════════════════════════════
# 1. AnthropicProvider
# ═══════════════════════════════════════════════════════════════════


class TestAnthropicProvider:
    """Tests for AnthropicProvider."""

    def test_init(self, mock_settings):
        """Provider initialises with default values."""
        from nexus.llm.providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider()
        assert provider.name == "anthropic"
        assert provider._call_count == 0
        assert provider._total_cost == 0.0
        assert provider._last_error is None
        assert provider.is_available is True

    def test_init_no_api_key(self):
        """Provider reports unavailable when key is missing."""
        from nexus.llm.providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider()
        # Simulate missing API key regardless of module-level get_settings
        provider.settings.anthropic_api_key = None
        assert provider.is_available is False

    def test_get_stats(self, mock_settings):
        """get_stats returns expected keys and initial values."""
        from nexus.llm.providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider()
        stats = provider.get_stats()
        assert stats["provider"] == "anthropic"
        assert stats["available"] is True
        assert stats["call_count"] == 0
        assert stats["total_cost_usd"] == 0.0
        assert stats["last_error"] is None
        assert "claude-3-5-sonnet-20241022" in stats["models"]

    @pytest.mark.asyncio
    async def test_complete_via_litellm(self, mock_settings, mock_litellm_response):
        """complete() via LiteLLM returns structured AnthropicResponse."""
        from nexus.llm.providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider()

        with patch("litellm.completion", return_value=mock_litellm_response):
            result = await provider.complete(
                messages=[{"role": "user", "content": "Hello"}],
                model="claude-3-5-sonnet-20241022",
            )

        assert result.content == "Hello from LiteLLM!"
        assert result.model == "claude-3-5-sonnet-20241022"
        assert result.finish_reason == "stop"
        assert result.usage["prompt_tokens"] == 10
        assert result.usage["completion_tokens"] == 20
        assert result.usage["total_tokens"] == 30
        assert result.latency_ms >= 0
        assert result.cost_usd >= 0

    @pytest.mark.asyncio
    async def test_complete_via_litellm_with_system_message(self, mock_settings, mock_litellm_response):
        """complete() passes system message to LiteLLM."""
        from nexus.llm.providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider()

        with patch("litellm.completion", return_value=mock_litellm_response) as mock_comp:
            result = await provider.complete(
                messages=[{"role": "user", "content": "Hi"}],
                system="You are helpful",
            )

        # Verify system param was passed
        call_kwargs = mock_comp.call_args[1]
        assert call_kwargs["model"] == "anthropic/claude-3-5-sonnet-20241022"
        assert call_kwargs["system"] == "You are helpful"

    @pytest.mark.asyncio
    async def test_complete_via_direct(self, mock_settings, mock_http_response):
        """complete() falls through to direct HTTP when LiteLLM raises generic error."""
        from nexus.llm.providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider()
        anthropic_response = {
            "content": [{"text": "Hello from direct!"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "stop_reason": "end_turn",
        }

        # Make LiteLLM raise a generic error -> triggers _call_direct fallback
        with patch.object(provider, "_call_via_litellm", side_effect=RuntimeError("LiteLLM down")):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(
                    return_value=mock_http_response(200, anthropic_response)
                )
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                result = await provider.complete(
                    messages=[{"role": "user", "content": "Hello"}],
                )

        assert result.content == "Hello from direct!"
        assert result.usage["prompt_tokens"] == 10
        assert result.usage["completion_tokens"] == 5
        assert result.finish_reason == "end_turn"

    @pytest.mark.asyncio
    async def test_complete_litellm_rate_limit_re_raised(self, mock_settings):
        """complete() re-raises LLMRateLimitError from LiteLLM without fallback."""
        from nexus.llm.providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider()

        with patch.object(
            provider, "_call_via_litellm", side_effect=LLMRateLimitError(provider="anthropic")
        ):
            with patch.object(provider, "_call_direct") as mock_direct:
                with pytest.raises(LLMRateLimitError):
                    await provider.complete(messages=[{"role": "user", "content": "Hi"}])
                mock_direct.assert_not_called()

    @pytest.mark.asyncio
    async def test_complete_litellm_provider_error_re_raised(self, mock_settings):
        """complete() re-raises LLMProviderError from LiteLLM without fallback."""
        from nexus.llm.providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider()

        with patch.object(
            provider,
            "_call_via_litellm",
            side_effect=LLMProviderError(provider="anthropic", reason="Bad request"),
        ):
            with patch.object(provider, "_call_direct") as mock_direct:
                with pytest.raises(LLMProviderError):
                    await provider.complete(messages=[{"role": "user", "content": "Hi"}])
                mock_direct.assert_not_called()

    @pytest.mark.asyncio
    async def test_complete_all_fail(self, mock_settings):
        """complete() raises LLMProviderError when both methods fail."""
        from nexus.llm.providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider()

        with patch.object(provider, "_call_via_litellm", side_effect=RuntimeError("LiteLLM down")):
            with patch.object(
                provider,
                "_call_direct",
                side_effect=LLMProviderError(provider="anthropic", reason="Direct down"),
            ):
                with pytest.raises(LLMProviderError):
                    await provider.complete(messages=[{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_litellm_rate_limit(self, mock_settings):
        """_call_via_litellm raises LLMRateLimitError on rate limit keywords."""
        from nexus.llm.providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider()

        with patch("litellm.completion", side_effect=Exception("429 Too Many Requests")):
            with pytest.raises(LLMRateLimitError):
                await provider._call_via_litellm(
                    messages=[{"role": "user", "content": "Hi"}],
                    model="claude-3-5-sonnet-20241022",
                    temperature=0.7,
                    max_tokens=100,
                    top_p=1.0,
                    system=None,
                )

    @pytest.mark.asyncio
    async def test_direct_http_429_raises_rate_limit(self, mock_settings, mock_http_response):
        """Direct HTTP 429 raises LLMRateLimitError."""
        from nexus.llm.providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(429, {}))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMRateLimitError):
                await provider._call_direct(
                    messages=[{"role": "user", "content": "Hi"}],
                    model="claude-3-5-sonnet-20241022",
                    temperature=0.7,
                    max_tokens=100,
                    top_p=1.0,
                    system=None,
                )

    @pytest.mark.asyncio
    async def test_direct_no_api_key(self, mock_settings):
        """_call_direct raises LLMProviderError when API key is missing."""
        from nexus.llm.providers.anthropic_provider import AnthropicProvider

        settings = MagicMock()
        settings.anthropic_api_key = ""
        provider = AnthropicProvider()
        provider.settings = settings

        with pytest.raises(LLMProviderError, match="ANTHROPIC_API_KEY not configured"):
            await provider._call_direct(
                messages=[{"role": "user", "content": "Hi"}],
                model="claude-3-5-sonnet-20241022",
                temperature=0.7,
                max_tokens=100,
                top_p=1.0,
                system=None,
            )

    @pytest.mark.asyncio
    async def test_stream(self, mock_settings, mock_stream_response):
        """stream() yields text chunks from SSE events."""
        from nexus.llm.providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider()
        lines = [
            'data: {"type":"content_block_delta","delta":{"text":"Hello"}}',
            'data: {"type":"content_block_delta","delta":{"text":" World"}}',
        ]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            stream_mock = mock_stream_response(200, lines)
            mock_client.stream = MagicMock(return_value=stream_mock)
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            chunks = []
            async for chunk in provider.stream(
                messages=[{"role": "user", "content": "Hello"}],
            ):
                chunks.append(chunk)

        assert chunks == ["Hello", " World"]

    @pytest.mark.asyncio
    async def test_stream_no_api_key(self):
        """stream() raises LLMProviderError when API key is missing."""
        from nexus.llm.providers.anthropic_provider import AnthropicProvider

        settings = MagicMock()
        settings.anthropic_api_key = ""
        provider = AnthropicProvider()
        provider.settings = settings

        with pytest.raises(LLMProviderError, match="ANTHROPIC_API_KEY not configured"):
            async for _ in provider.stream(
                messages=[{"role": "user", "content": "Hi"}],
            ):
                pass

    @pytest.mark.asyncio
    async def test_stream_http_error(self, mock_settings, mock_stream_response):
        """stream() raises on non-200 HTTP response."""
        from nexus.llm.providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            stream_mock = mock_stream_response(500, [])
            mock_client.stream = MagicMock(return_value=stream_mock)
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMProviderError, match="HTTP 500"):
                async for _ in provider.stream(
                    messages=[{"role": "user", "content": "Hi"}],
                ):
                    pass

    @pytest.mark.asyncio
    async def test_get_stats_after_call(self, mock_settings, mock_litellm_response):
        """get_stats reflects call count and cost after a completion."""
        from nexus.llm.providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider()

        with patch("litellm.completion", return_value=mock_litellm_response):
            await provider.complete(messages=[{"role": "user", "content": "Hi"}])

        stats = provider.get_stats()
        assert stats["call_count"] == 1
        assert stats["total_cost_usd"] > 0
        assert stats["last_error"] is None


# ═══════════════════════════════════════════════════════════════════
# 2. GeminiProvider
# ═══════════════════════════════════════════════════════════════════


class TestGeminiProvider:
    """Tests for GeminiProvider."""

    def test_init(self, mock_settings):
        """Provider initialises with default values."""
        from nexus.llm.providers.gemini_provider import GeminiProvider

        provider = GeminiProvider()
        assert provider.name == "gemini"
        assert provider._call_count == 0
        assert provider._total_cost == 0.0
        assert provider._last_error is None
        assert provider.is_available is True

    def test_init_no_api_key(self):
        """Provider reports unavailable when key is missing."""
        from nexus.llm.providers.gemini_provider import GeminiProvider

        provider = GeminiProvider()
        provider.settings.google_api_key = None
        assert provider.is_available is False

    def test_get_stats(self, mock_settings):
        """get_stats returns expected keys."""
        from nexus.llm.providers.gemini_provider import GeminiProvider

        provider = GeminiProvider()
        stats = provider.get_stats()
        assert stats["provider"] == "gemini"
        assert stats["available"] is True
        assert stats["call_count"] == 0
        assert stats["last_error"] is None
        assert "gemini-2.0-flash" in stats["models"]

    def test_convert_messages_to_gemini(self, mock_settings):
        """Message conversion handles user, assistant, system roles."""
        from nexus.llm.providers.gemini_provider import GeminiProvider

        provider = GeminiProvider()
        messages = [
            {"role": "system", "content": "Be helpful"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = provider._convert_messages_to_gemini(messages)
        assert len(result) == 4  # system → user+model stub + user + model
        assert result[0]["role"] == "user"
        assert "System instruction" in result[0]["parts"][0]["text"]
        assert result[1]["role"] == "model"
        assert result[2]["role"] == "user"
        assert result[3]["role"] == "model"

    @pytest.mark.asyncio
    async def test_complete_via_litellm(self, mock_settings, mock_litellm_response):
        """complete() via LiteLLM returns GeminiResponse."""
        from nexus.llm.providers.gemini_provider import GeminiProvider

        provider = GeminiProvider()

        with patch("litellm.completion", return_value=mock_litellm_response):
            result = await provider.complete(
                messages=[{"role": "user", "content": "Hello"}],
                model="gemini-2.0-flash",
            )

        assert result.content == "Hello from LiteLLM!"
        assert result.model == "gemini-2.0-flash"
        assert result.finish_reason == "stop"
        assert result.usage["prompt_tokens"] == 10

    @pytest.mark.asyncio
    async def test_complete_via_direct(self, mock_settings, mock_http_response):
        """complete() falls through to direct HTTP when LiteLLM fails."""
        from nexus.llm.providers.gemini_provider import GeminiProvider

        provider = GeminiProvider()
        gemini_response = {
            "candidates": [{
                "content": {"parts": [{"text": "Direct response"}], "role": "model"},
                "finishReason": "STOP",
            }],
            "usageMetadata": {
                "promptTokenCount": 5,
                "candidatesTokenCount": 10,
                "totalTokenCount": 15,
            },
        }

        with patch.object(provider, "_call_via_litellm", side_effect=RuntimeError("Boom")):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_http_response(200, gemini_response))
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                result = await provider.complete(
                    messages=[{"role": "user", "content": "Hello"}],
                )

        assert result.content == "Direct response"
        assert result.finish_reason == "STOP"
        assert result.usage["prompt_tokens"] == 5
        assert result.usage["completion_tokens"] == 10

    @pytest.mark.asyncio
    async def test_complete_direct_no_candidates(self, mock_settings, mock_http_response):
        """Direct path returns fallback when no candidates returned."""
        from nexus.llm.providers.gemini_provider import GeminiProvider

        provider = GeminiProvider()
        gemini_response = {"candidates": [], "usageMetadata": {}}

        with patch.object(provider, "_call_via_litellm", side_effect=RuntimeError("Boom")):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_http_response(200, gemini_response))
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                result = await provider.complete(messages=[{"role": "user", "content": "Hi"}])

        assert result.content == "No response generated"
        assert result.finish_reason == "SAFETY"

    @pytest.mark.asyncio
    async def test_complete_direct_with_grounding(self, mock_settings, mock_http_response):
        """Direct path includes grounding tools when enabled."""
        from nexus.llm.providers.gemini_provider import GeminiProvider

        provider = GeminiProvider()
        gemini_response = {
            "candidates": [{"content": {"parts": [{"text": "Grounded response"}]}, "finishReason": "STOP"}],
            "usageMetadata": {},
        }

        with patch.object(provider, "_call_via_litellm", side_effect=RuntimeError("Boom")):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_http_response(200, gemini_response))
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_class.return_value = mock_client

                result = await provider.complete(
                    messages=[{"role": "user", "content": "Search something"}],
                    grounding=True,
                )

                # Verify grounding tool was included in payload
                call_args = mock_client.post.call_args
                payload = call_args[1]["json"]
                assert "tools" in payload
                assert payload["tools"] == [{"google_search": {}}]

    @pytest.mark.asyncio
    async def test_rate_limit_litellm(self, mock_settings):
        """Rate limit keyword in LiteLLM raises LLMRateLimitError."""
        from nexus.llm.providers.gemini_provider import GeminiProvider

        provider = GeminiProvider()

        with patch("litellm.completion", side_effect=Exception("rate limit exceeded")):
            with pytest.raises(LLMRateLimitError):
                await provider._call_via_litellm(
                    messages=[{"role": "user", "content": "Hi"}],
                    model="gemini-2.0-flash",
                    temperature=0.7,
                    max_tokens=100,
                    top_p=0.95,
                )

    @pytest.mark.asyncio
    async def test_rate_limit_direct(self, mock_settings, mock_http_response):
        """Direct HTTP 429 raises LLMRateLimitError."""
        from nexus.llm.providers.gemini_provider import GeminiProvider

        provider = GeminiProvider()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(429, {}))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMRateLimitError):
                await provider._call_direct(
                    messages=[{"role": "user", "content": "Hi"}],
                    model="gemini-2.0-flash",
                    temperature=0.7,
                    max_tokens=100,
                    top_p=0.95,
                    grounding=False,
                )

    @pytest.mark.asyncio
    async def test_direct_no_api_key(self):
        """_call_direct raises when API key is missing."""
        from nexus.llm.providers.gemini_provider import GeminiProvider

        settings = MagicMock()
        settings.google_api_key = ""
        provider = GeminiProvider()
        provider.settings = settings

        with pytest.raises(LLMProviderError, match="GOOGLE_API_KEY not configured"):
            await provider._call_direct(
                messages=[{"role": "user", "content": "Hi"}],
                model="gemini-2.0-flash",
                temperature=0.7,
                max_tokens=100,
                top_p=0.95,
                grounding=False,
            )

    @pytest.mark.asyncio
    async def test_stream(self, mock_settings, mock_stream_response):
        """stream() yields text chunks from Gemini SSE events."""
        from nexus.llm.providers.gemini_provider import GeminiProvider

        provider = GeminiProvider()
        lines = [
            'data: {"candidates":[{"content":{"parts":[{"text":"Hello"}]}}]}',
            'data: {"candidates":[{"content":{"parts":[{"text":" World"}]}}]}',
        ]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            stream_mock = mock_stream_response(200, lines)
            mock_client.stream = MagicMock(return_value=stream_mock)
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            chunks = []
            async for chunk in provider.stream(
                messages=[{"role": "user", "content": "Hello"}],
            ):
                chunks.append(chunk)

        assert chunks == ["Hello", " World"]

    @pytest.mark.asyncio
    async def test_stream_no_api_key(self):
        """stream() raises when API key is missing."""
        from nexus.llm.providers.gemini_provider import GeminiProvider

        settings = MagicMock()
        settings.google_api_key = ""
        provider = GeminiProvider()
        provider.settings = settings

        with pytest.raises(LLMProviderError, match="GOOGLE_API_KEY not configured"):
            async for _ in provider.stream(
                messages=[{"role": "user", "content": "Hi"}],
            ):
                pass

    @pytest.mark.asyncio
    async def test_all_fail(self, mock_settings):
        """complete() raises LLMProviderError when both methods fail."""
        from nexus.llm.providers.gemini_provider import GeminiProvider

        provider = GeminiProvider()

        with patch.object(provider, "_call_via_litellm", side_effect=RuntimeError("LiteLLM down")):
            with patch.object(
                provider,
                "_call_direct",
                side_effect=LLMProviderError(provider="gemini", reason="Direct down"),
            ):
                with pytest.raises(LLMProviderError):
                    await provider.complete(messages=[{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_stats_after_call(self, mock_settings, mock_litellm_response):
        """get_stats reflects call after completion."""
        from nexus.llm.providers.gemini_provider import GeminiProvider

        provider = GeminiProvider()

        with patch("litellm.completion", return_value=mock_litellm_response):
            await provider.complete(messages=[{"role": "user", "content": "Hi"}])

        stats = provider.get_stats()
        assert stats["call_count"] == 1
        assert stats["total_cost_usd"] > 0


# ═══════════════════════════════════════════════════════════════════
# 3. GLMProvider
# ═══════════════════════════════════════════════════════════════════


class TestGLMProvider:
    """Tests for GLMProvider (ZAI API)."""

    def test_init(self, mock_settings):
        """Provider initialises with default values."""
        from nexus.llm.providers.glm_provider import GLMProvider

        provider = GLMProvider()
        assert provider.name == "glm"
        assert provider._call_count == 0
        assert provider._total_cost == 0.0
        assert provider._last_error is None
        assert provider.is_available is True
        assert "bigmodel.cn" in provider.base_url

    def test_init_no_api_key(self):
        """Provider reports unavailable when key is missing."""
        from nexus.llm.providers.glm_provider import GLMProvider

        provider = GLMProvider()
        provider.settings.zai_api_key = None
        assert provider.is_available is False

    def test_get_stats(self, mock_settings):
        """get_stats returns expected keys."""
        from nexus.llm.providers.glm_provider import GLMProvider

        provider = GLMProvider()
        stats = provider.get_stats()
        assert stats["provider"] == "glm"
        assert stats["available"] is True
        assert stats["call_count"] == 0
        assert stats["last_error"] is None
        assert stats["base_url"] == "https://open.bigmodel.cn/api/paas/v4"
        assert "glm-4-plus" in stats["models"]

    @pytest.mark.asyncio
    async def test_complete_success(self, mock_settings, mock_http_response):
        """complete() returns GLMResponse for a successful direct call."""
        from nexus.llm.providers.glm_provider import GLMProvider

        provider = GLMProvider()
        glm_response = {
            "choices": [{
                "message": {"content": "Hello from GLM!"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(200, glm_response))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await provider.complete(
                messages=[{"role": "user", "content": "Hello"}],
                model="glm-4-plus",
            )

        assert result.content == "Hello from GLM!"
        assert result.model == "glm-4-plus"
        assert result.finish_reason == "stop"
        assert result.usage["prompt_tokens"] == 10

    @pytest.mark.asyncio
    async def test_complete_with_tools(self, mock_settings, mock_http_response):
        """complete() passes tools/tool_choice in payload."""
        from nexus.llm.providers.glm_provider import GLMProvider

        provider = GLMProvider()
        glm_response = {
            "choices": [{
                "message": {
                    "content": "",
                    "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": "{}"}}],
                },
                "finish_reason": "tool_calls",
            }],
            "usage": {"prompt_tokens": 5, "completion_tokens": 0, "total_tokens": 5},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(200, glm_response))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await provider.complete(
                messages=[{"role": "user", "content": "What's the weather?"}],
                tools=[{"type": "function", "function": {"name": "get_weather"}}],
                tool_choice="auto",
            )

        # Tool calls should be serialised into content
        assert "tool_calls" in result.content
        assert result.finish_reason == "tool_calls"

    @pytest.mark.asyncio
    async def test_complete_json_mode(self, mock_settings, mock_http_response):
        """complete() sets response_format for json_mode."""
        from nexus.llm.providers.glm_provider import GLMProvider

        provider = GLMProvider()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                return_value=mock_http_response(200, {
                    "choices": [{"message": {"content": '{"key": "value"}'}, "finish_reason": "stop"}],
                    "usage": {},
                })
            )
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await provider.complete(
                messages=[{"role": "user", "content": "Return JSON"}],
                json_mode=True,
            )

        # Verify json_mode was in payload
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["response_format"] == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_complete_no_api_key(self):
        """complete() raises when ZAI_API_KEY is missing."""
        from nexus.llm.providers.glm_provider import GLMProvider

        settings = MagicMock()
        settings.zai_api_key = ""
        provider = GLMProvider()
        provider.settings = settings

        with pytest.raises(LLMProviderError, match="ZAI_API_KEY not configured"):
            await provider.complete(messages=[{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_rate_limit_integer_retry_after(self, mock_settings):
        """Rate limit with integer Retry-After header."""
        from nexus.llm.providers.glm_provider import GLMProvider

        provider = GLMProvider()
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"retry-after": "5"}
        mock_response.text = "Rate limited"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMRateLimitError) as exc_info:
                await provider.complete(messages=[{"role": "user", "content": "Hi"}])

            assert exc_info.value.details.get("retry_after") == 5

    @pytest.mark.asyncio
    async def test_rate_limit_date_retry_after(self, mock_settings):
        """Rate limit with HTTP-date Retry-After header (RFC 7231)."""
        from nexus.llm.providers.glm_provider import GLMProvider
        import datetime

        future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=10)
        date_str = future.strftime("%a, %d %b %Y %H:%M:%S GMT")

        provider = GLMProvider()
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"retry-after": date_str}
        mock_response.text = "Rate limited"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMRateLimitError) as exc_info:
                await provider.complete(messages=[{"role": "user", "content": "Hi"}])

            # retry_after should be a positive integer (parsed from date)
            assert exc_info.value.details.get("retry_after", -1) >= 0

    @pytest.mark.asyncio
    async def test_rate_limit_invalid_retry_after(self, mock_settings):
        """Rate limit with unparseable Retry-After header."""
        from nexus.llm.providers.glm_provider import GLMProvider

        provider = GLMProvider()
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"retry-after": "not-a-number"}
        mock_response.text = "Rate limited"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMRateLimitError) as exc_info:
                await provider.complete(messages=[{"role": "user", "content": "Hi"}])

            # retry_after should be None when parsing fails
            assert exc_info.value.details.get("retry_after") is None

    @pytest.mark.asyncio
    async def test_401_unauthorized(self, mock_settings):
        """HTTP 401 raises LLMProviderError for invalid key."""
        from nexus.llm.providers.glm_provider import GLMProvider

        provider = GLMProvider()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMProviderError, match="Invalid ZAI_API_KEY"):
                await provider.complete(messages=[{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_timeout_error(self, mock_settings):
        """TimeoutException raises LLMProviderError."""
        from nexus.llm.providers.glm_provider import GLMProvider
        import httpx

        provider = GLMProvider()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMProviderError, match="timed out"):
                await provider.complete(messages=[{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_connect_error(self, mock_settings):
        """ConnectError raises LLMProviderError."""
        from nexus.llm.providers.glm_provider import GLMProvider
        import httpx

        provider = GLMProvider()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMProviderError, match="Cannot connect"):
                await provider.complete(messages=[{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_no_choices(self, mock_settings, mock_http_response):
        """Empty choices list raises LLMProviderError."""
        from nexus.llm.providers.glm_provider import GLMProvider

        provider = GLMProvider()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                return_value=mock_http_response(200, {"choices": [], "usage": {}})
            )
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMProviderError, match="No choices"):
                await provider.complete(messages=[{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_stream(self, mock_settings, mock_stream_response):
        """stream() yields text chunks from SSE."""
        from nexus.llm.providers.glm_provider import GLMProvider

        provider = GLMProvider()
        lines = [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" World"}}]}',
            'data: [DONE]',
        ]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            stream_mock = mock_stream_response(200, lines)
            mock_client.stream = MagicMock(return_value=stream_mock)
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            chunks = []
            async for chunk in provider.stream(
                messages=[{"role": "user", "content": "Hello"}],
            ):
                chunks.append(chunk)

        assert chunks == ["Hello", " World"]

    @pytest.mark.asyncio
    async def test_vision(self, mock_settings, mock_http_response):
        """vision() creates multimodal messages and calls complete."""
        from nexus.llm.providers.glm_provider import GLMProvider

        provider = GLMProvider()

        with patch.object(provider, "complete") as mock_complete:
            mock_response = MagicMock()
            mock_response.content = "Vision analysis result"
            mock_complete.return_value = mock_response

            result = await provider.vision(
                prompt="What's in this image?",
                image_url="https://example.com/image.jpg",
            )

            assert result.content == "Vision analysis result"
            # Verify the messages passed to complete contain multimodal content
            call_args = mock_complete.call_args
            messages = call_args[1]["messages"]
            assert len(messages) == 1
            assert messages[0]["role"] == "user"
            assert isinstance(messages[0]["content"], list)
            assert messages[0]["content"][0]["type"] == "text"
            assert messages[0]["content"][1]["type"] == "image_url"

    @pytest.mark.asyncio
    async def test_stats_after_call(self, mock_settings, mock_http_response):
        """get_stats reflects call after completion."""
        from nexus.llm.providers.glm_provider import GLMProvider

        provider = GLMProvider()
        glm_response = {
            "choices": [{"message": {"content": "Hello"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(200, glm_response))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            await provider.complete(messages=[{"role": "user", "content": "Hi"}])

        stats = provider.get_stats()
        assert stats["call_count"] == 1
        assert stats["total_cost_usd"] > 0


# ═══════════════════════════════════════════════════════════════════
# 4. OllamaProvider
# ═══════════════════════════════════════════════════════════════════


class TestOllamaProvider:
    """Tests for OllamaProvider."""

    def test_init(self, mock_settings):
        """Provider initialises with default values."""
        from nexus.llm.providers.ollama_provider import OllamaProvider

        provider = OllamaProvider()
        assert provider.name == "ollama"
        assert provider._call_count == 0
        assert provider._last_error is None
        assert provider.is_available is True  # Always available
        assert "127.0.0.1" in provider.base_url

    def test_get_stats(self, mock_settings):
        """get_stats returns expected keys."""
        from nexus.llm.providers.ollama_provider import OllamaProvider

        provider = OllamaProvider()
        stats = provider.get_stats()
        assert stats["provider"] == "ollama"
        assert stats["available"] is True
        assert stats["call_count"] == 0
        assert stats["last_error"] is None
        assert stats["default_model"] == "llama3.1:8b"
        assert "llama3.1:8b" in stats["known_models"]

    @pytest.mark.asyncio
    async def test_check_connection_success(self, mock_settings, mock_http_response):
        """check_connection returns True when server responds."""
        from nexus.llm.providers.ollama_provider import OllamaProvider

        provider = OllamaProvider()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_http_response(200, {"models": []}))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await provider.check_connection()
            assert result is True

    @pytest.mark.asyncio
    async def test_check_connection_failure(self, mock_settings):
        """check_connection returns False when server is unreachable."""
        from nexus.llm.providers.ollama_provider import OllamaProvider
        import httpx

        provider = OllamaProvider()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await provider.check_connection()
            assert result is False

    @pytest.mark.asyncio
    async def test_list_models_success(self, mock_settings, mock_http_response):
        """list_models returns model list from server."""
        from nexus.llm.providers.ollama_provider import OllamaProvider

        provider = OllamaProvider()
        models_data = {
            "models": [
                {"name": "llama3.1:8b", "size": 4_700_000_000},
                {"name": "mistral:7b", "size": 4_100_000_000},
            ]
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_http_response(200, models_data))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await provider.list_models()
            assert len(result) == 2
            assert result[0]["name"] == "llama3.1:8b"
            assert provider._available_models == ["llama3.1:8b", "mistral:7b"]

    @pytest.mark.asyncio
    async def test_list_models_failure(self, mock_settings):
        """list_models returns empty list on connection error."""
        from nexus.llm.providers.ollama_provider import OllamaProvider
        import httpx

        provider = OllamaProvider()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await provider.list_models()
            assert result == []

    @pytest.mark.asyncio
    async def test_complete_success(self, mock_settings, mock_http_response):
        """complete() returns OllamaResponse for a successful call."""
        from nexus.llm.providers.ollama_provider import OllamaProvider

        provider = OllamaProvider()
        ollama_response = {
            "model": "llama3.1:8b",
            "message": {"content": "Hello from Ollama!"},
            "prompt_eval_count": 10,
            "eval_count": 20,
            "done": True,
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(200, ollama_response))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await provider.complete(
                messages=[{"role": "user", "content": "Hello"}],
                model="llama3.1:8b",
            )

        assert result.content == "Hello from Ollama!"
        assert result.model == "llama3.1:8b"
        assert result.finish_reason == "stop"
        assert result.usage["prompt_tokens"] == 10
        assert result.usage["completion_tokens"] == 20
        assert result.usage["total_tokens"] == 30

    @pytest.mark.asyncio
    async def test_complete_default_model(self, mock_settings, mock_http_response):
        """complete() uses default model from settings when None given."""
        from nexus.llm.providers.ollama_provider import OllamaProvider

        provider = OllamaProvider()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                return_value=mock_http_response(200, {"message": {"content": "OK"}, "done": True})
            )
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await provider.complete(messages=[{"role": "user", "content": "Hi"}])

            # Should default to llama3.1:8b
            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            assert payload["model"] == "llama3.1:8b"

    @pytest.mark.asyncio
    async def test_complete_connect_error(self, mock_settings):
        """ConnectError raises LLMProviderError."""
        from nexus.llm.providers.ollama_provider import OllamaProvider
        import httpx

        provider = OllamaProvider()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMProviderError, match="Cannot connect to Ollama"):
                await provider.complete(messages=[{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_complete_timeout_error(self, mock_settings):
        """TimeoutException raises LLMProviderError."""
        from nexus.llm.providers.ollama_provider import OllamaProvider
        import httpx

        provider = OllamaProvider()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMProviderError, match="timed out"):
                await provider.complete(messages=[{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_complete_http_error(self, mock_settings, mock_http_response):
        """Non-200 HTTP status raises LLMProviderError."""
        from nexus.llm.providers.ollama_provider import OllamaProvider

        provider = OllamaProvider()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(500, {}))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMProviderError, match="HTTP 500"):
                await provider.complete(messages=[{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_stream(self, mock_settings, mock_stream_response):
        """stream() yields text chunks from Ollama NDJSON."""
        from nexus.llm.providers.ollama_provider import OllamaProvider

        provider = OllamaProvider()
        lines = [
            '{"message":{"content":"Hello"},"done":false}',
            '{"message":{"content":" World"},"done":false}',
            '{"message":{"content":""},"done":true}',
        ]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            stream_mock = mock_stream_response(200, lines)
            mock_client.stream = MagicMock(return_value=stream_mock)
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            chunks = []
            async for chunk in provider.stream(
                messages=[{"role": "user", "content": "Hello"}],
            ):
                chunks.append(chunk)

        assert chunks == ["Hello", " World"]

    @pytest.mark.asyncio
    async def test_generate(self, mock_settings, mock_http_response):
        """generate() returns OllamaResponse for single prompt."""
        from nexus.llm.providers.ollama_provider import OllamaProvider

        provider = OllamaProvider()
        gen_response = {
            "model": "llama3.1:8b",
            "response": "Generated text",
            "prompt_eval_count": 5,
            "eval_count": 10,
            "done": True,
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(200, gen_response))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await provider.generate(prompt="Tell me something")

        assert result.content == "Generated text"
        assert result.usage["prompt_tokens"] == 5
        assert result.usage["completion_tokens"] == 10

    @pytest.mark.asyncio
    async def test_pull_model(self, mock_settings, mock_http_response):
        """pull_model returns True on success."""
        from nexus.llm.providers.ollama_provider import OllamaProvider

        provider = OllamaProvider()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(200, {}))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await provider.pull_model("llama3.1:8b")
            assert result is True

    @pytest.mark.asyncio
    async def test_pull_model_failure(self, mock_settings):
        """pull_model returns False on connection error."""
        from nexus.llm.providers.ollama_provider import OllamaProvider
        import httpx

        provider = OllamaProvider()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await provider.pull_model("llama3.1:8b")
            assert result is False

    @pytest.mark.asyncio
    async def test_get_embeddings(self, mock_settings, mock_http_response):
        """get_embeddings returns vector of floats."""
        from nexus.llm.providers.ollama_provider import OllamaProvider

        provider = OllamaProvider()
        emb_response = {"embedding": [0.1, 0.2, 0.3, 0.4]}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(200, emb_response))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await provider.get_embeddings("test prompt")
            assert result == [0.1, 0.2, 0.3, 0.4]

    @pytest.mark.asyncio
    async def test_get_embeddings_connect_error(self, mock_settings):
        """get_embeddings raises on connection error."""
        from nexus.llm.providers.ollama_provider import OllamaProvider
        import httpx

        provider = OllamaProvider()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(LLMProviderError, match="Cannot connect to Ollama"):
                await provider.get_embeddings("test")

    @pytest.mark.asyncio
    async def test_stats_after_call(self, mock_settings, mock_http_response):
        """get_stats reflects call after completion."""
        from nexus.llm.providers.ollama_provider import OllamaProvider

        provider = OllamaProvider()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                return_value=mock_http_response(200, {"message": {"content": "OK"}, "done": True})
            )
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            await provider.complete(messages=[{"role": "user", "content": "Hi"}])

        stats = provider.get_stats()
        assert stats["call_count"] == 1


# ═══════════════════════════════════════════════════════════════════
# 5. OpenAIProvider
# ═══════════════════════════════════════════════════════════════════


class TestOpenAIProvider:
    """Tests for OpenAIProvider."""

    def test_init(self, mock_settings):
        """Provider initialises with default values."""
        from nexus.llm.providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider()
        assert provider.name == "openai"
        assert provider._call_count == 0
        assert provider._total_cost == 0.0
        assert provider._last_error is None
        assert provider.is_available is True

    def test_init_no_api_key(self):
        """Provider reports unavailable when key is missing."""
        from nexus.llm.providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider()
        provider.settings.openai_api_key = None
        assert provider.is_available is False

    def test_get_stats(self, mock_settings):
        """get_stats returns expected keys."""
        from nexus.llm.providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider()
        stats = provider.get_stats()
        assert stats["provider"] == "openai"
        assert stats["available"] is True
        assert stats["call_count"] == 0
        assert stats["last_error"] is None
        assert "gpt-4o" in stats["models"]
        assert "gpt-4o-mini" in stats["models"]

    @pytest.mark.asyncio
    async def test_complete_via_litellm(self, mock_settings, mock_litellm_response):
        """complete() via LiteLLM returns OpenAIResponse."""
        from nexus.llm.providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider()

        with patch("litellm.completion", return_value=mock_litellm_response):
            result = await provider.complete(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-4o",
            )

        assert result.content == "Hello from LiteLLM!"
        assert result.model == "gpt-4o"
        assert result.finish_reason == "stop"
        assert result.usage["prompt_tokens"] == 10
        assert result.usage["completion_tokens"] == 20

    @pytest.mark.asyncio
    async def test_complete_via_litellm_with_json_mode(self, mock_settings, mock_litellm_response):
        """LiteLLM path passes response_format for json_mode."""
        from nexus.llm.providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider()

        with patch("litellm.completion", return_value=mock_litellm_response) as mock_comp:
            await provider.complete(
                messages=[{"role": "user", "content": "Return JSON"}],
                json_mode=True,
            )

            call_kwargs = mock_comp.call_args[1]
            assert call_kwargs["response_format"] == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_complete_via_direct_sdk(self, mock_settings):
        """complete() falls through to direct OpenAI SDK when LiteLLM raises LLMProviderError."""
        from nexus.llm.providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider()

        # Mock the direct SDK client
        mock_direct_response = MagicMock()
        mock_direct_response.choices = [MagicMock()]
        mock_direct_response.choices[0].message.content = "Direct SDK response"
        mock_direct_response.choices[0].finish_reason = "stop"
        mock_direct_response.usage.prompt_tokens = 5
        mock_direct_response.usage.completion_tokens = 15
        mock_direct_response.usage.total_tokens = 20

        with patch.object(provider, "_call_via_litellm", side_effect=LLMProviderError(provider="openai", reason="LiteLLM failed")):
            with patch("openai.AsyncOpenAI") as mock_openai:
                mock_client = AsyncMock()
                mock_client.chat.completions.create = AsyncMock(return_value=mock_direct_response)
                mock_openai.return_value = mock_client

                result = await provider.complete(
                    messages=[{"role": "user", "content": "Hello"}],
                )

        assert result.content == "Direct SDK response"
        assert result.usage["prompt_tokens"] == 5
        assert result.usage["completion_tokens"] == 15

    @pytest.mark.asyncio
    async def test_complete_via_import_error_fallback(self, mock_settings):
        """complete() falls through to direct SDK when LiteLLM raises ImportError."""
        from nexus.llm.providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider()

        mock_direct_response = MagicMock()
        mock_direct_response.choices = [MagicMock()]
        mock_direct_response.choices[0].message.content = "Import fallback response"
        mock_direct_response.choices[0].finish_reason = "stop"
        mock_direct_response.usage.prompt_tokens = 3
        mock_direct_response.usage.completion_tokens = 7
        mock_direct_response.usage.total_tokens = 10

        with patch.object(provider, "_call_via_litellm", side_effect=ImportError("No module litellm")):
            with patch("openai.AsyncOpenAI") as mock_openai:
                mock_client = AsyncMock()
                mock_client.chat.completions.create = AsyncMock(return_value=mock_direct_response)
                mock_openai.return_value = mock_client

                result = await provider.complete(
                    messages=[{"role": "user", "content": "Hello"}],
                )

        assert result.content == "Import fallback response"

    @pytest.mark.asyncio
    async def test_litellm_rate_limit(self, mock_settings):
        """_call_via_litellm raises LLMRateLimitError on rate keywords."""
        from nexus.llm.providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider()

        with patch("litellm.completion", side_effect=Exception("rate limit exceeded")):
            with pytest.raises(LLMRateLimitError):
                await provider._call_via_litellm(
                    messages=[{"role": "user", "content": "Hi"}],
                    model="gpt-4o",
                    temperature=0.7,
                    max_tokens=100,
                    top_p=1.0,
                    frequency_penalty=0.0,
                    presence_penalty=0.0,
                    json_mode=False,
                )

    @pytest.mark.asyncio
    async def test_direct_sdk_rate_limit(self, mock_settings):
        """Direct SDK path raises LLMRateLimitError on rate keywords."""
        from nexus.llm.providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider()

        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(side_effect=Exception("429 rate limit"))
            mock_openai.return_value = mock_client

            with pytest.raises(LLMRateLimitError):
                await provider._call_direct(
                    messages=[{"role": "user", "content": "Hi"}],
                    model="gpt-4o",
                    temperature=0.7,
                    max_tokens=100,
                    top_p=1.0,
                    frequency_penalty=0.0,
                    presence_penalty=0.0,
                    json_mode=False,
                )

    @pytest.mark.asyncio
    async def test_direct_sdk_no_api_key(self):
        """_call_direct raises LLMProviderError when API key is missing."""
        from nexus.llm.providers.openai_provider import OpenAIProvider

        settings = MagicMock()
        settings.openai_api_key = ""
        provider = OpenAIProvider()
        provider.settings = settings

        with pytest.raises(LLMProviderError, match="OPENAI_API_KEY not configured"):
            await provider._call_direct(
                messages=[{"role": "user", "content": "Hi"}],
                model="gpt-4o",
                temperature=0.7,
                max_tokens=100,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0,
                json_mode=False,
            )

    @pytest.mark.asyncio
    async def test_complete_all_fail(self, mock_settings):
        """complete() raises LLMProviderError when both methods fail."""
        from nexus.llm.providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider()

        # _call_via_litellm raises LLMProviderError -> caught -> tries _call_direct
        # _call_direct also raises LLMProviderError -> propagates to caller
        with patch.object(
            provider, "_call_via_litellm",
            side_effect=LLMProviderError(provider="openai", reason="LiteLLM down"),
        ):
            with patch.object(
                provider,
                "_call_direct",
                side_effect=LLMProviderError(provider="openai", reason="Direct down"),
            ):
                with pytest.raises(LLMProviderError):
                    await provider.complete(messages=[{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_stream(self, mock_settings):
        """stream() yields text chunks from OpenAI SDK stream."""
        from nexus.llm.providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider()

        # Create mock streaming chunks
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "Hello"
        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta.content = " World"
        chunk3 = MagicMock()
        chunk3.choices = [MagicMock()]
        chunk3.choices[0].delta.content = None  # Trigger stop condition

        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = AsyncMock()

            async def async_gen():
                for c in [chunk1, chunk2, chunk3]:
                    yield c

            mock_client.chat.completions.create = AsyncMock(return_value=async_gen())
            mock_openai.return_value = mock_client

            chunks = []
            async for chunk in provider.stream(
                messages=[{"role": "user", "content": "Hello"}],
            ):
                chunks.append(chunk)

        assert chunks == ["Hello", " World"]

    @pytest.mark.asyncio
    async def test_stream_no_api_key(self):
        """stream() raises when API key is missing."""
        from nexus.llm.providers.openai_provider import OpenAIProvider

        settings = MagicMock()
        settings.openai_api_key = ""
        provider = OpenAIProvider()
        provider.settings = settings

        with pytest.raises(LLMProviderError, match="OPENAI_API_KEY not configured"):
            async for _ in provider.stream(
                messages=[{"role": "user", "content": "Hi"}],
            ):
                pass

    @pytest.mark.asyncio
    async def test_stream_rate_limit(self, mock_settings):
        """stream() raises LLMRateLimitError on rate limit."""
        from nexus.llm.providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider()

        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("429 rate limit")
            )
            mock_openai.return_value = mock_client

            with pytest.raises(LLMRateLimitError):
                async for _ in provider.stream(
                    messages=[{"role": "user", "content": "Hi"}],
                ):
                    pass

    @pytest.mark.asyncio
    async def test_stats_after_call(self, mock_settings, mock_litellm_response):
        """get_stats reflects call after completion."""
        from nexus.llm.providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider()

        with patch("litellm.completion", return_value=mock_litellm_response):
            await provider.complete(messages=[{"role": "user", "content": "Hi"}])

        stats = provider.get_stats()
        assert stats["call_count"] == 1
        assert stats["total_cost_usd"] > 0
        assert stats["last_error"] is None
