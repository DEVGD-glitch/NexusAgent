"""
Tests for nexus.llm.fallback — FallbackChain, ProviderHealthRecord,
RetryConfig, and FallbackEvent.

Covers init, health tracking, circuit breaker, retry policy,
provider fallback ordering, and error edge cases.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import time

from nexus.core.exceptions import (
    LLMAllProvidersFailedError,
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
)
from nexus.llm.fallback import (
    FallbackChain,
    FallbackEvent,
    ProviderHealth,
    ProviderHealthRecord,
    RetryConfig,
    RetryPolicy,
)


# ═══════════════════════════════════════════════════════════════════
# RetryConfig
# ═══════════════════════════════════════════════════════════════════


class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_default_policy(self):
        """Default retry policy is exponential backoff."""
        config = RetryConfig()
        assert config.policy == RetryPolicy.EXPONENTIAL
        assert config.max_retries == 3
        assert config.base_delay_seconds == 1.0

    def test_get_delay_none(self):
        """NONE policy returns 0 delay."""
        config = RetryConfig(policy=RetryPolicy.NONE)
        assert config.get_delay(0) == 0.0
        assert config.get_delay(5) == 0.0

    def test_get_delay_fixed(self):
        """FIXED policy returns base delay."""
        config = RetryConfig(policy=RetryPolicy.FIXED, base_delay_seconds=2.0)
        assert config.get_delay(0) == 2.0
        assert config.get_delay(10) == 2.0

    def test_get_delay_exponential(self):
        """EXPONENTIAL policy doubles each attempt with cap."""
        config = RetryConfig(
            policy=RetryPolicy.EXPONENTIAL,
            base_delay_seconds=1.0,
            backoff_factor=2.0,
            max_delay_seconds=30.0,
        )
        assert config.get_delay(0) == 1.0
        assert config.get_delay(1) == 2.0
        assert config.get_delay(2) == 4.0
        assert config.get_delay(3) == 8.0
        assert config.get_delay(4) == 16.0
        # Capped at max_delay
        assert config.get_delay(10) == 30.0


# ═══════════════════════════════════════════════════════════════════
# ProviderHealthRecord
# ═══════════════════════════════════════════════════════════════════


class TestProviderHealthRecord:
    """Tests for ProviderHealthRecord."""

    def test_init(self):
        """Record initialises with UNKNOWN status."""
        record = ProviderHealthRecord(provider="openai")
        assert record.provider == "openai"
        assert record.status == ProviderHealth.UNKNOWN
        assert record.consecutive_failures == 0
        assert record.consecutive_successes == 0
        assert record.total_requests == 0

    def test_record_success(self):
        """record_success updates health metrics."""
        record = ProviderHealthRecord(provider="openai")
        record.record_success(latency_ms=100.0)

        assert record.consecutive_successes == 1
        assert record.consecutive_failures == 0
        assert record.total_requests == 1
        assert record.total_successes == 1
        assert record.last_success_time is not None
        assert record.avg_latency_ms == 100.0
        assert record.status == ProviderHealth.DEGRADED

    def test_record_success_becomes_healthy(self):
        """Three consecutive successes → HEALTHY."""
        record = ProviderHealthRecord(provider="openai")
        for _ in range(3):
            record.record_success(latency_ms=50.0)

        assert record.status == ProviderHealth.HEALTHY
        assert record.consecutive_successes == 3

    def test_record_failure(self):
        """record_failure updates health metrics."""
        record = ProviderHealthRecord(provider="openai")
        record.record_failure("API error")

        assert record.consecutive_failures == 1
        assert record.consecutive_successes == 0
        assert record.total_requests == 1
        assert record.total_failures == 1
        assert record.last_error == "API error"
        assert record.last_failure_time is not None
        assert record.status == ProviderHealth.DEGRADED

    def test_record_failure_becomes_unhealthy(self):
        """Three consecutive failures → UNHEALTHY."""
        record = ProviderHealthRecord(provider="openai")
        for _ in range(3):
            record.record_failure("Error")

        assert record.status == ProviderHealth.UNHEALTHY
        assert record.consecutive_failures == 3

    def test_success_resets_failures(self):
        """A success resets consecutive_failures counter."""
        record = ProviderHealthRecord(provider="openai")
        record.record_failure("Error")
        record.record_failure("Error")
        record.record_success(latency_ms=50.0)

        assert record.consecutive_failures == 0
        assert record.consecutive_successes == 1
        assert record.status == ProviderHealth.DEGRADED

    def test_latency_samples_capped(self):
        """Only last 100 latency samples are kept."""
        record = ProviderHealthRecord(provider="openai")
        for i in range(150):
            record.record_success(latency_ms=float(i))

        assert len(record._latency_samples) == 100
        assert record.avg_latency_ms == sum(range(50, 150)) / 100

    def test_to_dict(self):
        """to_dict returns serializable dict."""
        record = ProviderHealthRecord(provider="gemini")
        record.record_success(latency_ms=75.0)
        d = record.to_dict()
        assert d["provider"] == "gemini"
        assert d["status"] == "degraded"
        assert d["total_requests"] == 1
        assert d["total_successes"] == 1
        assert "last_error" in d
        assert d["avg_latency_ms"] == 75.0


# ═══════════════════════════════════════════════════════════════════
# FallbackEvent
# ═══════════════════════════════════════════════════════════════════


class TestFallbackEvent:
    """Tests for FallbackEvent."""

    def test_to_dict(self):
        """to_dict returns serializable dict."""
        event = FallbackEvent(
            from_provider="openai",
            to_provider="anthropic",
            reason="Rate limited",
            task_preview="Analyze data",
        )
        d = event.to_dict()
        assert d["from_provider"] == "openai"
        assert d["to_provider"] == "anthropic"
        assert d["reason"] == "Rate limited"
        assert d["timestamp"] > 0
        assert len(d["task_preview"]) <= 100


# ═══════════════════════════════════════════════════════════════════
# FallbackChain
# ═══════════════════════════════════════════════════════════════════


class TestFallbackChainInit:
    """Tests for FallbackChain initialisation."""

    def test_init_with_providers(self, mock_settings):
        """Chain initialises with given provider list."""
        chain = FallbackChain(providers=["openai", "ollama"])
        assert chain.providers == ["openai", "ollama"]
        assert len(chain._health) == 2
        assert "openai" in chain._health
        assert "ollama" in chain._health

    def test_init_from_settings(self, mock_settings):
        """Chain uses fallback_providers from settings when no list given."""
        chain = FallbackChain()
        assert len(chain.providers) >= 1

    def test_init_default_values(self, mock_settings):
        """Chain has sensible default values."""
        chain = FallbackChain(providers=["openai"])
        assert chain._circuit_breaker_threshold == 3
        assert chain._circuit_breaker_recovery_seconds == 60.0
        assert isinstance(chain._retry_config, RetryConfig)


class TestFallbackChainHealth:
    """Tests for FallbackChain health tracking methods."""

    def test_is_provider_available_ollama_always(self, mock_settings):
        """Ollama is always available."""
        chain = FallbackChain(providers=["ollama"])
        assert chain._is_provider_available("ollama") is True

    def test_is_provider_available_with_key(self, mock_settings):
        """Provider with API key is available."""
        chain = FallbackChain(providers=["openai"])
        assert chain._is_provider_available("openai") is True

    def test_is_provider_available_no_key(self, mock_settings):
        """Provider without API key is not available."""
        # Override the conftest's mock_settings directly on the chain
        chain = FallbackChain(providers=["openai", "anthropic"])
        chain.settings.openai_api_key = None
        chain.settings.anthropic_api_key = None
        chain.settings.google_api_key = None
        chain.settings.zai_api_key = None
        assert chain._is_provider_available("openai") is False
        assert chain._is_provider_available("anthropic") is False

    def test_is_provider_healthy_unknown_is_healthy(self, mock_settings):
        """UNKNOWN health status is considered healthy."""
        chain = FallbackChain(providers=["openai"])
        assert chain._is_provider_healthy("openai") is True

    def test_is_provider_healthy_healthy(self, mock_settings):
        """HEALTHY provider is healthy."""
        chain = FallbackChain(providers=["openai"])
        chain._health["openai"].record_success(latency_ms=10)
        chain._health["openai"].record_success(latency_ms=10)
        chain._health["openai"].record_success(latency_ms=10)
        assert chain._health["openai"].status == ProviderHealth.HEALTHY
        assert chain._is_provider_healthy("openai") is True

    def test_is_provider_healthy_unhealthy_blocked(self, mock_settings):
        """UNHEALTHY provider is NOT healthy (circuit breaker)."""
        chain = FallbackChain(providers=["openai"])
        for _ in range(3):
            chain._health["openai"].record_failure("Error")
        assert chain._health["openai"].status == ProviderHealth.UNHEALTHY
        assert chain._is_provider_healthy("openai") is False

    def test_is_provider_healthy_unhealthy_recovers(self, mock_settings):
        """UNHEALTHY provider recovers after recovery period."""
        chain = FallbackChain(
            providers=["openai"],
            circuit_breaker_recovery_seconds=0.0,  # Immediate recovery
        )
        for _ in range(3):
            chain._health["openai"].record_failure("Error")
        assert chain._health["openai"].status == ProviderHealth.UNHEALTHY

        # Recovery period is 0s, so it should be available
        assert chain._is_provider_healthy("openai") is True

    def test_get_ordered_providers(self, mock_settings):
        """get_ordered_providers excludes unavailable/unhealthy."""
        chain = FallbackChain(providers=["openai", "anthropic", "gemini"])

        # Simulate missing keys by overriding settings on the chain directly
        chain.settings.anthropic_api_key = None
        chain.settings.google_api_key = "key"  # Available but will mark unhealthy

        # Mark gemini as unhealthy
        for _ in range(3):
            chain._health["gemini"].record_failure("Error")

        ordered = chain.get_ordered_providers()
        assert ordered == ["openai"]  # Only openai is both available and healthy


class TestFallbackChainComplete:
    """Tests for FallbackChain.complete()."""

    @pytest.mark.asyncio
    async def test_complete_success_first_provider(self, mock_settings):
        """complete() returns result from first available provider."""
        mock_response = MagicMock()
        mock_response.content = "Success from openai"
        mock_response.model = "gpt-4o"
        mock_response.usage = {"prompt_tokens": 10, "completion_tokens": 5}
        mock_response.latency_ms = 100.0
        mock_response.finish_reason = "stop"

        with patch("nexus.llm.router.LLMRouter") as MockRouter:
            mock_router = AsyncMock()
            mock_router.complete.return_value = mock_response
            MockRouter.return_value = mock_router

            with patch("nexus.llm.fallback.get_observability") as mock_obs:
                mock_obs_instance = MagicMock()
                mock_obs.return_value = mock_obs_instance

                chain = FallbackChain(providers=["openai", "anthropic"])
                result = await chain.complete(
                    messages=[{"role": "user", "content": "Hello"}],
                )

        assert result["status"] == "completed"
        assert result["content"] == "Success from openai"
        assert result["provider"] == "openai"
        assert result["latency_ms"] == 100.0
        assert result["total_latency_ms"] >= 0

        # Health should be updated
        assert chain._health["openai"].total_successes == 1
        assert chain._health["openai"].status == ProviderHealth.DEGRADED

        # Observability should be called
        mock_obs_instance.record_llm_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_fallback_to_next_provider(self, mock_settings):
        """complete() falls through to next provider when first fails."""
        from nexus.llm.fallback import RetryConfig, RetryPolicy

        responses = {
            "openai": None,  # Will raise LLMProviderError
            "anthropic": MagicMock(
                content="Fallback to anthropic",
                model="claude-3-5-sonnet-20241022",
                usage={"prompt_tokens": 5, "completion_tokens": 3},
                latency_ms=150.0,
                finish_reason="stop",
            ),
        }

        with patch("nexus.llm.router.LLMRouter") as MockRouter:
            mock_router = AsyncMock()

            async def _complete_side_effect(*args, **kwargs):
                provider = kwargs.get("provider", "openai")
                if provider == "openai":
                    raise LLMProviderError(provider="openai", reason="Server error")
                resp = responses.get(provider)
                if resp:
                    return resp
                raise LLMProviderError(provider=provider, reason="Unknown")

            mock_router.complete.side_effect = _complete_side_effect
            MockRouter.return_value = mock_router

            with patch("nexus.llm.fallback.get_observability"):
                # Use NONE retry policy so LLMProviderError moves to next provider immediately
                chain = FallbackChain(
                    providers=["openai", "anthropic"],
                    retry_config=RetryConfig(policy=RetryPolicy.NONE, max_retries=0),
                )
                result = await chain.complete(
                    messages=[{"role": "user", "content": "Hello"}],
                )

        assert result["content"] == "Fallback to anthropic"
        assert result["provider"] == "anthropic"

        # Health records updated
        assert chain._health["openai"].total_failures == 1
        assert chain._health["anthropic"].total_successes == 1

        # Fallback event logged
        assert len(chain._fallback_log) == 1
        assert chain._fallback_log[0].from_provider == "openai"
        assert chain._fallback_log[0].to_provider == "anthropic"

    @pytest.mark.asyncio
    async def test_complete_all_providers_fail(self, mock_settings):
        """complete() raises LLMAllProvidersFailedError when all fail."""
        with patch("nexus.llm.router.LLMRouter") as MockRouter:
            mock_router = AsyncMock()
            mock_router.complete.side_effect = LLMProviderError(
                provider="openai", reason="Down"
            )
            MockRouter.return_value = mock_router

            chain = FallbackChain(providers=["openai"])

            with pytest.raises(LLMAllProvidersFailedError):
                await chain.complete(
                    messages=[{"role": "user", "content": "Hello"}],
                )

    @pytest.mark.asyncio
    async def test_complete_empty_chain(self, mock_settings):
        """complete() raises LLMError when provider chain is empty."""
        chain = FallbackChain(providers=["openai", "anthropic"])
        # Override the chain's settings to make all providers unavailable
        chain.settings.openai_api_key = None
        chain.settings.anthropic_api_key = None
        chain.settings.google_api_key = None
        chain.settings.zai_api_key = None

        with pytest.raises(LLMError, match="No LLM providers available"):
            await chain.complete(
                messages=[{"role": "user", "content": "Hello"}],
            )

    @pytest.mark.asyncio
    async def test_complete_with_preferred_provider(self, mock_settings):
        """complete() prefers the specified provider."""
        mock_response = MagicMock()
        mock_response.content = "From preferred"
        mock_response.model = "gpt-4o"
        mock_response.usage = {"prompt_tokens": 1, "completion_tokens": 1}
        mock_response.latency_ms = 50.0
        mock_response.finish_reason = "stop"

        with patch("nexus.llm.router.LLMRouter") as MockRouter:
            mock_router = AsyncMock()
            mock_router.complete.return_value = mock_response
            MockRouter.return_value = mock_router

            with patch("nexus.llm.fallback.get_observability"):
                chain = FallbackChain(providers=["anthropic", "openai"])
                result = await chain.complete(
                    messages=[{"role": "user", "content": "Hello"}],
                    preferred_provider="openai",
                )

        assert result["provider"] == "openai"

    @pytest.mark.asyncio
    async def test_rate_limit_breaks_to_next_provider(self, mock_settings):
        """Rate limit on a provider breaks out of retries and moves to next."""
        with patch("nexus.llm.router.LLMRouter") as MockRouter:
            mock_router = AsyncMock()

            async def _side_effect(*args, **kwargs):
                provider = kwargs.get("provider", "openai")
                if provider == "openai":
                    raise LLMRateLimitError(provider="openai")
                resp = MagicMock(
                    content="From anthropic",
                    model="claude-model",
                    usage={},
                    latency_ms=50.0,
                    finish_reason="stop",
                )
                return resp

            mock_router.complete.side_effect = _side_effect
            MockRouter.return_value = mock_router

            with patch("nexus.llm.fallback.get_observability"):
                chain = FallbackChain(providers=["openai", "anthropic"])
                result = await chain.complete(
                    messages=[{"role": "user", "content": "Hello"}],
                )

        assert result["provider"] == "anthropic"
        assert result["content"] == "From anthropic"

    @pytest.mark.asyncio
    async def test_retry_on_provider_error(self, mock_settings):
        """Provider error is retried per retry config before fallback."""
        call_count = {"count": 0}

        with patch("nexus.llm.router.LLMRouter") as MockRouter:
            mock_router = AsyncMock()

            async def _side_effect(*args, **kwargs):
                call_count["count"] += 1
                if call_count["count"] < 3:
                    raise LLMProviderError(provider="openai", reason="Transient error")
                resp = MagicMock(
                    content="After retries",
                    model="gpt-4o",
                    usage={},
                    latency_ms=50.0,
                    finish_reason="stop",
                )
                return resp

            mock_router.complete.side_effect = _side_effect
            MockRouter.return_value = mock_router

            with patch("nexus.llm.fallback.get_observability"):
                chain = FallbackChain(
                    providers=["openai", "anthropic"],
                    retry_config=MagicMock(
                        max_retries=3,
                        get_delay=lambda a: 0.0,  # No delay for tests
                        policy="exponential",
                    ),
                )
                result = await chain.complete(
                    messages=[{"role": "user", "content": "Hello"}],
                )

        assert result["content"] == "After retries"
        assert call_count["count"] == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_rate_limit(self, mock_settings):
        """Rate limit is NOT retried — moves to next provider immediately."""
        with patch("nexus.llm.router.LLMRouter") as MockRouter:
            mock_router = AsyncMock()
            mock_router.complete.side_effect = LLMRateLimitError(provider="openai")
            MockRouter.return_value = mock_router

            chain = FallbackChain(providers=["openai", "anthropic"])

            # Since anthropic has no mock, it'll also fail
            with pytest.raises(LLMAllProvidersFailedError):
                await chain.complete(
                    messages=[{"role": "user", "content": "Hello"}],
                )

            # Only one call per provider (no retries on rate limit)
            assert mock_router.complete.call_count == 2  # Once per provider


class TestFallbackChainManagement:
    """Tests for FallbackChain management methods."""

    def test_update_provider_order(self, mock_settings):
        """update_provider_order changes order and adds health records."""
        chain = FallbackChain(providers=["openai"])
        chain.update_provider_order(["anthropic", "gemini"])

        assert chain.providers == ["anthropic", "gemini"]
        assert "anthropic" in chain._health
        assert "gemini" in chain._health

    def test_get_health_status(self, mock_settings):
        """get_health_status returns structured health info."""
        chain = FallbackChain(providers=["openai", "ollama"])
        status = chain.get_health_status()

        assert "providers" in status
        assert "available_providers" in status
        assert "total_fallback_events" in status
        assert "openai" in status["providers"]
        assert "ollama" in status["providers"]

    def test_get_fallback_history(self, mock_settings):
        """get_fallback_history returns recent fallback events."""
        chain = FallbackChain(providers=["openai", "anthropic"])
        history = chain.get_fallback_history()
        assert history == []

        # Manually add an event
        chain._fallback_log.append(
            FallbackEvent(from_provider="openai", to_provider="anthropic", reason="Error")
        )
        history = chain.get_fallback_history()
        assert len(history) == 1
        assert history[0]["from_provider"] == "openai"

    def test_reset_provider_health(self, mock_settings):
        """reset_provider_health clears a provider's health record."""
        chain = FallbackChain(providers=["openai"])
        chain._health["openai"].record_failure("Error")
        chain._health["openai"].record_failure("Error")
        chain._health["openai"].record_failure("Error")
        assert chain._health["openai"].status == ProviderHealth.UNHEALTHY

        chain.reset_provider_health("openai")
        assert chain._health["openai"].status == ProviderHealth.UNKNOWN
        assert chain._health["openai"].consecutive_failures == 0

    def test_get_stats(self, mock_settings):
        """get_stats returns aggregate statistics."""
        chain = FallbackChain(providers=["openai", "ollama"])

        # Simulate some activity
        chain._health["openai"].record_success(latency_ms=100.0)
        chain._health["ollama"].record_failure("Timeout")

        stats = chain.get_stats()
        assert stats["total_requests"] == 2
        assert stats["total_successes"] == 1
        assert stats["total_failures"] == 1
        assert stats["success_rate"] == 0.5
        assert stats["fallback_events"] == 0

    def test_get_default_model(self, mock_settings):
        """_get_default_model returns correct model per provider."""
        chain = FallbackChain(providers=["openai"])
        assert chain._get_default_model("openai") == "gpt-4o"
        assert chain._get_default_model("ollama") == "llama3.1:8b"
        # Unknown provider returns fallback
        model = chain._get_default_model("nonexistent")
        assert model is not None
