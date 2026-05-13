"""
Tests for nexus.security.vault - SecretsVault.
"""

import pytest
import tempfile
from pathlib import Path
from nexus.security.vault import SecretsVault


class TestSecretsVault:
    """Test cases for SecretsVault."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def vault(self, temp_dir):
        return SecretsVault(vault_dir=temp_dir)

    def test_init(self, vault, temp_dir):
        assert vault is not None
        assert vault.vault_dir == Path(temp_dir)

    def test_store_and_retrieve(self, vault):
        """Store and retrieve a secret."""
        vault.store("key1", "secret_value")
        retrieved = vault.retrieve("key1")
        assert retrieved == "secret_value"

    def test_retrieve_missing_returns_none(self, vault):
        """Retrieve missing key returns None."""
        result = vault.retrieve("nonexistent_key")
        assert result is None

    def test_update_secret(self, vault):
        """Update existing secret."""
        vault.store("key1", "value1")
        vault.store("key1", "value2")
        assert vault.retrieve("key1") == "value2"

    def test_delete_secret(self, vault):
        """Delete a secret."""
        vault.store("key1", "value1")
        vault.delete("key1")
        assert vault.retrieve("key1") is None

    def test_list_keys(self, vault):
        """List all keys."""
        vault.store("key1", "value1")
        vault.store("key2", "value2")
        keys = vault.list_keys()
        assert "key1" in keys
        assert "key2" in keys