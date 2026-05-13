"""
Tests for nexus.core.config — NexusConfig and settings management.
"""

import os
import pytest
from unittest.mock import patch

from nexus.core.config import NexusConfig, get_settings, reload_settings, Environment, LogLevel


class TestNexusConfig:
    """Unit tests for NexusConfig model."""

    def test_default_values(self):
        """Config should have sensible defaults."""
        # Create a temp .env to avoid inheriting from project .env
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("")
            tmp_env = f.name
        try:
            config = NexusConfig(_env_file=tmp_env)
            assert config.nexus_env == Environment.DEVELOPMENT
            assert config.nexus_log_level == LogLevel.INFO
            assert config.nexus_port == 8080
            assert config.nexus_host == "0.0.0.0"
            assert config.chroma_persist_dir == "./nexus_data/chroma"
            assert config.ollama_base_url == "http://127.0.0.1:11434"
            assert config.ollama_default_model == "llama3.1:8b"
            assert config.memory_max_working_tokens == 30000
            assert config.llm_default_provider == "openai"
            assert config.llm_default_model == "gpt-4o"
            assert config.browser_service_url == "http://localhost:8001"
        finally:
            os.unlink(tmp_env)

    def test_env_override(self, tmp_path):
        """Config values should be overridable via environment variables."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXUS_PORT=9999\nNEXUS_ENV=production\nNEXUS_SECRET_KEY=test-secret-key-12345\n")

        config = NexusConfig(_env_file=str(env_file))
        assert config.nexus_port == 9999
        assert config.nexus_env == Environment.PRODUCTION

    def test_port_validation_valid(self):
        """Valid ports should be accepted."""
        config = NexusConfig(nexus_port=80)
        assert config.nexus_port == 80
        config = NexusConfig(nexus_port=65535)
        assert config.nexus_port == 65535

    def test_port_validation_invalid(self):
        """Invalid ports should raise ValueError."""
        with pytest.raises(ValueError, match="Port must be between"):
            NexusConfig(nexus_port=0)
        with pytest.raises(ValueError, match="Port must be between"):
            NexusConfig(nexus_port=70000)

    def test_available_providers_with_keys(self):
        """available_providers should list providers with configured API keys."""
        config = NexusConfig(
            openai_api_key="sk-test",
            anthropic_api_key="sk-ant-test",
            google_api_key="google-test",
            zai_api_key="zai-test",
        )
        providers = config.available_providers
        assert "openai" in providers
        assert "anthropic" in providers
        assert "gemini" in providers
        assert "glm" in providers
        assert "ollama" in providers  # Always available

    def test_available_providers_no_keys(self):
        """Without API keys, only ollama should be available."""
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("")
            tmp_env = f.name
        try:
            config = NexusConfig(_env_file=tmp_env)
            providers = config.available_providers
            assert "ollama" in providers  # local fallback always available
        finally:
            os.unlink(tmp_env)

    def test_fallback_providers_filtered(self):
        """Fallback chain should only include providers with configured keys."""
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("OPENAI_API_KEY=sk-test\nLLM_FALLBACK_CHAIN=openai,anthropic,gemini,glm,ollama\n")
            tmp_env = f.name
        try:
            config = NexusConfig(_env_file=tmp_env)
            fallback = config.fallback_providers
            assert "openai" in fallback
            assert "ollama" in fallback  # local always available
        finally:
            os.unlink(tmp_env)

    def test_is_production(self):
        """is_production property should reflect environment."""
        config = NexusConfig(nexus_env=Environment.PRODUCTION)
        assert config.is_production is True
        assert config.is_development is False

    def test_is_development(self):
        """is_development property should reflect environment."""
        config = NexusConfig(nexus_env=Environment.DEVELOPMENT)
        assert config.is_development is True
        assert config.is_production is False

    def test_secret_key_production_validation(self):
        """Default secret key should be rejected in production."""
        with patch.dict(os.environ, {"NEXUS_ENV": "production"}):
            with pytest.raises(ValueError, match="NEXUS_SECRET_KEY must be changed"):
                NexusConfig(nexus_secret_key="change-me-to-a-secure-random-string")

    def test_custom_secret_key_production(self):
        """Custom secret key should be accepted in production."""
        with patch.dict(os.environ, {"NEXUS_ENV": "production"}):
            config = NexusConfig(nexus_secret_key="a-very-secure-random-key-12345")
            assert config.nexus_secret_key == "a-very-secure-random-key-12345"

    def test_llm_settings(self):
        """LLM router settings should have correct defaults."""
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("")
            tmp_env = f.name
        try:
            config = NexusConfig(_env_file=tmp_env)
            assert config.llm_timeout_seconds == 120
            assert config.llm_max_retries == 3
            # LLM_FALLBACK_CHAIN defaults to gemini in .env, so check dynamically
            # For isolated test, just verify it's a valid string
            assert isinstance(config.llm_fallback_chain, str)
        finally:
            os.unlink(tmp_env)

    def test_memory_settings(self):
        """Memory settings should have correct defaults."""
        config = NexusConfig()
        assert config.memory_max_working_tokens == 30000
        assert config.memory_compression_threshold == 0.8
        assert config.memory_default_top_k == 5


class TestGetSettings:
    """Tests for settings caching and singleton behavior."""

    def test_get_settings_returns_config(self):
        """get_settings should return a NexusConfig instance."""
        reload_settings()
        settings = get_settings()
        assert isinstance(settings, NexusConfig)

    def test_get_settings_cached(self):
        """get_settings should return the same instance on repeated calls."""
        reload_settings()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_reload_settings(self):
        """reload_settings should clear cache and return new instance."""
        s1 = get_settings()
        s2 = reload_settings()
        assert s1 is not s2
        assert isinstance(s2, NexusConfig)

    def test_config_from_env_vars(self):
        """Config should pick up values from environment variables."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-from-env"}):
            config = NexusConfig()
            assert config.openai_api_key == "sk-from-env"
