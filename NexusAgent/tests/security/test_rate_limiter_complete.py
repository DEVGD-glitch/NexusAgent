"""
Complete tests for nexus.security.rate_limiter - RateLimiter.

Covers remaining lines: check() with burst allowance, is_allowed() with
different limits, get_remaining() for different actions, add_limit() custom
config, reset() for identifier/action/all, get_stats() with active windows,
_get_key() formatting, RateLimitWindow lock, cleanup, and warning logging.
"""

import time
from unittest.mock import patch

import pytest

from nexus.security.rate_limiter import (
    RateLimiter,
    RateLimitConfig,
    RateLimitExceededError,
    RateLimitWindow,
)


class TestRateLimiterComplete:
    """Complete tests for RateLimiter — remaining uncovered paths."""

    @pytest.fixture
    def limiter(self):
        return RateLimiter()

    # ── check() with burst ──────────────────────────────────────────

    def test_check_with_burst_allowance(self, limiter):
        """Burst allows exceeding the base limit."""
        limiter.add_limit("test_burst", max_requests=5, window_seconds=60, burst=3)
        # effective = 5 + 3 = 8
        for _ in range(8):
            assert limiter.check("burst_user", "test_burst") is True
        # 9th should raise
        with pytest.raises(RateLimitExceededError):
            limiter.check("burst_user", "test_burst")

    def test_check_unknown_action_allowed(self, limiter):
        """check with unknown action returns True."""
        result = limiter.check("user", "unknown_action")
        assert result is True

    # ── is_allowed() ────────────────────────────────────────────────

    def test_is_allowed_returns_true(self, limiter):
        """is_allowed returns True when under limit."""
        assert limiter.is_allowed("user1", "api_call") is True

    def test_is_allowed_returns_false(self, limiter):
        """is_allowed returns False when over effective limit."""
        limiter.add_limit("test_limit", max_requests=2, window_seconds=60, burst=0)
        limiter.check("user1", "test_limit")
        limiter.check("user1", "test_limit")
        assert limiter.is_allowed("user1", "test_limit") is False

    def test_is_allowed_unknown_action(self, limiter):
        """is_allowed with unknown action returns True."""
        assert limiter.is_allowed("user", "unknown_action") is True

    # ── get_remaining() ─────────────────────────────────────────────

    def test_get_remaining_returns_dict(self, limiter):
        """get_remaining returns proper dict structure."""
        remaining = limiter.get_remaining("user1", "api_call")
        assert "remaining" in remaining
        assert "limit" in remaining
        assert "burst" in remaining
        assert "current_count" in remaining
        assert "window_seconds" in remaining

    def test_get_remaining_after_consuming(self, limiter):
        """get_remaining decreases after check()."""
        limiter.add_limit("test_limit", max_requests=10, window_seconds=60, burst=0)
        limiter.check("user1", "test_limit")
        limiter.check("user1", "test_limit")
        remaining = limiter.get_remaining("user1", "test_limit")
        assert remaining["remaining"] == 8
        assert remaining["current_count"] == 2

    def test_get_remaining_unknown_action(self, limiter):
        """get_remaining with unknown action returns infinity."""
        remaining = limiter.get_remaining("user", "unknown_action")
        assert remaining["remaining"] == float("inf")

    def test_get_remaining_for_tool_call(self, limiter):
        """get_remaining works for tool_call config."""
        remaining = limiter.get_remaining("user1", "tool_call")
        assert remaining["limit"] == 120
        assert remaining["burst"] == 20
        assert remaining["window_seconds"] == 60

    def test_get_remaining_for_llm_call(self, limiter):
        """get_remaining works for llm_call config."""
        remaining = limiter.get_remaining("user1", "llm_call")
        assert remaining["limit"] == 60
        assert remaining["burst"] == 10

    def test_get_remaining_for_code_execution(self, limiter):
        """get_remaining works for code_execution config."""
        remaining = limiter.get_remaining("user1", "code_execution")
        assert remaining["limit"] == 30
        assert remaining["burst"] == 5

    # ── add_limit() ─────────────────────────────────────────────────

    def test_add_limit_creates_config(self, limiter):
        """add_limit creates a new rate limit config."""
        limiter.add_limit("custom_action", max_requests=50, window_seconds=30, burst=5)
        config = limiter._configs["custom_action"]
        assert config.max_requests == 50
        assert config.window_seconds == 30
        assert config.burst == 5
        assert config.name == "custom_action"

    def test_add_limit_updates_existing(self, limiter):
        """add_limit updates an existing rate limit config."""
        limiter.add_limit("api_call", max_requests=100, window_seconds=120, burst=20)
        config = limiter._configs["api_call"]
        assert config.max_requests == 100
        assert config.window_seconds == 120
        assert config.burst == 20

    def test_add_limit_default_burst_zero(self, limiter):
        """add_limit defaults burst to 0."""
        limiter.add_limit("no_burst", max_requests=10, window_seconds=60)
        assert limiter._configs["no_burst"].burst == 0

    # ── reset() ─────────────────────────────────────────────────────

    def test_reset_identifier_and_action(self, limiter):
        """reset with identifier + action removes only that window."""
        limiter.check("user1", "api_call")
        limiter.check("user1", "tool_call")
        assert "user1:api_call" in limiter._windows
        assert "user1:tool_call" in limiter._windows
        limiter.reset(identifier="user1", action="api_call")
        assert "user1:api_call" not in limiter._windows
        assert "user1:tool_call" in limiter._windows

    def test_reset_identifier_only(self, limiter):
        """reset with only identifier removes all windows for that user."""
        limiter.check("user1", "api_call")
        limiter.check("user1", "tool_call")
        limiter.check("user2", "api_call")
        limiter.reset(identifier="user1")
        assert all(not k.startswith("user1:") for k in limiter._windows)
        assert "user2:api_call" in limiter._windows

    def test_reset_action_only(self, limiter):
        """reset with only action hits else branch (clears all)."""
        limiter.check("user1", "api_call")
        limiter.check("user1", "tool_call")
        limiter.reset(action="api_call")
        # identifier=None is falsy, so falls to else → clears all windows
        assert len(limiter._windows) == 0

    def test_reset_all(self, limiter):
        """reset with no args clears all windows."""
        limiter.check("user1", "api_call")
        limiter.check("user2", "tool_call")
        assert len(limiter._windows) == 2
        limiter.reset()
        assert len(limiter._windows) == 0

    def test_reset_with_none_values(self, limiter):
        """reset with both None clears all windows."""
        limiter.check("user1", "api_call")
        limiter.reset(identifier=None, action=None)
        assert len(limiter._windows) == 0

    # ── get_stats() ─────────────────────────────────────────────────

    def test_get_stats_with_active_windows(self, limiter):
        """get_stats shows active windows count."""
        limiter.check("user1", "api_call")
        limiter.check("user2", "tool_call")
        stats = limiter.get_stats()
        assert stats["active_windows"] == 2

    def test_get_stats_configured_limits(self, limiter):
        """get_stats includes all configured limits."""
        stats = limiter.get_stats()
        limits = stats["configured_limits"]
        assert "api_call" in limits
        assert "tool_call" in limits
        assert "code_execution" in limits
        assert "llm_call" in limits
        assert limits["api_call"]["max"] == 60
        assert limits["api_call"]["burst"] == 10
        assert limits["api_call"]["window_s"] == 60

    def test_get_stats_no_active_windows(self, limiter):
        """get_stats returns zero active windows when none used."""
        stats = limiter.get_stats()
        assert stats["active_windows"] == 0

    # ── _get_key() formatting ───────────────────────────────────────

    def test_get_key_standard(self):
        """_get_key formats identifier:action."""
        limiter = RateLimiter()
        key = limiter._get_key("user_123", "api_call")
        assert key == "user_123:api_call"

    def test_get_key_empty_values(self):
        """_get_key handles empty strings."""
        limiter = RateLimiter()
        key = limiter._get_key("", "")
        assert key == ":"

    def test_get_key_special_chars(self):
        """_get_key handles identifiers with special chars."""
        limiter = RateLimiter()
        key = limiter._get_key("user@host:8080", "tool:call")
        assert key == "user@host:8080:tool:call"

    # ── RateLimitWindow ─────────────────────────────────────────────

    def test_window_lock_behaves_as_lock(self):
        """RateLimitWindow.lock behaves as a lock object."""
        window = RateLimitWindow()
        # threading.Lock is a factory function in Python 3.12+, not a class
        # Verify it behaves like a lock instead
        assert window.lock.acquire(timeout=0.01) is True
        window.lock.release()

    def test_window_lock_usage(self):
        """RateLimitWindow lock can be acquired and released."""
        window = RateLimitWindow()
        with window.lock:
            window.timestamps.append(1.0)
        assert len(window.timestamps) == 1

    def test_window_lock_repr_excluded(self):
        """RateLimitWindow repr does not include lock."""
        window = RateLimitWindow()
        assert "lock" not in repr(window)

    # ── _cleanup_old_entries ────────────────────────────────────────

    def test_cleanup_removes_old_entries(self, limiter):
        """_cleanup_old_entries removes timestamps outside window."""
        window = RateLimitWindow()
        now = time.monotonic()
        window.timestamps.append(now - 120)  # 120s old — outside 60s window
        window.timestamps.append(now - 10)   # 10s old — inside window
        limiter._cleanup_old_entries(window, 60)
        assert len(window.timestamps) == 1
        assert window.timestamps[0] > now - 60

    def test_cleanup_all_expired(self, limiter):
        """_cleanup_old_entries removes all when all expired."""
        window = RateLimitWindow()
        now = time.monotonic()
        window.timestamps.append(now - 120)
        window.timestamps.append(now - 90)
        limiter._cleanup_old_entries(window, 60)
        assert len(window.timestamps) == 0

    def test_cleanup_empty_window(self, limiter):
        """_cleanup_old_entries handles empty window."""
        window = RateLimitWindow()
        limiter._cleanup_old_entries(window, 60)
        assert len(window.timestamps) == 0

    # ── Logger warning on rate exceed ───────────────────────────────

    def test_logger_warning_on_exceed(self, limiter):
        """check logs warning when rate limit exceeded."""
        limiter.add_limit("test_warn", max_requests=1, window_seconds=60, burst=0)
        limiter.check("logger_user", "test_warn")
        with patch("nexus.security.rate_limiter.logger") as mock_logger:
            with pytest.raises(RateLimitExceededError):
                limiter.check("logger_user", "test_warn")
            mock_logger.warning.assert_called_once()

    def test_logger_warning_message_content(self, limiter):
        """Warning log contains identifier, action, and counts."""
        limiter.add_limit("test_msg", max_requests=1, window_seconds=60, burst=0)
        limiter.check("log_user", "test_msg")
        with patch("nexus.security.rate_limiter.logger") as mock_logger:
            with pytest.raises(RateLimitExceededError):
                limiter.check("log_user", "test_msg")
            args, _ = mock_logger.warning.call_args
            formatted = args[0] % args[1:]
            assert "log_user" in formatted
            assert "test_msg" in formatted

    # ── RateLimitConfig with burst ──────────────────────────────────

    def test_rate_limit_config_default_burst(self):
        """RateLimitConfig defaults burst to 0."""
        config = RateLimitConfig(name="test", max_requests=10, window_seconds=60)
        assert config.burst == 0

    def test_rate_limit_config_with_burst(self):
        """RateLimitConfig with explicit burst."""
        config = RateLimitConfig(name="test", max_requests=10, window_seconds=60, burst=5)
        assert config.burst == 5

    # ── Integration: check with tokens > 1 ──────────────────────────

    def test_check_with_multiple_tokens(self, limiter):
        """check consumes multiple tokens at once."""
        limiter.add_limit("multi_token", max_requests=10, window_seconds=60, burst=0)
        # Consume 5 tokens at once
        limiter.check("multi_user", "multi_token", tokens=5)
        remaining = limiter.get_remaining("multi_user", "multi_token")
        assert remaining["current_count"] == 5

    def test_check_multiple_tokens_exceeds(self, limiter):
        """check with tokens exceeding limit raises."""
        limiter.add_limit("multi_exceed", max_requests=5, window_seconds=60, burst=0)
        with pytest.raises(RateLimitExceededError):
            limiter.check("multi_user", "multi_exceed", tokens=10)

    # ── get_remaining uses max not effective_limit ──────────────────

    def test_get_remaining_remaining_uses_max_no_burst(self, limiter):
        """get_remaining remaining uses max_requests (not effective_limit)."""
        limiter.add_limit("rem_test", max_requests=10, window_seconds=60, burst=5)
        limiter.check("rem_user", "rem_test")
        remaining = limiter.get_remaining("rem_user", "rem_test")
        # remaining = max(0, max_requests - current_count) = 10 - 1 = 9
        # effective is 15, but remaining reports max - current
        assert remaining["remaining"] == 9
        assert remaining["limit"] == 10
        assert remaining["burst"] == 5
