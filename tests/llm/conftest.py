"""
Shared fixtures for LLM tests.

Patches get_settings() at every module that imports it, since
'from nexus.core.config import get_settings' creates module-level
references that aren't affected by patching the source.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# All modules that import get_settings() at import time
_GET_SETTINGS_TARGETS = [
    "nexus.llm.router.get_settings",
    "nexus.llm.fallback.get_settings",
    "nexus.llm.providers.anthropic_provider.get_settings",
    "nexus.llm.providers.gemini_provider.get_settings",
    "nexus.llm.providers.glm_provider.get_settings",
    "nexus.llm.providers.ollama_provider.get_settings",
    "nexus.llm.providers.openai_provider.get_settings",
]


@pytest.fixture
def mock_settings():
    """Mock get_settings in ALL importing modules with test API keys."""
    settings = MagicMock()
    settings.openai_api_key = "sk-test-openai"
    settings.anthropic_api_key = "sk-test-anthropic"
    settings.google_api_key = "sk-test-google"
    settings.zai_api_key = "sk-test-zai"
    settings.zai_base_url = "https://open.bigmodel.cn/api/paas/v4"
    settings.ollama_base_url = "http://127.0.0.1:11434"
    settings.ollama_default_model = "llama3.1:8b"
    settings.llm_timeout_seconds = 30
    settings.llm_default_provider = "openai"
    settings.llm_default_model = "gpt-4o"
    settings.llm_fallback_chain = "openai,anthropic,gemini,glm,ollama"
    settings.fallback_providers = ["openai", "anthropic", "gemini", "glm", "ollama"]
    settings.llm_max_retries = 3
    settings.nexus_env = "development"
    settings.nexus_host = "0.0.0.0"
    settings.nexus_port = 8080

    patchers = [patch(target, return_value=settings) for target in _GET_SETTINGS_TARGETS]
    for p in patchers:
        p.start()
    yield settings
    for p in patchers:
        p.stop()
    # Clear the LRU cache on the real get_settings to ensure
    # subsequent tests (including those outside tests/llm/) get
    # a fresh NexusConfig from .env rather than a stale cached mock.
    from nexus.core.config import reload_settings
    reload_settings()


@pytest.fixture
def mock_litellm_response():
    """Create a standard mocked LiteLLM response."""
    mock = MagicMock()
    mock.choices = [MagicMock()]
    mock.choices[0].message.content = "Hello from LiteLLM!"
    mock.choices[0].finish_reason = "stop"
    mock.usage.prompt_tokens = 10
    mock.usage.completion_tokens = 20
    mock.usage.total_tokens = 30
    return mock


@pytest.fixture
def mock_http_response():
    """Create a factory for mocked HTTP responses."""

    def _make(status_code=200, json_data=None):
        mock = MagicMock()
        mock.status_code = status_code
        mock.json.return_value = json_data or {}
        mock.text = json_data and str(json_data) or "{}"
        mock.headers = {}
        return mock

    return _make


@pytest.fixture
def mock_async_client():
    """Create a mocked httpx.AsyncClient — post is async, stream is NOT.

    httpx.AsyncClient.stream() returns an async context manager
    synchronously (it's not a coroutine), so stream must be a
    regular MagicMock, not an AsyncMock.
    """

    def _make(post_response=None, stream_response=None):
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=post_response or MagicMock(status_code=200))
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        if stream_response:
            mock_client.stream = MagicMock(return_value=stream_response)
        else:
            mock_client.stream = MagicMock()

        return mock_client

    return _make


@pytest.fixture
def mock_stream_response():
    """Create a mocked streaming HTTP response.

    aiter_lines is set as a callable (async function) that returns
    an async generator, because the code calls response.aiter_lines()
    with parentheses.
    """

    def _make(status_code=200, lines=None):
        mock = AsyncMock()
        mock.status_code = status_code
        mock.__aenter__.return_value = mock
        mock.__aexit__.return_value = None

        async def _aiter_lines_func():
            for line in (lines or []):
                yield line

        mock.aiter_lines = _aiter_lines_func
        return mock

    return _make
