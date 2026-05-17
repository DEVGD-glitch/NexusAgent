"""Tests for the Monitoring System."""

import pytest
from nexus.monitoring.metrics import SystemMetrics, TokenUsage, ToolCallRecord, ErrorRecord
from nexus.monitoring.collector import MetricsCollector


class TestSystemMetrics:
    def test_default_values(self):
        m = SystemMetrics()
        assert m.cpu_percent >= 0
        assert m.memory_mb >= 0
        assert m.tokens_used_today == 0
        assert m.tool_calls_today == 0

    def test_to_dict(self):
        m = SystemMetrics(cpu_percent=25.0, memory_mb=512)
        d = m.to_dict()
        assert d["cpu_percent"] == 25.0
        assert d["memory_mb"] == 512


class TestTokenUsage:
    def test_create(self):
        t = TokenUsage(provider="openai", model="gpt-4", prompt_tokens=100, completion_tokens=50)
        assert t.prompt_tokens == 100
        assert t.completion_tokens == 50

    def test_to_dict(self):
        t = TokenUsage(provider="openai", model="gpt-4", prompt_tokens=10, completion_tokens=5)
        d = t.to_dict()
        assert d["provider"] == "openai"
        assert d["prompt_tokens"] == 10


class TestToolCallRecord:
    def test_create(self):
        r = ToolCallRecord(tool_name="read_file", duration_ms=50.0, success=True)
        assert r.tool_name == "read_file"
        assert r.success is True


class TestErrorRecord:
    def test_create(self):
        e = ErrorRecord(error_type="timeout", details="Request timed out")
        assert e.error_type == "timeout"
        assert e.details == "Request timed out"


class TestMetricsCollector:
    def setup_method(self):
        self.collector = MetricsCollector()

    def test_record_token_usage(self):
        usage = TokenUsage(provider="openai", model="gpt-4", prompt_tokens=100, completion_tokens=50)
        self.collector.record_token_usage(usage)
        data = self.collector.get_token_usage()
        assert isinstance(data, (dict, list))

    def test_record_tool_call(self):
        call = ToolCallRecord(tool_name="read_file", duration_ms=25.0, success=True)
        self.collector.record_tool_call(call)
        metrics = self.collector.get_current_metrics()
        assert metrics.tool_calls_today >= 1

    def test_record_error(self):
        self.collector.record_error("timeout", "Request timed out")
        metrics = self.collector.get_current_metrics()
        assert metrics.errors_last_hour >= 1

    def test_get_token_usage(self):
        usage = TokenUsage(provider="openai", model="gpt-4", prompt_tokens=100, completion_tokens=50)
        self.collector.record_token_usage(usage)
        data = self.collector.get_token_usage()
        assert isinstance(data, (dict, list))

    def test_get_tool_stats(self):
        call = ToolCallRecord(tool_name="read_file", duration_ms=10.0, success=True)
        self.collector.record_tool_call(call)
        data = self.collector.get_tool_stats()
        assert isinstance(data, (dict, list))

    def test_get_error_stats(self):
        self.collector.record_error("timeout", "details")
        data = self.collector.get_error_stats()
        assert isinstance(data, (dict, list))

    def test_get_status(self):
        status = self.collector.get_status()
        assert isinstance(status, dict)
