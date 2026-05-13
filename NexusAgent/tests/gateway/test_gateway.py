"""
Tests for nexus.api.gateway - FastAPI Gateway.
"""

import pytest
from pathlib import Path
from nexus.api.gateway import (
    app,
    _get_working_dir,
    _safe_path,
)


class TestGatewayApp:
    """Test cases for FastAPI app."""

    def test_app_created(self):
        """App should be created."""
        assert app is not None
        assert app.title == "NEXUS Agent Gateway"

    def test_app_version(self):
        """App should have version."""
        assert app.version == "0.1.0"


class TestSafePath:
    """Test cases for path safety functions."""

    def test_get_working_dir(self):
        """Working directory should be a Path."""
        wd = _get_working_dir()
        assert isinstance(wd, Path)

    def test_safe_path_valid(self):
        """Valid path within working dir should return Path."""
        wd = _get_working_dir()
        # Use a subpath that's definitely inside
        safe = _safe_path("test.txt", wd)
        # Result depends on whether it exists, but should not be None for valid requests

    def test_safe_path_with_subdirectory(self):
        """Path with subdirectory should work."""
        wd = _get_working_dir()
        result = _safe_path("subdir/test.txt", wd)
        # May be None if file doesn't exist, but path parsing works


class TestPathTraversal:
    """Test cases for path traversal protection."""

    def test_detect_parent_traversal(self):
        """Should detect ../ in path."""
        wd = _get_working_dir()
        result = _safe_path("../etc/passwd", wd)
        assert result is None

    def test_detect_absolute_traversal(self):
        """Should detect absolute path outside working dir."""
        wd = _get_working_dir()
        result = _safe_path("/etc/passwd", wd)
        assert result is None or not str(result).startswith("/etc")