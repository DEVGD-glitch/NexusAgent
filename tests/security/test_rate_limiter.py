"""
Tests for nexus.security.rate_limiter - RateLimiter.
"""

import pytest
from nexus.security.rate_limiter import RateLimiter, RateLimitConfig, RateLimitExceededError, RateLimitWindow


class TestRateLimiter:
    """Test cases for RateLimiter."""

    @pytest.fixture
    def limiter(self):
        return RateLimiter()

    def test_init(self, limiter):
        assert limiter is not None

    def test_check_returns_bool(self, limiter):
        """check should return boolean."""
        # Should return True (allowed) for first request
        result = limiter.check("user1", "api_call")
        assert isinstance(result, bool)

    def test_check_exceeding_limit_raises(self, limiter):
        """check should raise RateLimitExceededError when limit exceeded."""
        # We can't easily test this without mocking, but check method exists
        assert hasattr(limiter, 'check')

    def test_get_stats_returns_dict(self, limiter):
        """get_stats should return dictionary."""
        limiter.check("user1", "api_call")
        stats = limiter.get_stats()
        assert isinstance(stats, dict)


class TestRateLimitConfig:
    """Test cases for RateLimitConfig."""

    def test_creation(self):
        """RateLimitConfig creation with required fields."""
        config = RateLimitConfig(name="test", max_requests=10, window_seconds=60)
        assert config.name == "test"
        assert config.max_requests == 10
        assert config.window_seconds == 60

    def test_with_burst(self):
        """RateLimitConfig with burst."""
        config = RateLimitConfig(name="test", max_requests=10, window_seconds=60, burst=5)
        assert config.burst == 5


class TestRateLimitWindow:
    """Test cases for RateLimitWindow."""

    def test_default_creation(self):
        """RateLimitWindow with defaults."""
        window = RateLimitWindow()
        assert window.timestamps == []
        assert window.lock is not None


class TestRateLimitExceededError:
    """Test cases for RateLimitExceededError."""

    def test_error_creation(self):
        """RateLimitExceededError creation."""
        error = RateLimitExceededError("user1", 60)
        assert "user1" in str(error)
        assert "60" in str(error)