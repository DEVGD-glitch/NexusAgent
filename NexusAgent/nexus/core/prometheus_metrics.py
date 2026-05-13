"""
NEXUS Prometheus Metrics — Production-ready observability.

Provides Prometheus-compatible metrics for monitoring:
- Request rates and latencies
- LLM token usage and costs
- Memory system performance
- Agent execution metrics
- System health indicators

Usage:
    from nexus.core.prometheus_metrics import metrics
    metrics.inc_request_total("/chat", "success")
    metrics.observe_llm_tokens(1500, "gpt-4")
"""

import time
from typing import Optional
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)


class NexusMetrics:
    """Prometheus metrics collector for NEXUS Agent."""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or CollectorRegistry()
        self._register_metrics()
    
    def _register_metrics(self):
        """Register all Prometheus metrics."""
        
        # HTTP Requests
        self.request_total = Counter(
            'nexus_http_requests_total',
            'Total number of HTTP requests',
            ['endpoint', 'status', 'method'],
            registry=self.registry,
        )
        
        self.request_latency = Histogram(
            'nexus_http_request_latency_seconds',
            'HTTP request latency in seconds',
            ['endpoint', 'method'],
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
            registry=self.registry,
        )
        
        self.requests_in_progress = Gauge(
            'nexus_http_requests_in_progress',
            'Number of HTTP requests currently being processed',
            ['endpoint'],
            registry=self.registry,
        )
        
        # LLM Metrics
        self.llm_tokens_total = Counter(
            'nexus_llm_tokens_total',
            'Total number of tokens processed by LLM',
            ['provider', 'model', 'type'],
            registry=self.registry,
        )
        
        self.llm_requests_total = Counter(
            'nexus_llm_requests_total',
            'Total number of LLM API requests',
            ['provider', 'model', 'status'],
            registry=self.registry,
        )
        
        self.llm_latency = Histogram(
            'nexus_llm_request_latency_seconds',
            'LLM API request latency in seconds',
            ['provider', 'model'],
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
            registry=self.registry,
        )
        
        self.llm_cost_usd = Counter(
            'nexus_llm_cost_usd_total',
            'Estimated cost of LLM usage in USD',
            ['provider', 'model'],
            registry=self.registry,
        )
        
        # Memory System
        self.memory_embeddings_total = Counter(
            'nexus_memory_embeddings_total',
            'Total number of embeddings stored',
            ['layer', 'collection'],
            registry=self.registry,
        )
        
        self.memory_queries_total = Counter(
            'nexus_memory_queries_total',
            'Total number of memory queries',
            ['layer', 'status'],
            registry=self.registry,
        )
        
        self.memory_query_latency = Histogram(
            'nexus_memory_query_latency_seconds',
            'Memory query latency in seconds',
            ['layer'],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
            registry=self.registry,
        )
        
        # Agent Execution
        self.agent_tasks_total = Counter(
            'nexus_agent_tasks_total',
            'Total number of agent tasks executed',
            ['agent_type', 'status', 'orchestrator'],
            registry=self.registry,
        )
        
        self.agent_task_duration = Histogram(
            'nexus_agent_task_duration_seconds',
            'Agent task execution duration',
            ['agent_type', 'orchestrator'],
            buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0),
            registry=self.registry,
        )
        
        self.agent_steps_total = Counter(
            'nexus_agent_steps_total',
            'Total number of reasoning steps taken by agents',
            ['agent_type', 'strategy'],
            registry=self.registry,
        )
        
        self.agent_tools_called = Counter(
            'nexus_agent_tools_called_total',
            'Total number of tool calls by agents',
            ['tool_name', 'status'],
            registry=self.registry,
        )
        
        # WebSocket Events
        self.websocket_connections = Gauge(
            'nexus_websocket_connections',
            'Number of active WebSocket connections',
            registry=self.registry,
        )
        
        self.websocket_messages_total = Counter(
            'nexus_websocket_messages_total',
            'Total number of WebSocket messages sent',
            ['event_type'],
            registry=self.registry,
        )
        
        # System Metrics
        self.system_cpu_percent = Gauge(
            'nexus_system_cpu_percent',
            'CPU usage percentage',
            registry=self.registry,
        )
        
        self.system_memory_percent = Gauge(
            'nexus_system_memory_percent',
            'Memory usage percentage',
            registry=self.registry,
        )
        
        self.system_disk_percent = Gauge(
            'nexus_system_disk_percent',
            'Disk usage percentage',
            registry=self.registry,
        )
        
        self.system_uptime_seconds = Gauge(
            'nexus_system_uptime_seconds',
            'System uptime in seconds',
            registry=self.registry,
        )
        
        # Subsystem Health
        self.subsystem_health = Gauge(
            'nexus_subsystem_health',
            'Health status of subsystems (1=healthy, 0=unhealthy)',
            ['subsystem'],
            registry=self.registry,
        )
        
        # Security
        self.security_violations_total = Counter(
            'nexus_security_violations_total',
            'Total number of security violations detected',
            ['violation_type', 'action'],
            registry=self.registry,
        )
        
        self.sandbox_executions_total = Counter(
            'nexus_sandbox_executions_total',
            'Total number of sandboxed code executions',
            ['status'],
            registry=self.registry,
        )
    
    def inc_request_total(self, endpoint: str, status: str, method: str = "POST"):
        self.request_total.labels(endpoint=endpoint, status=status, method=method).inc()
    
    def observe_request_latency(self, endpoint: str, method: str, duration: float):
        self.request_latency.labels(endpoint=endpoint, method=method).observe(duration)
    
    def inc_requests_in_progress(self, endpoint: str):
        self.requests_in_progress.labels(endpoint=endpoint).inc()
    
    def dec_requests_in_progress(self, endpoint: str):
        self.requests_in_progress.labels(endpoint=endpoint).dec()
    
    def observe_llm_tokens(self, tokens: int, provider: str, model: str, token_type: str = "completion"):
        self.llm_tokens_total.labels(provider=provider, model=model, type=token_type).inc(tokens)
    
    def inc_llm_request(self, provider: str, model: str, status: str = "success"):
        self.llm_requests_total.labels(provider=provider, model=model, status=status).inc()
    
    def observe_llm_latency(self, provider: str, model: str, duration: float):
        self.llm_latency.labels(provider=provider, model=model).observe(duration)
    
    def observe_llm_cost(self, cost_usd: float, provider: str, model: str):
        self.llm_cost_usd.labels(provider=provider, model=model).inc(cost_usd)
    
    def set_memory_embeddings(self, count: int, layer: str, collection: str):
        self.memory_embeddings_total.labels(layer=layer, collection=collection).inc(count)
    
    def inc_memory_query(self, layer: str, status: str = "success"):
        self.memory_queries_total.labels(layer=layer, status=status).inc()
    
    def observe_memory_query_latency(self, layer: str, duration: float):
        self.memory_query_latency.labels(layer=layer).observe(duration)
    
    def inc_agent_task(self, agent_type: str, status: str, orchestrator: str):
        self.agent_tasks_total.labels(agent_type=agent_type, status=status, orchestrator=orchestrator).inc()
    
    def observe_agent_task_duration(self, agent_type: str, orchestrator: str, duration: float):
        self.agent_task_duration.labels(agent_type=agent_type, orchestrator=orchestrator).observe(duration)
    
    def inc_agent_step(self, agent_type: str, strategy: str):
        self.agent_steps_total.labels(agent_type=agent_type, strategy=strategy).inc()
    
    def inc_agent_tool_call(self, tool_name: str, status: str = "success"):
        self.agent_tools_called.labels(tool_name=tool_name, status=status).inc()
    
    def set_websocket_connections(self, count: int):
        self.websocket_connections.set(count)
    
    def inc_websocket_message(self, event_type: str):
        self.websocket_messages_total.labels(event_type=event_type).inc()
    
    def set_system_cpu(self, percent: float):
        self.system_cpu_percent.set(percent)
    
    def set_system_memory(self, percent: float):
        self.system_memory_percent.set(percent)
    
    def set_system_disk(self, percent: float):
        self.system_disk_percent.set(percent)
    
    def set_system_uptime(self, seconds: float):
        self.system_uptime_seconds.set(seconds)
    
    def set_subsystem_health(self, subsystem: str, healthy: bool):
        self.subsystem_health.labels(subsystem=subsystem).set(1 if healthy else 0)
    
    def inc_security_violation(self, violation_type: str, action: str):
        self.security_violations_total.labels(violation_type=violation_type, action=action).inc()
    
    def inc_sandbox_execution(self, status: str = "success"):
        self.sandbox_executions_total.labels(status=status).inc()
    
    def get_latest_metrics(self) -> bytes:
        return generate_latest(self.registry)
    
    def get_content_type(self) -> str:
        return CONTENT_TYPE_LATEST


metrics = NexusMetrics()


def get_metrics() -> NexusMetrics:
    return metrics


async def metrics_endpoint():
    """FastAPI endpoint handler for Prometheus metrics."""
    from starlette.responses import Response
    
    return Response(
        content=metrics.get_latest_metrics(),
        media_type=metrics.get_content_type(),
    )
