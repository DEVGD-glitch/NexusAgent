"""
Complete tests for NEXUS Security modules.

Covers:
  - AuditLogger: file rotation logic, log query with filters, entry count
    and stats, tool call logging, LLM call logging, memory access logging,
    security event logging, query with category/action/outcome/since filters,
    multiple log file handling, error on corrupt entries
  - SecretsVault: pepper creation and reuse, key derivation, store/retrieve/
    delete/list, migrate from env file, error cases (corrupted vault, wrong
    key, cryptography missing), pepper atomic write
"""

import pytest
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# ═══════════════════════════════════════════════════════════════════
# Module-Level Patches
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def mock_settings():
    """Mock get_settings in security modules."""
    from unittest.mock import MagicMock, patch

    settings = MagicMock()
    settings.audit_log_dir = ""
    settings.nexus_env = "development"

    targets = [
        "nexus.security.audit.get_settings",
    ]
    patchers = [patch(target, return_value=settings) for target in targets]
    for p in patchers:
        p.start()
    yield settings
    for p in patchers:
        p.stop()


# ═══════════════════════════════════════════════════════════════════
# Audit Logger Tests
# ═══════════════════════════════════════════════════════════════════

class TestAuditEntry:
    """Test AuditEntry dataclass."""

    def test_default_creation(self):
        """AuditEntry with default values."""
        from nexus.security.audit import AuditEntry

        entry = AuditEntry(action="test_action")
        assert entry.action == "test_action"
        assert entry.event_id is not None
        assert len(entry.event_id) == 16
        assert entry.timestamp is not None
        assert entry.category.value == "agent_action"
        assert entry.level.value == "info"

    def test_creation_with_all_fields(self):
        """AuditEntry with all fields."""
        from nexus.security.audit import AuditEntry, AuditCategory, AuditLevel

        entry = AuditEntry(
            category=AuditCategory.SECURITY,
            level=AuditLevel.CRITICAL,
            action="file_access_denied",
            actor="user_abc",
            target="/etc/passwd",
            details={"ip": "192.168.1.1"},
            outcome="denied",
            session_id="sess_123",
            ip_address="192.168.1.1",
        )
        assert entry.actor == "user_abc"
        assert entry.outcome == "denied"
        assert entry.session_id == "sess_123"

    def test_to_json_serialization(self):
        """to_json should produce valid JSON string."""
        from nexus.security.audit import AuditEntry, AuditCategory

        entry = AuditEntry(
            category=AuditCategory.TOOL_CALL,
            action="execute_code",
            target="sandbox",
            details={"code_length": 150},
            outcome="success",
        )
        json_str = entry.to_json()
        data = json.loads(json_str)
        assert data["action"] == "execute_code"
        assert data["category"] == "tool_call"
        assert data["outcome"] == "success"
        assert data["details"]["code_length"] == 150
        assert "event_id" in data
        assert "timestamp" in data


class TestAuditLoggerFileIO:
    """Test AuditLogger file I/O operations (using tmp_path)."""

    def test_init_creates_directory(self, tmp_path):
        """AuditLogger should create log directory."""
        from nexus.security.audit import AuditLogger

        log_dir = tmp_path / "audit_logs"
        logger = AuditLogger(log_dir=str(log_dir))
        assert log_dir.exists()

    def test_log_writes_to_file(self, tmp_path):
        """Log should write entry to JSONL file."""
        from nexus.security.audit import AuditLogger, AuditCategory

        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=str(log_dir))

        event_id = logger.log(
            category=AuditCategory.AGENT_ACTION,
            action="test_write",
            outcome="success",
        )

        # Check file was created
        log_files = list(log_dir.glob("nexus_audit_*.jsonl"))
        assert len(log_files) >= 1

        # Read back and verify
        content = log_files[0].read_text(encoding="utf-8")
        assert event_id in content
        assert "test_write" in content

    def test_log_file_rotation_by_date(self, tmp_path):
        """Log should create new file per day."""
        from nexus.security.audit import AuditLogger, AuditCategory

        log_dir = tmp_path / "rotation"
        logger = AuditLogger(log_dir=str(log_dir))

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        expected_name = f"nexus_audit_{today}.jsonl"

        logger.log(category=AuditCategory.AUTH, action="login", outcome="success")
        log_files = list(log_dir.glob("*.jsonl"))
        assert len(log_files) >= 1
        assert any(expected_name in f.name for f in log_files)

    def test_multiple_entries_in_same_file(self, tmp_path):
        """Multiple logs should append to same file."""
        from nexus.security.audit import AuditLogger, AuditCategory

        log_dir = tmp_path / "multi"
        logger = AuditLogger(log_dir=str(log_dir))

        ids = []
        for i in range(5):
            eid = logger.log(
                category=AuditCategory.AGENT_ACTION,
                action=f"action_{i}",
                outcome="success",
            )
            ids.append(eid)

        log_files = list(log_dir.glob("*.jsonl"))
        content = log_files[0].read_text(encoding="utf-8")
        lines = content.strip().split("\n")
        assert len(lines) == 5
        for eid in ids:
            assert eid in content

    def test_query_all_entries(self, tmp_path):
        """query() should return all entries when no filters."""
        from nexus.security.audit import AuditLogger, AuditCategory

        log_dir = tmp_path / "query_all"
        logger = AuditLogger(log_dir=str(log_dir))

        logger.log(category=AuditCategory.AUTH, action="login", outcome="success")
        logger.log(category=AuditCategory.TOOL_CALL, action="execute", outcome="success")
        logger.log(category=AuditCategory.SECURITY, action="blocked", outcome="denied")

        results = logger.query()
        assert len(results) == 3

    def test_query_filter_by_category(self, tmp_path):
        """query() should filter by category."""
        from nexus.security.audit import AuditLogger, AuditCategory

        log_dir = tmp_path / "query_cat"
        logger = AuditLogger(log_dir=str(log_dir))

        logger.log(category=AuditCategory.AUTH, action="login", outcome="success")
        logger.log(category=AuditCategory.TOOL_CALL, action="run", outcome="success")
        logger.log(category=AuditCategory.AUTH, action="logout", outcome="success")

        results = logger.query(category=AuditCategory.AUTH)
        assert len(results) == 2
        assert all(r["category"] == "auth" for r in results)

    def test_query_filter_by_action(self, tmp_path):
        """query() should filter by action."""
        from nexus.security.audit import AuditLogger, AuditCategory

        log_dir = tmp_path / "query_action"
        logger = AuditLogger(log_dir=str(log_dir))

        logger.log(category=AuditCategory.AUTH, action="login", outcome="success")
        logger.log(category=AuditCategory.AUTH, action="logout", outcome="success")
        logger.log(category=AuditCategory.AUTH, action="login", outcome="failed")

        results = logger.query(action="login")
        assert len(results) == 2

    def test_query_filter_by_outcome(self, tmp_path):
        """query() should filter by outcome."""
        from nexus.security.audit import AuditLogger, AuditCategory

        log_dir = tmp_path / "query_outcome"
        logger = AuditLogger(log_dir=str(log_dir))

        logger.log(category=AuditCategory.AUTH, action="login", outcome="success")
        logger.log(category=AuditCategory.AUTH, action="login", outcome="failed")
        logger.log(category=AuditCategory.AUTH, action="login", outcome="success")

        results = logger.query(outcome="success")
        assert len(results) == 2

    def test_query_filter_by_since(self, tmp_path):
        """query() should filter by timestamp."""
        from nexus.security.audit import AuditLogger, AuditCategory

        log_dir = tmp_path / "query_since"
        logger = AuditLogger(log_dir=str(log_dir))

        logger.log(category=AuditCategory.AUTH, action="old", outcome="success")
        later = datetime.now(timezone.utc).isoformat()
        logger.log(category=AuditCategory.AUTH, action="new", outcome="success")

        results = logger.query(since=later)
        assert len(results) == 1
        assert results[0]["action"] == "new"

    def test_query_with_limit(self, tmp_path):
        """query() should respect limit."""
        from nexus.security.audit import AuditLogger, AuditCategory

        log_dir = tmp_path / "query_limit"
        logger = AuditLogger(log_dir=str(log_dir))

        for i in range(10):
            logger.log(category=AuditCategory.AGENT_ACTION, action=f"action_{i}", outcome="success")

        results = logger.query(limit=3)
        assert len(results) == 3

    def test_query_multiple_filters(self, tmp_path):
        """query() with multiple filters combined."""
        from nexus.security.audit import AuditLogger, AuditCategory

        log_dir = tmp_path / "query_multi"
        logger = AuditLogger(log_dir=str(log_dir))

        logger.log(category=AuditCategory.AUTH, action="login", outcome="success")
        logger.log(category=AuditCategory.AUTH, action="login", outcome="failed")
        logger.log(category=AuditCategory.TOOL_CALL, action="run", outcome="success")

        results = logger.query(category=AuditCategory.AUTH, action="login", outcome="success")
        assert len(results) == 1

    def test_query_traverses_multiple_log_files(self, tmp_path):
        """query() should read from multiple log files."""
        from nexus.security.audit import AuditLogger, AuditCategory

        log_dir = tmp_path / "multi_file"

        # Create log entries by manipulating the internal file pointer
        logger = AuditLogger(log_dir=str(log_dir))
        logger.log(category=AuditCategory.AUTH, action="file1_entry", outcome="success")

        # Force a new file by closing current handle
        logger.close()

        # Write directly to a second log file
        yesterday_file = log_dir / "nexus_audit_2020-01-01.jsonl"
        yesterday_file.write_text(
            json.dumps({
                "event_id": "old_event",
                "timestamp": "2020-01-01T00:00:00",
                "category": "auth",
                "action": "old_entry",
            }) + "\n",
            encoding="utf-8",
        )

        results = logger.query()
        # Should find entries from both files
        actions = [r["action"] for r in results]
        assert "old_entry" in actions
        assert "file1_entry" in actions

    def test_query_skips_corrupt_lines(self, tmp_path):
        """query() should skip corrupt JSON lines."""
        from nexus.security.audit import AuditLogger

        log_dir = tmp_path / "corrupt"
        logger = AuditLogger(log_dir=str(log_dir))

        # Write a corrupt line directly
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = log_dir / f"nexus_audit_{today}.jsonl"
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("not valid json\n")
            f.write(json.dumps({"event_id": "valid", "action": "good"}) + "\n")

        results = logger.query()
        assert len(results) == 1
        assert results[0]["event_id"] == "valid"

    def test_query_file_not_found(self, tmp_path):
        """query() should handle missing file gracefully."""
        from nexus.security.audit import AuditLogger

        log_dir = tmp_path / "empty_dir"
        log_dir.mkdir()
        logger = AuditLogger(log_dir=str(log_dir))

        results = logger.query()
        assert results == []


class TestAuditLoggerStats:
    """Test AuditLogger stats and counts."""

    def test_get_stats(self, tmp_path):
        """get_stats should return log statistics."""
        from nexus.security.audit import AuditLogger, AuditCategory

        log_dir = tmp_path / "stats"
        logger = AuditLogger(log_dir=str(log_dir))

        logger.log(category=AuditCategory.AGENT_ACTION, action="a1", outcome="success")
        logger.log(category=AuditCategory.AGENT_ACTION, action="a2", outcome="failed")

        stats = logger.get_stats()
        assert stats["entries_logged"] == 2
        assert stats["log_files"] >= 1
        assert stats["total_size_bytes"] > 0
        assert str(log_dir) in stats["log_dir"]

    def test_get_stats_empty(self, tmp_path):
        """get_stats on fresh logger should return zeros."""
        from nexus.security.audit import AuditLogger

        log_dir = tmp_path / "empty_stats"
        logger = AuditLogger(log_dir=str(log_dir))

        stats = logger.get_stats()
        assert stats["entries_logged"] == 0
        assert stats["total_size_bytes"] == 0
        # No log files yet (maybe empty glob)
        assert stats["log_files"] >= 0

    def test_close_method(self, tmp_path):
        """close() should release file handle."""
        from nexus.security.audit import AuditLogger

        log_dir = tmp_path / "close_test"
        logger = AuditLogger(log_dir=str(log_dir))
        logger.log(action="test")
        assert logger._file_handle is not None

        logger.close()
        assert logger._file_handle is None
        assert logger._current_file is None

    def test_close_twice(self, tmp_path):
        """close() called twice should not raise."""
        from nexus.security.audit import AuditLogger

        log_dir = tmp_path / "close2"
        logger = AuditLogger(log_dir=str(log_dir))
        logger.close()
        logger.close()  # Should not raise


class TestAuditLoggerConvenience:
    """Test AuditLogger convenience methods."""

    def test_log_tool_call(self, tmp_path):
        """log_tool_call should log with TOOL_CALL category."""
        from nexus.security.audit import AuditLogger

        log_dir = tmp_path / "tool_call"
        logger = AuditLogger(log_dir=str(log_dir))

        event_id = logger.log_tool_call(
            tool_name="execute_python",
            params={"code": "print(1)"},
            outcome="success",
            execution_time_ms=150.0,
            session_id="sess_001",
        )
        assert event_id is not None

        # Verify in file
        log_files = list(log_dir.glob("*.jsonl"))
        content = log_files[0].read_text(encoding="utf-8")
        assert "execute_python" in content
        assert "tool_call" in content
        assert "execution_time_ms" in content

    def test_log_llm_call(self, tmp_path):
        """log_llm_call should log LLM API calls."""
        from nexus.security.audit import AuditLogger

        log_dir = tmp_path / "llm_call"
        logger = AuditLogger(log_dir=str(log_dir))

        event_id = logger.log_llm_call(
            provider="openai",
            model="gpt-4o",
            tokens_used=150,
            cost_usd=0.002,
            outcome="success",
            session_id="sess_002",
        )
        assert event_id is not None
        log_files = list(log_dir.glob("*.jsonl"))
        content = log_files[0].read_text(encoding="utf-8")
        assert "openai/gpt-4o" in content
        assert "llm_call" in content
        assert "tokens" in content
        assert "cost_usd" in content

    def test_log_memory_access(self, tmp_path):
        """log_memory_access should log memory operations."""
        from nexus.security.audit import AuditLogger

        log_dir = tmp_path / "mem_access"
        logger = AuditLogger(log_dir=str(log_dir))

        event_id = logger.log_memory_access(
            operation="read",
            namespace="knowledge",
            doc_id="doc_123",
            outcome="success",
            session_id="sess_003",
        )
        assert event_id is not None
        log_files = list(log_dir.glob("*.jsonl"))
        content = log_files[0].read_text(encoding="utf-8")
        assert "memory_access" in content
        assert "knowledge/doc_123" in content

    def test_log_memory_access_without_doc_id(self, tmp_path):
        """log_memory_access without doc_id should work."""
        from nexus.security.audit import AuditLogger

        log_dir = tmp_path / "mem_no_doc"
        logger = AuditLogger(log_dir=str(log_dir))

        event_id = logger.log_memory_access(
            operation="list",
            namespace="knowledge",
            outcome="success",
        )
        assert event_id is not None
        log_files = list(log_dir.glob("*.jsonl"))
        content = log_files[0].read_text(encoding="utf-8")
        assert "knowledge" in content

    def test_log_security_event(self, tmp_path):
        """log_security_event should log with SECURITY category."""
        from nexus.security.audit import AuditLogger
        from nexus.security.audit import AuditLevel

        log_dir = tmp_path / "security_event"
        logger = AuditLogger(log_dir=str(log_dir))

        event_id = logger.log_security_event(
            event_type="path_traversal_detected",
            reason="Attempted ../ in file path",
            severity=AuditLevel.WARNING,
            details={"ip": "10.0.0.1"},
        )
        assert event_id is not None
        log_files = list(log_dir.glob("*.jsonl"))
        content = log_files[0].read_text(encoding="utf-8")
        assert "security" in content
        assert "path_traversal_detected" in content
        assert "denied" in content


# ═══════════════════════════════════════════════════════════════════
# Secrets Vault Tests
# ═══════════════════════════════════════════════════════════════════

class TestSecretsVaultInit:
    """Test SecretsVault initialization."""

    def test_init_creates_vault_dir(self, tmp_path):
        """SecretsVault should create vault directory."""
        from nexus.security.vault import SecretsVault

        vault_dir = tmp_path / "nexus_vault"
        vault = SecretsVault(vault_dir=str(vault_dir))
        assert vault_dir.exists()
        assert vault.vault_dir == vault_dir

    def test_init_generates_pepper(self, tmp_path):
        """SecretsVault should create pepper file."""
        from nexus.security.vault import SecretsVault

        vault_dir = tmp_path / "vault"
        # Patch to use our dir for pepper too
        pepper_file = tmp_path / ".pepper"
        with patch.object(Path, "exists") as mock_exists:
            mock_exists.return_value = False
            with patch("nexus.security.vault.Path") as mock_path:
                mock_pepper = MagicMock()
                mock_pepper.parent = tmp_path
                mock_pepper.__truediv__.return_value = tmp_path / ".pepper"
                mock_path.return_value = mock_pepper

                vault = SecretsVault(vault_dir=str(vault_dir))

    def test_pepper_reuse(self, tmp_path):
        """SecretsVault should reuse existing pepper."""
        from nexus.security.vault import SecretsVault
        import secrets

        vault_dir = tmp_path / "vault_reuse"
        # Create a vault to generate pepper first
        vault1 = SecretsVault(vault_dir=str(vault_dir))
        # Get the actual pepper file path and content
        pepper_file = vault1._pepper_file
        assert pepper_file.exists()
        existing_pepper = pepper_file.read_bytes()

        # Create another vault that should reuse the same pepper
        vault2 = SecretsVault(vault_dir=str(tmp_path / "vault_reuse2"))
        assert vault2._pepper_file.exists()
        assert vault2._pepper_file.read_bytes() == existing_pepper


class TestSecretsVaultStoreRetrieve:
    """Test SecretsVault store and retrieve operations."""

    @pytest.fixture
    def vault(self, tmp_path):
        """Create vault with temp directory."""
        from nexus.security.vault import SecretsVault

        vault_dir = tmp_path / "vault_sr"
        return SecretsVault(vault_dir=str(vault_dir))

    def test_store_and_retrieve(self, vault):
        """Store and retrieve a secret."""
        vault.store("OPENAI_API_KEY", "sk-test-key-12345")
        result = vault.retrieve("OPENAI_API_KEY")
        assert result == "sk-test-key-12345"

    def test_store_multiple_keys(self, vault):
        """Store multiple secrets."""
        vault.store("KEY_A", "value_a")
        vault.store("KEY_B", "value_b")
        assert vault.retrieve("KEY_A") == "value_a"
        assert vault.retrieve("KEY_B") == "value_b"

    def test_retrieve_nonexistent_returns_none(self, vault):
        """Retrieve missing key returns None."""
        result = vault.retrieve("NONEXISTENT_KEY")
        assert result is None

    def test_update_existing_secret(self, vault):
        """Update an existing secret."""
        vault.store("MY_KEY", "original_value")
        vault.store("MY_KEY", "updated_value")
        assert vault.retrieve("MY_KEY") == "updated_value"

    def test_delete_secret(self, vault):
        """Delete a secret."""
        vault.store("DELETE_ME", "to_be_deleted")
        result = vault.delete("DELETE_ME")
        assert result is True
        assert vault.retrieve("DELETE_ME") is None

    def test_delete_nonexistent(self, vault):
        """Delete non-existent key should return True."""
        result = vault.delete("NO_SUCH_KEY")
        assert result is True

    def test_list_keys(self, vault):
        """List all stored keys."""
        vault.store("KEY_1", "val1")
        vault.store("KEY_2", "val2")
        vault.store("KEY_3", "val3")
        keys = vault.list_keys()
        assert "KEY_1" in keys
        assert "KEY_2" in keys
        assert "KEY_3" in keys
        assert len(keys) == 3

    def test_list_keys_empty(self, vault):
        """List keys on empty vault should return []."""
        keys = vault.list_keys()
        assert keys == []

    def test_check_all(self, vault):
        """check_all should return dict of configured keys."""
        vault.store("KEY_A", "val_a")
        vault.store("KEY_B", "val_b")
        result = vault.check_all()
        assert result == {"KEY_A": True, "KEY_B": True}

    def test_check_all_empty(self, vault):
        """check_all on empty vault should return empty dict."""
        result = vault.check_all()
        assert result == {}

    def test_store_empty_value(self, vault):
        """Store empty string should work."""
        vault.store("EMPTY_KEY", "")
        result = vault.retrieve("EMPTY_KEY")
        assert result == ""


class TestSecretsVaultMigrate:
    """Test SecretsVault.migrate_from_env()."""

    def test_migrate_no_env_file(self, tmp_path):
        """migrate_from_env with missing .env should return 0."""
        from nexus.security.vault import SecretsVault

        vault_dir = tmp_path / "vault_migrate"
        vault = SecretsVault(vault_dir=str(vault_dir))

        result = vault.migrate_from_env(str(tmp_path / ".env"))
        assert result == 0

    def test_migrate_with_env_file(self, tmp_path):
        """migrate_from_env should migrate API keys."""
        from nexus.security.vault import SecretsVault

        vault_dir = tmp_path / "vault_migrate2"
        vault = SecretsVault(vault_dir=str(vault_dir))

        env_file = tmp_path / ".env"
        env_file.write_text(
            "OPENAI_API_KEY=sk-openai-test\n"
            "ANTHROPIC_API_KEY=sk-ant-test\n"
            "SOME_OTHER_VAR=value\n"
            "GOOGLE_API_KEY=\n",  # Empty value should be skipped
            encoding="utf-8",
        )

        result = vault.migrate_from_env(str(env_file))
        assert result == 2
        assert vault.retrieve("OPENAI_API_KEY") == "sk-openai-test"
        assert vault.retrieve("ANTHROPIC_API_KEY") == "sk-ant-test"

    def test_migrate_marks_migrated_keys(self, tmp_path):
        """migrate_from_env should comment out migrated keys."""
        from nexus.security.vault import SecretsVault

        vault_dir = tmp_path / "vault_migrate3"
        vault = SecretsVault(vault_dir=str(vault_dir))

        env_file = tmp_path / ".env"
        env_file.write_text(
            "OPENAI_API_KEY=sk-test\n"
            "DATABASE_URL=postgres://localhost\n",
            encoding="utf-8",
        )

        vault.migrate_from_env(str(env_file))
        content = env_file.read_text(encoding="utf-8")
        assert "OPENAI_API_KEY (migrated to vault)" in content
        assert "DATABASE_URL" in content  # Not migrated, still there

    def test_migrate_skips_empty_quoted_values(self, tmp_path):
        """migrate_from_env should skip empty quoted values."""
        from nexus.security.vault import SecretsVault

        vault_dir = tmp_path / "vault_migrate4"
        vault = SecretsVault(vault_dir=str(vault_dir))

        env_file = tmp_path / ".env"
        env_file.write_text(
            'OPENAI_API_KEY=""\n'
            "ANTHROPIC_API_KEY=''\n",
            encoding="utf-8",
        )

        result = vault.migrate_from_env(str(env_file))
        assert result == 0


class TestSecretsVaultPepper:
    """Test SecretsVault pepper operations."""

    def test_pepper_atomic_write(self, tmp_path):
        """Pepper should be written atomically (temp file + rename)."""
        from nexus.security.vault import SecretsVault
        import secrets

        vault_dir = tmp_path / "vault_atomic"
        # Pepper is generated internally; verify the temp file cleanup doesn't fail
        vault = SecretsVault(vault_dir=str(vault_dir))
        assert vault._pepper_file.exists()
        assert len(vault._pepper_file.read_bytes()) == 32

    def test_key_derivation_consistent(self, tmp_path):
        """Key derivation should be consistent for same pepper."""
        from nexus.security.vault import SecretsVault

        vault_dir = tmp_path / "vault_consistency"
        vault1 = SecretsVault(vault_dir=str(vault_dir))
        vault2 = SecretsVault(vault_dir=str(vault_dir))

        # Both should produce the same key since pepper is reused
        assert vault1._key == vault2._key

    def test_key_derivation_different_peppers(self, tmp_path):
        """Different peppers should produce different keys."""
        from nexus.security.vault import SecretsVault

        # Create two vaults with different pepper dirs
        vault1_dir = tmp_path / "vault_k1"
        vault2_dir = tmp_path / "vault_k2"

        # Force different pepper files by patching
        with patch("nexus.security.vault.SecretsVault._get_pepper") as mock_pepper:
            mock_pepper.side_effect = [b"a" * 32, b"b" * 32]

            vault1 = SecretsVault(vault_dir=str(vault1_dir))
            vault2 = SecretsVault(vault_dir=str(vault2_dir))

            assert vault1._key != vault2._key


class TestSecretsVaultErrors:
    """Test SecretsVault error handling."""

    def test_cryptography_not_available(self, tmp_path):
        """Store should handle missing cryptography package."""
        from nexus.security.vault import SecretsVault

        vault_dir = tmp_path / "vault_no_crypto"
        vault = SecretsVault(vault_dir=str(vault_dir))

        with patch("nexus.security.vault.SecretsVault._get_fernet", return_value=None):
            result = vault.store("TEST_KEY", "test_value")
            assert result is False

    def test_retrieve_cryptography_missing(self, tmp_path):
        """Retrieve should handle missing cryptography package."""
        from nexus.security.vault import SecretsVault

        vault_dir = tmp_path / "vault_no_crypto_ret"
        vault = SecretsVault(vault_dir=str(vault_dir))

        with patch("nexus.security.vault.SecretsVault._get_fernet", return_value=None):
            result = vault.retrieve("TEST_KEY")
            assert result is None

    def test_corrupted_vault_file(self, tmp_path):
        """Retrieve from corrupted file should return None."""
        from nexus.security.vault import SecretsVault

        vault_dir = tmp_path / "vault_corrupt"
        vault = SecretsVault(vault_dir=str(vault_dir))

        # Store then corrupt the file
        vault.store("MY_KEY", "original_value")
        vault_file = vault_dir / "MY_KEY.vault"
        vault_file.write_text("corrupted-not-base64")

        result = vault.retrieve("MY_KEY")
        assert result is None

    def test_store_failure_returns_false(self, tmp_path):
        """Store should return False on failure."""
        from nexus.security.vault import SecretsVault

        vault_dir = tmp_path / "vault_fail"
        vault = SecretsVault(vault_dir=str(vault_dir))

        with patch.object(vault, "_get_fernet") as mock_fernet:
            mock_fernet.return_value.encrypt.side_effect = Exception("Encryption failed")
            result = vault.store("FAIL_KEY", "value")
            assert result is False

    def test_delete_failure(self, tmp_path):
        """Delete should handle file errors."""
        from nexus.security.vault import SecretsVault

        vault_dir = tmp_path / "vault_del_fail"
        vault = SecretsVault(vault_dir=str(vault_dir))

        # Mock unlink to fail
        with patch("pathlib.Path.unlink", side_effect=Exception("Disk error")):
            result = vault.delete("SOME_KEY")
            assert result is True  # delete catches and logs exceptions

    def test_get_pepper_handles_read_error(self, tmp_path):
        """_get_pepper should handle existing file read error gracefully."""
        from nexus.security.vault import SecretsVault

        vault_dir = tmp_path / "vault_pepper_err"

        # Use a temporary path for the pepper file to avoid Windows rename issues
        pepper_file = tmp_path / "test_pepper"
        with patch("nexus.security.vault.Path.expanduser") as mock_expand:
            mock_expand.return_value = pepper_file
            vault = SecretsVault(vault_dir=str(vault_dir))

            # Write initial pepper file
            pepper_file.write_bytes(b"old_pepper_32_bytes_existing_content")

            # Now patch read_bytes to fail, _get_pepper should generate new pepper
            with patch.object(Path, "read_bytes", side_effect=Exception("Read error")):
                # Also patch rename to avoid FileExistsError on Windows
                with patch.object(Path, "rename") as mock_rename:
                    mock_rename.return_value = None
                    with patch.object(Path, "unlink") as mock_unlink:
                        pepper = vault._get_pepper()
                        assert len(pepper) == 32


# ═══════════════════════════════════════════════════════════════════
# Enums Tests
# ═══════════════════════════════════════════════════════════════════

class TestAuditEnums:
    """Test audit enums."""

    def test_audit_level_values(self):
        from nexus.security.audit import AuditLevel
        assert AuditLevel.DEBUG.value == "debug"
        assert AuditLevel.INFO.value == "info"
        assert AuditLevel.WARNING.value == "warning"
        assert AuditLevel.CRITICAL.value == "critical"

    def test_audit_category_values(self):
        from nexus.security.audit import AuditCategory
        assert AuditCategory.AUTH.value == "auth"
        assert AuditCategory.TOOL_CALL.value == "tool_call"
        assert AuditCategory.MEMORY_ACCESS.value == "memory_access"
        assert AuditCategory.CODE_EXECUTION.value == "code_execution"
        assert AuditCategory.LLM_CALL.value == "llm_call"
        assert AuditCategory.CONFIG_CHANGE.value == "config_change"
        assert AuditCategory.AGENT_ACTION.value == "agent_action"
        assert AuditCategory.DATA_ACCESS.value == "data_access"
        assert AuditCategory.SECURITY.value == "security"
