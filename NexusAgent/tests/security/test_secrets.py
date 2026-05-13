"""
Comprehensive tests for nexus.security.secrets - SecretsManager.

Covers all methods: get, require, mask, is_configured,
get_configured_providers, validate_all, hash_secret,
encrypt_value, decrypt_value, get_stats.

All external dependencies (settings, vault, cryptography) are mocked.
"""

import hashlib
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from nexus.security.secrets import SecretsManager


class TestSecretsManagerGet:
    """Tests for SecretsManager.get()."""

    def test_get_reads_env_first(self):
        """get reads from environment before config."""
        with patch("nexus.security.secrets.os.environ.get", return_value="env-val"):
            sm = SecretsManager()
            assert sm.get("OPENAI_API_KEY") == "env-val"

    def test_get_returns_cached_value(self):
        """get returns cached value without checking env/config."""
        sm = SecretsManager()
        sm._cache["MY_KEY"] = "cached-val"
        with patch("nexus.security.secrets.os.environ.get") as mock_env:
            result = sm.get("MY_KEY")
            assert result == "cached-val"
            mock_env.assert_not_called()

    def test_get_reads_config_when_env_missing(self):
        """get falls through to config mapping when env is empty."""
        sm = SecretsManager()
        sm.settings.openai_api_key = "cfg-key"

        with patch("nexus.security.secrets.os.environ.get", return_value=None):
            result = sm.get("OPENAI_API_KEY")
            assert result == "cfg-key"

    def test_get_config_returns_none_when_empty(self):
        """get returns None from config when the config value is empty."""
        sm = SecretsManager()
        sm.settings.openai_api_key = ""

        with patch("nexus.security.secrets.os.environ.get", return_value=None):
            result = sm.get("OPENAI_API_KEY")
            assert result is None

    def test_get_caches_env_value(self):
        """get caches the value it reads from environment."""
        sm = SecretsManager()
        with patch("nexus.security.secrets.os.environ.get", return_value="env-val"):
            sm.get("MY_KEY")
        assert sm._cache["MY_KEY"] == "env-val"

    def test_get_caches_config_value(self):
        """get caches the value it reads from config."""
        sm = SecretsManager()
        sm.settings.openai_api_key = "cfg-key"
        with patch("nexus.security.secrets.os.environ.get", return_value=None):
            sm.get("OPENAI_API_KEY")
        assert sm._cache["OPENAI_API_KEY"] == "cfg-key"

    def test_get_returns_default_when_not_found(self):
        """get returns default when key is not found anywhere."""
        sm = SecretsManager()
        with patch("nexus.security.secrets.os.environ.get", return_value=None):
            result = sm.get("NONEXISTENT_KEY", default="fallback")
            assert result == "fallback"

    def test_get_returns_none_default(self):
        """get returns None by default when key not found."""
        sm = SecretsManager()
        with patch("nexus.security.secrets.os.environ.get", return_value=None):
            result = sm.get("NONEXISTENT_KEY")
            assert result is None

    def test_get_key_not_in_config_mapping(self):
        """get handles keys not in config_mapping."""
        sm = SecretsManager()
        with patch("nexus.security.secrets.os.environ.get", return_value=None):
            result = sm.get("SOME_RANDOM_KEY")
            assert result is None

    @patch("nexus.security.vault.SecretsVault")
    def test_get_reads_vault_as_last_resort(self, mock_vault_class):
        """get checks encrypted vault after env and config."""
        mock_vault = mock_vault_class.return_value
        mock_vault.retrieve.return_value = "vault-val"

        sm = SecretsManager()
        with patch("nexus.security.secrets.os.environ.get", return_value=None):
            result = sm.get("CUSTOM_KEY")
            # CUSTOM_KEY is not in config_mapping so it falls through to vault
            assert result == "vault-val"

    @patch("nexus.security.vault.SecretsVault")
    def test_get_vault_failure_returns_default(self, mock_vault_class):
        """get swallows vault exception and returns default."""
        mock_vault_class.side_effect = RuntimeError("vault unavailable")

        sm = SecretsManager()
        with patch("nexus.security.secrets.os.environ.get", return_value=None):
            result = sm.get("CUSTOM_KEY", default="safe-default")
            assert result == "safe-default"

    def test_get_caches_vault_value(self):
        """get caches a value retrieved from vault."""
        sm = SecretsManager()
        with patch("nexus.security.secrets.os.environ.get", return_value=None), \
             patch("nexus.security.vault.SecretsVault") as m:
            vault = m.return_value
            vault.retrieve.return_value = "vault-val"
            sm.get("CUSTOM_KEY")

        assert sm._cache["CUSTOM_KEY"] == "vault-val"


class TestSecretsManagerRequire:
    """Tests for SecretsManager.require()."""

    def test_require_returns_value_when_configured(self):
        """require returns the value when key is found."""
        sm = SecretsManager()
        with patch.object(sm, "get", return_value="configured-key"):
            result = sm.require("OPENAI_API_KEY")
            assert result == "configured-key"

    def test_require_raises_value_error_when_missing(self):
        """require raises ValueError when key is not found."""
        sm = SecretsManager()
        with patch.object(sm, "get", return_value=None):
            with pytest.raises(ValueError) as excinfo:
                sm.require("MISSING_KEY")
            assert "MISSING_KEY" in str(excinfo.value)
            assert "not configured" in str(excinfo.value)

    def test_require_raises_on_empty_string(self):
        """require raises ValueError when value is empty string."""
        sm = SecretsManager()
        with patch.object(sm, "get", return_value=""):
            with pytest.raises(ValueError):
                sm.require("EMPTY_KEY")


class TestSecretsManagerMask:
    """Tests for SecretsManager.mask()."""

    def test_mask_long_value(self):
        """mask shows first 3 and last N chars."""
        result = SecretsManager.mask("sk-abc123def456", visible_chars=4)
        assert result == "sk-...f456"

    def test_mask_short_value(self):
        """mask returns *** for very short values."""
        result = SecretsManager.mask("ab", visible_chars=4)
        assert result == "***"

    def mask_empty_value(self):
        """mask returns *** for empty string."""
        result = SecretsManager.mask("", visible_chars=4)
        assert result == "***"

    def mask_none_value(self):
        """mask returns *** for None."""
        result = SecretsManager.mask(None, visible_chars=4)
        assert result == "***"

    def test_mask_custom_visible_chars(self):
        """mask respects visible_chars parameter."""
        result = SecretsManager.mask("abcdefgh", visible_chars=2)
        assert result == "abc...gh"

    def test_mask_exact_length(self):
        """mask handles value length == visible_chars."""
        # len("abcd") == 4, value = "abcdefgh", visible_chars = 8 → len(value) == 8 ≯ 8, so returns "***"
        result = SecretsManager.mask("abcdefgh", visible_chars=8)
        assert result == "***"


class TestSecretsManagerIsConfigured:
    """Tests for SecretsManager.is_configured()."""

    def test_is_configured_true(self):
        """is_configured returns True for non-empty value."""
        sm = SecretsManager()
        with patch.object(sm, "get", return_value="some-key"):
            assert sm.is_configured("OPENAI_API_KEY") is True

    def test_is_configured_false_none(self):
        """is_configured returns False when get returns None."""
        sm = SecretsManager()
        with patch.object(sm, "get", return_value=None):
            assert sm.is_configured("ANY_KEY") is False

    def test_is_configured_false_empty(self):
        """is_configured returns False for empty string."""
        sm = SecretsManager()
        with patch.object(sm, "get", return_value=""):
            assert sm.is_configured("ANY_KEY") is False

    def test_is_configured_false_whitespace(self):
        """is_configured returns False for whitespace-only."""
        sm = SecretsManager()
        with patch.object(sm, "get", return_value="   "):
            assert sm.is_configured("ANY_KEY") is False


class TestSecretsManagerConfiguredProviders:
    """Tests for SecretsManager.get_configured_providers()."""

    def test_all_providers_configured(self):
        """Returns all providers when all keys are present."""
        sm = SecretsManager()
        with patch.object(sm, "is_configured", return_value=True):
            providers = sm.get_configured_providers()
            assert "openai" in providers
            assert "anthropic" in providers
            assert "gemini" in providers
            assert "glm" in providers
            assert "ollama" in providers  # Always included

    def test_no_api_providers_configured(self):
        """Returns only ollama when no API keys are set."""
        sm = SecretsManager()
        with patch.object(sm, "is_configured", return_value=False):
            providers = sm.get_configured_providers()
            assert providers == ["ollama"]

    def test_only_openai_configured(self):
        """Returns only openai and ollama."""
        def side_effect(key):
            return key == "OPENAI_API_KEY"
        sm = SecretsManager()
        with patch.object(sm, "is_configured", side_effect=side_effect):
            providers = sm.get_configured_providers()
            assert providers == ["openai", "ollama"]

    def test_providers_order(self):
        """Providers are returned in a consistent order."""
        sm = SecretsManager()
        with patch.object(sm, "is_configured", return_value=True):
            providers = sm.get_configured_providers()
            # openai, anthropic, gemini, glm, ollama
            assert providers.index("openai") < providers.index("ollama")


class TestSecretsManagerValidateAll:
    """Tests for SecretsManager.validate_all()."""

    def test_validate_all_returns_dict(self):
        """validate_all returns a dict with all SENSITIVE_KEYS."""
        sm = SecretsManager()
        with patch.object(sm, "is_configured", side_effect=lambda k: k == "OPENAI_API_KEY"):
            results = sm.validate_all()
            assert isinstance(results, dict)
            for key in SecretsManager.SENSITIVE_KEYS:
                assert key in results

    def test_validate_all_all_configured(self):
        """validate_all returns True for all when everything configured."""
        sm = SecretsManager()
        with patch.object(sm, "is_configured", return_value=True):
            results = sm.validate_all()
            assert all(results.values())

    def test_validate_all_none_configured(self):
        """validate_all returns False for all when nothing configured."""
        sm = SecretsManager()
        with patch.object(sm, "is_configured", return_value=False):
            results = sm.validate_all()
            assert not any(results.values())


class TestSecretsManagerHashSecret:
    """Tests for SecretsManager.hash_secret()."""

    def test_hash_secret_deterministic(self):
        """hash_secret produces consistent results for same input."""
        sm = SecretsManager()
        sm.settings.nexus_secret_key = "pepper-123"
        h1 = sm.hash_secret("my-secret")
        h2 = sm.hash_secret("my-secret")
        assert h1 == h2

    def test_hash_secret_different_inputs_differ(self):
        """hash_secret produces different hashes for different inputs."""
        sm = SecretsManager()
        sm.settings.nexus_secret_key = "pepper-123"
        h1 = sm.hash_secret("secret-1")
        h2 = sm.hash_secret("secret-2")
        assert h1 != h2

    def test_hash_secret_uses_pepper(self):
        """hash_secret incorporates the pepper in the hash."""
        sm = SecretsManager()
        sm.settings.nexus_secret_key = "pepper-1"
        h1 = sm.hash_secret("my-secret")

        sm2 = SecretsManager()
        sm2.settings.nexus_secret_key = "pepper-2"
        h2 = sm2.hash_secret("my-secret")
        assert h1 != h2

    def test_hash_secret_default_pepper(self):
        """hash_secret uses 'nexus-default-pepper' when no secret key is set."""
        sm = SecretsManager()
        sm.settings.nexus_secret_key = None
        # Should not raise
        h = sm.hash_secret("my-secret")
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest

    def test_hash_secret_output_format(self):
        """hash_secret returns a SHA-256 hex string."""
        sm = SecretsManager()
        sm.settings.nexus_secret_key = "test-pepper"
        h = sm.hash_secret("test-value")
        expected = hashlib.sha256(b"test-pepper:test-value").hexdigest()
        assert h == expected


class TestSecretsManagerEncryptDecrypt:
    """Tests for SecretsManager.encrypt_value() / decrypt_value()."""

    def test_encrypt_raises_without_key(self):
        """encrypt_value raises ValueError when NEXUS_SECRET_KEY not set."""
        sm = SecretsManager()
        sm.settings.nexus_secret_key = None
        with pytest.raises(ValueError, match="NEXUS_SECRET_KEY is not set"):
            sm.encrypt_value("my-value")

    def test_decrypt_raises_without_key(self):
        """decrypt_value raises ValueError when NEXUS_SECRET_KEY not set."""
        sm = SecretsManager()
        sm.settings.nexus_secret_key = None
        with pytest.raises(ValueError, match="NEXUS_SECRET_KEY is not set"):
            sm.decrypt_value("encrypted-value")

    @patch("cryptography.fernet.Fernet")
    def test_encrypt_decrypt_round_trip(self, mock_fernet_class):
        """encrypt_value and decrypt_value round-trip correctly."""
        mock_fernet = MagicMock()
        mock_fernet_class.return_value = mock_fernet
        mock_fernet.encrypt.return_value = b"encrypted_bytes"
        mock_fernet.decrypt.return_value = b"original_value"

        sm = SecretsManager()
        sm.settings.nexus_secret_key = "my-secret-key"

        encrypted = sm.encrypt_value("original_value")
        assert encrypted == "encrypted_bytes"

        decrypted = sm.decrypt_value(encrypted)
        assert decrypted == "original_value"

    @patch("cryptography.fernet.Fernet")
    def test_encrypt_uses_sha256_key_derivation(self, mock_fernet_class):
        """encrypt_value derives Fernet key via SHA-256."""
        sm = SecretsManager()
        sm.settings.nexus_secret_key = "my-key"

        sm.encrypt_value("val")
        # Fernet was instantiated with a key derived from SHA-256 of the secret key
        call_args = mock_fernet_class.call_args
        key_arg = call_args[0][0]
        import base64
        expected_key = base64.urlsafe_b64encode(
            hashlib.sha256(b"my-key").digest()
        )
        assert key_arg == expected_key

    @patch("cryptography.fernet.Fernet")
    def test_decrypt_invalid_token(self, mock_fernet_class):
        """decrypt_value raises ValueError on invalid token."""
        mock_fernet = MagicMock()
        mock_fernet_class.return_value = mock_fernet
        mock_fernet.decrypt.side_effect = Exception("InvalidToken")

        sm = SecretsManager()
        sm.settings.nexus_secret_key = "my-key"

        with pytest.raises(ValueError, match="Failed to decrypt"):
            sm.decrypt_value("bad-encrypted-data")


class TestSecretsManagerStats:
    """Tests for SecretsManager.get_stats()."""

    def test_get_stats_returns_dict(self):
        """get_stats returns a dictionary with expected keys."""
        sm = SecretsManager()
        with patch.object(sm, "validate_all", return_value={
            k: False for k in SecretsManager.SENSITIVE_KEYS
        }), patch.object(sm, "get_configured_providers", return_value=["ollama"]):
            stats = sm.get_stats()
            assert "total_keys_tracked" in stats
            assert stats["total_keys_tracked"] == len(SecretsManager.SENSITIVE_KEYS)
            assert stats["configured_count"] == 0
            assert stats["providers_available"] == ["ollama"]
            assert stats["cache_size"] == 0
            assert "configured_details" in stats

    def test_get_stats_with_configured_keys(self):
        """get_stats reflects configured keys count."""
        sm = SecretsManager()
        configured = {k: k == "OPENAI_API_KEY" for k in SecretsManager.SENSITIVE_KEYS}
        with patch.object(sm, "validate_all", return_value=configured), \
             patch.object(sm, "get_configured_providers", return_value=["openai", "ollama"]):
            stats = sm.get_stats()
            assert stats["configured_count"] == 1
            assert stats["providers_available"] == ["openai", "ollama"]


class TestSecretsManagerInit:
    """Tests for SecretsManager initialization."""

    @patch("nexus.security.secrets.get_settings")
    def test_init_calls_get_settings(self, mock_settings):
        """__init__ calls get_settings to populate self.settings."""
        s = MagicMock()
        mock_settings.return_value = s
        sm = SecretsManager()
        assert sm.settings == s

    def test_init_empty_cache(self):
        """__init__ starts with empty cache."""
        sm = SecretsManager()
        assert sm._cache == {}

    def test_init_empty_access_log(self):
        """__init__ starts with empty access log."""
        sm = SecretsManager()
        assert sm._access_log == []

    def test_sensitive_keys_frozenset(self):
        """SENSITIVE_KEYS is a frozenset."""
        assert isinstance(SecretsManager.SENSITIVE_KEYS, frozenset)
        assert "OPENAI_API_KEY" in SecretsManager.SENSITIVE_KEYS
        assert "TELEGRAM_BOT_TOKEN" in SecretsManager.SENSITIVE_KEYS
