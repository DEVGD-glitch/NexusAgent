"""
NEXUS MCP Server — Central tool server using FastMCP protocol.

This module provides the FastMCP server layer while delegating actual
implementation to the modular mcp_tools package.

Tool Categories (40+ tools):
  1. Memory        : search_memory, store_memory, delete_memory, list_namespaces, memory_stats
  2. Knowledge     : knowledge_query, knowledge_add_entity, knowledge_add_relation, knowledge_search, knowledge_paths
  3. LLM           : llm_complete, llm_stream, llm_list_models, llm_provider_status
  4. Agent         : spawn_agent, list_agents, agent_status, agent_delegate, a2a_discover
  5. Code          : execute_code, execute_sandboxed, install_package
  6. File          : read_file, write_file, list_files, delete_file, move_file, copy_file, search_files
  7. Web           : web_search, web_scrape, web_screenshot
  8. Reasoning     : reason_react, reason_tot, reason_lats
  9. Orchestration : run_pipeline, run_parallel, run_supervisor, run_swarm
  10. System       : get_status, get_config, health_check, audit_query, rate_limit_status
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from nexus.core.exceptions import MCPToolError
from nexus.mcp_tools import (
    memory_tools,
    knowledge_tools,
    llm_tools,
    agent_tools,
    code_tools,
    file_tools,
    web_tools,
    reasoning_tools,
    orchestration_tools,
    system_tools,
    bonus_tools,
)

logger = logging.getLogger(__name__)

# ── MCP Server Instance ──────────────────────────────────────────────

nexus_mcp = FastMCP(
    "NEXUS-ToolServer",
    instructions="NEXUS Universal AI Agent - Central MCP Tool Server v1.0.0 - 40+ tools across 10 categories",
)


def _json(data: Any) -> str:
    """Serialize data to JSON string."""
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


# ═════════════════════════════════════════════════════════════════════
# MEMORY TOOLS (5)
# ═════════════════════════════════════════════════════════════════════

@nexus_mcp.tool()
async def search_memory(query: str, namespace: str = "knowledge", top_k: int = 5) -> str:
    """Search NEXUS vector memory for relevant documents."""
    try:
        return await memory_tools.search_memory(query, namespace, top_k)
    except Exception as exc:
        logger.error("search_memory failed: %s", exc)
        raise MCPToolError("search_memory", str(exc)) from exc


@nexus_mcp.tool()
async def store_memory(text: str, namespace: str = "knowledge", metadata: dict = None) -> str:
    """Store content in NEXUS memory."""
    try:
        return await memory_tools.store_memory(text, namespace, metadata)
    except Exception as exc:
        logger.error("store_memory failed: %s", exc)
        raise MCPToolError("store_memory", str(exc)) from exc


@nexus_mcp.tool()
async def delete_memory(doc_ids: list[str], namespace: str = "conversations") -> str:
    """Delete content from NEXUS memory."""
    try:
        return await memory_tools.delete_memory(doc_ids, namespace)
    except Exception as exc:
        logger.error("delete_memory failed: %s", exc)
        raise MCPToolError("delete_memory", str(exc)) from exc


@nexus_mcp.tool()
async def list_namespaces() -> str:
    """List all available memory namespaces."""
    try:
        return await memory_tools.list_namespaces()
    except Exception as exc:
        logger.error("list_namespaces failed: %s", exc)
        raise MCPToolError("list_namespaces", str(exc)) from exc


@nexus_mcp.tool()
async def memory_stats() -> str:
    """Get memory usage statistics."""
    try:
        return await memory_tools.memory_stats()
    except Exception as exc:
        logger.error("memory_stats failed: %s", exc)
        raise MCPToolError("memory_stats", str(exc)) from exc


# ═════════════════════════════════════════════════════════════════════
# KNOWLEDGE TOOLS (5)
# ═════════════════════════════════════════════════════════════════════

@nexus_mcp.tool()
async def knowledge_query(entity_name: str, depth: int = 1) -> str:
    """Query knowledge graph for entity and its connections."""
    try:
        return await knowledge_tools.knowledge_query(entity_name, depth)
    except Exception as exc:
        logger.error("knowledge_query failed: %s", exc)
        raise MCPToolError("knowledge_query", str(exc)) from exc


@nexus_mcp.tool()
async def knowledge_add_entity(entity_type: str, name: str, properties: dict = None) -> str:
    """Add an entity to the knowledge graph."""
    try:
        return await knowledge_tools.knowledge_add_entity(entity_type, name, properties)
    except Exception as exc:
        logger.error("knowledge_add_entity failed: %s", exc)
        raise MCPToolError("knowledge_add_entity", str(exc)) from exc


@nexus_mcp.tool()
async def knowledge_add_relation(source: str, target: str, relation_type: str, properties: dict = None) -> str:
    """Add a relation between two entities."""
    try:
        return await knowledge_tools.knowledge_add_relation(source, target, relation_type, properties)
    except Exception as exc:
        logger.error("knowledge_add_relation failed: %s", exc)
        raise MCPToolError("knowledge_add_relation", str(exc)) from exc


@nexus_mcp.tool()
async def knowledge_search(query: str, entity_type: str = None, limit: int = 20) -> str:
    """Search the knowledge graph."""
    try:
        return await knowledge_tools.knowledge_search(query, entity_type, limit)
    except Exception as exc:
        logger.error("knowledge_search failed: %s", exc)
        raise MCPToolError("knowledge_search", str(exc)) from exc


@nexus_mcp.tool()
async def knowledge_paths(source_name: str, target_name: str, max_length: int = 5) -> str:
    """Find paths between two entities."""
    try:
        return await knowledge_tools.knowledge_paths(source_name, target_name, max_length)
    except Exception as exc:
        logger.error("knowledge_paths failed: %s", exc)
        raise MCPToolError("knowledge_paths", str(exc)) from exc


# ═════════════════════════════════════════════════════════════════════
# LLM TOOLS (4)
# ═════════════════════════════════════════════════════════════════────

@nexus_mcp.tool()
async def llm_complete(prompt: str, model: str = None, temperature: float = 0.7, max_tokens: int = 4096) -> str:
    """Complete a prompt using the LLM router."""
    try:
        return await llm_tools.llm_complete(prompt, model, temperature, max_tokens)
    except Exception as exc:
        logger.error("llm_complete failed: %s", exc)
        raise MCPToolError("llm_complete", str(exc)) from exc


@nexus_mcp.tool()
async def llm_list_models() -> str:
    """List available LLM models."""
    try:
        return await llm_tools.llm_list_models()
    except Exception as exc:
        logger.error("llm_list_models failed: %s", exc)
        raise MCPToolError("llm_list_models", str(exc)) from exc


@nexus_mcp.tool()
async def llm_provider_status() -> str:
    """Get status of all LLM providers."""
    try:
        return await llm_tools.llm_provider_status()
    except Exception as exc:
        logger.error("llm_provider_status failed: %s", exc)
        raise MCPToolError("llm_provider_status", str(exc)) from exc


@nexus_mcp.tool()
async def llm_stream(prompt: str, model: str = None, temperature: float = 0.7) -> str:
    """Stream a completion."""
    try:
        return await llm_tools.llm_stream(prompt, model, temperature)
    except Exception as exc:
        logger.error("llm_stream failed: %s", exc)
        raise MCPToolError("llm_stream", str(exc)) from exc


# ═════════════════════════════════════════════════════════════════════
# AGENT TOOLS (5)
# ═════════════════════════════════════════════════════════════════────

@nexus_mcp.tool()
async def spawn_agent(agent_type: str, task: str, config: dict = None) -> str:
    """Spawn an agent to execute a task."""
    try:
        return await agent_tools.spawn_agent(agent_type, task, config)
    except Exception as exc:
        logger.error("spawn_agent failed: %s", exc)
        raise MCPToolError("spawn_agent", str(exc)) from exc


@nexus_mcp.tool()
async def list_agents() -> str:
    """List all available agent types."""
    try:
        return await agent_tools.list_agents()
    except Exception as exc:
        logger.error("list_agents failed: %s", exc)
        raise MCPToolError("list_agents", str(exc)) from exc


@nexus_mcp.tool()
async def agent_status(instance_id: str) -> str:
    """Get status of a running agent."""
    try:
        return await agent_tools.agent_status(instance_id)
    except Exception as exc:
        logger.error("agent_status failed: %s", exc)
        raise MCPToolError("agent_status", str(exc)) from exc


@nexus_mcp.tool()
async def agent_delegate(source_agent: str, target_agent: str, task: str, context: dict = None) -> str:
    """Delegate a task from one agent to another."""
    try:
        return await agent_tools.agent_delegate(source_agent, target_agent, task, context)
    except Exception as exc:
        logger.error("agent_delegate failed: %s", exc)
        raise MCPToolError("agent_delegate", str(exc)) from exc


@nexus_mcp.tool()
async def a2a_discover(agent_url: str) -> str:
    """Discover an A2A agent's capabilities."""
    try:
        return await agent_tools.a2a_discover(agent_url)
    except Exception as exc:
        logger.error("a2a_discover failed: %s", exc)
        raise MCPToolError("a2a_discover", str(exc)) from exc


# ═════════════════════════════════════════════════════════════════════
# CODE TOOLS (3)
# ═════════════════════════════════════════════════════════════════════

@nexus_mcp.tool()
async def execute_code(code: str, language: str = "python", timeout: int = 30) -> str:
    """Execute code in a sandboxed environment."""
    try:
        return await code_tools.execute_code(code, language, timeout)
    except Exception as exc:
        logger.error("execute_code failed: %s", exc)
        raise MCPToolError("execute_code", str(exc)) from exc


@nexus_mcp.tool()
async def execute_sandboxed(command: str, timeout: int = 30, allowed_dirs: list[str] = None) -> str:
    """Execute a shell command in a sandboxed environment."""
    try:
        return await code_tools.execute_sandboxed(command, timeout, allowed_dirs)
    except Exception as exc:
        logger.error("execute_sandboxed failed: %s", exc)
        raise MCPToolError("execute_sandboxed", str(exc)) from exc


@nexus_mcp.tool()
async def install_package(package: str, version: str = None) -> str:
    """Install a Python package."""
    try:
        return await code_tools.install_package(package, version)
    except Exception as exc:
        logger.error("install_package failed: %s", exc)
        raise MCPToolError("install_package", str(exc)) from exc


# ═════════════════════════════════════════════════════════════════════
# FILE TOOLS (7)
# ═════════════════════════════════════════════════════════════════────

@nexus_mcp.tool()
async def read_file(path: str, encoding: str = "utf-8") -> str:
    """Read a file's contents."""
    try:
        return await file_tools.read_file(path, encoding)
    except Exception as exc:
        logger.error("read_file failed: %s", exc)
        raise MCPToolError("read_file", str(exc)) from exc


@nexus_mcp.tool()
async def write_file(path: str, content: str, encoding: str = "utf-8") -> str:
    """Write content to a file."""
    try:
        return await file_tools.write_file(path, content, encoding)
    except Exception as exc:
        logger.error("write_file failed: %s", exc)
        raise MCPToolError("write_file", str(exc)) from exc


@nexus_mcp.tool()
async def list_files(directory: str = ".", pattern: str = "*") -> str:
    """List files in a directory matching a pattern."""
    try:
        return await file_tools.list_files(directory, pattern)
    except Exception as exc:
        logger.error("list_files failed: %s", exc)
        raise MCPToolError("list_files", str(exc)) from exc


@nexus_mcp.tool()
async def delete_file(path: str) -> str:
    """Delete a file."""
    try:
        return await file_tools.delete_file(path)
    except Exception as exc:
        logger.error("delete_file failed: %s", exc)
        raise MCPToolError("delete_file", str(exc)) from exc


@nexus_mcp.tool()
async def move_file(source: str, destination: str) -> str:
    """Move a file to a new location."""
    try:
        return await file_tools.move_file(source, destination)
    except Exception as exc:
        logger.error("move_file failed: %s", exc)
        raise MCPToolError("move_file", str(exc)) from exc


@nexus_mcp.tool()
async def copy_file(source: str, destination: str) -> str:
    """Copy a file to a new location."""
    try:
        return await file_tools.copy_file(source, destination)
    except Exception as exc:
        logger.error("copy_file failed: %s", exc)
        raise MCPToolError("copy_file", str(exc)) from exc


@nexus_mcp.tool()
async def search_files(query: str, path: str = ".", file_pattern: str = "*") -> str:
    """Search for text within files."""
    try:
        return await file_tools.search_files(query, path, file_pattern)
    except Exception as exc:
        logger.error("search_files failed: %s", exc)
        raise MCPToolError("search_files", str(exc)) from exc


# ═════════════════════════════════════════════════════════════════════
# WEB TOOLS (3)
# ═════════════════════════════════════════════════════════════════════

@nexus_mcp.tool()
async def web_search(query: str, num_results: int = 5) -> str:
    """Search the web for information."""
    try:
        return await web_tools.web_search(query, num_results)
    except Exception as exc:
        logger.error("web_search failed: %s", exc)
        raise MCPToolError("web_search", str(exc)) from exc


@nexus_mcp.tool()
async def web_scrape(url: str, max_length: int = 10000) -> str:
    """Scrape a webpage's content."""
    try:
        return await web_tools.web_scrape(url, max_length)
    except Exception as exc:
        logger.error("web_scrape failed: %s", exc)
        raise MCPToolError("web_scrape", str(exc)) from exc


@nexus_mcp.tool()
async def web_screenshot(url: str) -> str:
    """Take a screenshot of a webpage."""
    try:
        return await web_tools.web_screenshot(url)
    except Exception as exc:
        logger.error("web_screenshot failed: %s", exc)
        raise MCPToolError("web_screenshot", str(exc)) from exc


# ═════════════════════════════════════════════════════════════════════
# REASONING TOOLS (3)
# ═════════════════════════════════════════════════════════════════════

@nexus_mcp.tool()
async def reason_react(task: str, max_iterations: int = 10) -> str:
    """Execute ReAct (Reasoning + Acting) reasoning."""
    try:
        return await reasoning_tools.reason_react(task, max_iterations)
    except Exception as exc:
        logger.error("reason_react failed: %s", exc)
        raise MCPToolError("reason_react", str(exc)) from exc


@nexus_mcp.tool()
async def reason_tot(task: str, max_depth: int = 3, branch_factor: int = 3) -> str:
    """Execute Tree of Thoughts reasoning."""
    try:
        return await reasoning_tools.reason_tot(task, max_depth, branch_factor)
    except Exception as exc:
        logger.error("reason_tot failed: %s", exc)
        raise MCPToolError("reason_tot", str(exc)) from exc


@nexus_mcp.tool()
async def reason_lats(task: str, max_simulations: int = 10, max_depth: int = 4) -> str:
    """Execute LATS (Language Agent Tree Search) reasoning."""
    try:
        return await reasoning_tools.reason_lats(task, max_simulations, max_depth)
    except Exception as exc:
        logger.error("reason_lats failed: %s", exc)
        raise MCPToolError("reason_lats", str(exc)) from exc


# ═════════════════════════════════════════════════════════════════════
# ORCHESTRATION TOOLS (4)
# ═════════════════════════════════════════════════════════════════════

@nexus_mcp.tool()
async def run_pipeline(tasks: list[str], sequential: bool = True) -> str:
    """Run a pipeline of tasks."""
    try:
        return await orchestration_tools.run_pipeline(tasks, sequential)
    except Exception as exc:
        logger.error("run_pipeline failed: %s", exc)
        raise MCPToolError("run_pipeline", str(exc)) from exc


@nexus_mcp.tool()
async def run_parallel(tasks: list[str]) -> str:
    """Run tasks in parallel."""
    try:
        return await orchestration_tools.run_parallel(tasks)
    except Exception as exc:
        logger.error("run_parallel failed: %s", exc)
        raise MCPToolError("run_parallel", str(exc)) from exc


@nexus_mcp.tool()
async def run_supervisor(task: str, agents: list[str]) -> str:
    """Run a supervisor that delegates to sub-agents."""
    try:
        return await orchestration_tools.run_supervisor(task, agents)
    except Exception as exc:
        logger.error("run_supervisor failed: %s", exc)
        raise MCPToolError("run_supervisor", str(exc)) from exc


@nexus_mcp.tool()
async def run_swarm(tasks: list[str], agent_count: int = 3) -> str:
    """Run a swarm of agents on multiple tasks."""
    try:
        return await orchestration_tools.run_swarm(tasks, agent_count)
    except Exception as exc:
        logger.error("run_swarm failed: %s", exc)
        raise MCPToolError("run_swarm", str(exc)) from exc


# ═════════════════════════════════════════════════════════════════════
# SYSTEM TOOLS (5)
# ═════════════════════════════════════════════════════════════════════

@nexus_mcp.tool()
async def get_status() -> str:
    """Get NEXUS system status."""
    try:
        return await system_tools.get_status()
    except Exception as exc:
        logger.error("get_status failed: %s", exc)
        raise MCPToolError("get_status", str(exc)) from exc


@nexus_mcp.tool()
async def get_config() -> str:
    """Get NEXUS configuration."""
    try:
        return await system_tools.get_config()
    except Exception as exc:
        logger.error("get_config failed: %s", exc)
        raise MCPToolError("get_config", str(exc)) from exc


@nexus_mcp.tool()
async def health_check() -> str:
    """Perform health check on NEXUS components."""
    try:
        return await system_tools.health_check()
    except Exception as exc:
        logger.error("health_check failed: %s", exc)
        raise MCPToolError("health_check", str(exc)) from exc


@nexus_mcp.tool()
async def audit_query(query: str, start_date: str = None, end_date: str = None, limit: int = 100) -> str:
    """Query security audit logs."""
    try:
        return await bonus_tools.audit_query(query, start_date, end_date, limit)
    except Exception as exc:
        logger.error("audit_query failed: %s", exc)
        raise MCPToolError("audit_query", str(exc)) from exc


@nexus_mcp.tool()
async def rate_limit_status(identifier: str = "default") -> str:
    """Get rate limit status for an identifier."""
    try:
        return await bonus_tools.rate_limit_status(identifier)
    except Exception as exc:
        logger.error("rate_limit_status failed: %s", exc)
        raise MCPToolError("rate_limit_status", str(exc)) from exc


# ═════════════════════════════════════════════════════════════════════
# RESEARCH TOOLS (2)
# ═════════════════════════════════════════════════════════════════════

@nexus_mcp.tool()
async def deep_research(topic: str, depth: str = "medium") -> str:
    """Perform deep research on a topic."""
    try:
        return await bonus_tools.deep_research(topic, depth)
    except Exception as exc:
        logger.error("deep_research failed: %s", exc)
        raise MCPToolError("deep_research", str(exc)) from exc


@nexus_mcp.tool()
async def rag_query(query: str, namespace: str = "knowledge", top_k: int = 5) -> str:
    """Query the RAG system."""
    try:
        return await bonus_tools.rag_query(query, namespace, top_k)
    except Exception as exc:
        logger.error("rag_query failed: %s", exc)
        raise MCPToolError("rag_query", str(exc)) from exc


# ═════════════════════════════════════════════════════════════════════
# RESOURCES
# ═════════════════════════════════════════════════════════════════════

@nexus_mcp.resource("nexus://config")
def get_config_resource() -> str:
    """Return NEXUS configuration as a resource."""
    try:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                return json.dumps({"error": "Cannot call async get_config from sync context"})
        except RuntimeError:
            pass
        return asyncio.get_event_loop().run_until_complete(system_tools.get_config())
    except Exception as exc:
        logger.error("get_config_resource failed: %s", exc)
        return json.dumps({"error": str(exc)})


@nexus_mcp.resource("nexus://status")
def get_status_resource() -> str:
    """Return NEXUS status as a resource."""
    try:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                return json.dumps({"error": "Cannot call async get_status from sync context"})
        except RuntimeError:
            pass
        return asyncio.get_event_loop().run_until_complete(system_tools.get_status())
    except Exception as exc:
        logger.error("get_status_resource failed: %s", exc)
        return json.dumps({"error": str(exc)})


@nexus_mcp.resource("nexus://tools")
def get_tools_resource() -> str:
    """Return list of all available MCP tools."""
    tools = [
        "search_memory", "store_memory", "delete_memory", "list_namespaces", "memory_stats",
        "knowledge_query", "knowledge_add_entity", "knowledge_add_relation", "knowledge_search", "knowledge_paths",
        "llm_complete", "llm_stream", "llm_list_models", "llm_provider_status",
        "spawn_agent", "list_agents", "agent_status", "agent_delegate", "a2a_discover",
        "execute_code", "execute_sandboxed", "install_package",
        "read_file", "write_file", "list_files", "delete_file", "move_file", "copy_file", "search_files",
        "web_search", "web_scrape", "web_screenshot",
        "reason_react", "reason_tot", "reason_lats",
        "run_pipeline", "run_parallel", "run_supervisor", "run_swarm",
        "get_status", "get_config", "health_check", "audit_query", "rate_limit_status",
        "deep_research", "rag_query",
    ]
    return json.dumps({"total": len(tools), "tools": tools}, indent=2)


# ═════════════════════════════════════════════════════════════════════
# PROMPT DEFINITIONS
# ═════════════════════════════════════════════════════════════════════

@nexus_mcp.prompt()
def research_task(topic: str, depth: str = "medium") -> str:
    """Template for research tasks."""
    return (
        f"You are NEXUS, a universal AI research agent. Conduct research on: {topic}\n\n"
        f"Depth level: {depth}\n\n"
        "Steps:\n"
        "1. Use search_memory to check existing knowledge\n"
        "2. Use web_search to find current information\n"
        "3. Use deep_research for comprehensive multi-source analysis\n"
        "4. Use knowledge_add_entity and knowledge_add_relation to store findings\n"
        "5. Store key findings in memory using store_memory\n"
    )


@nexus_mcp.prompt()
def code_task(description: str, language: str = "python") -> str:
    """Template for coding tasks."""
    return (
        f"You are NEXUS, a universal AI coding agent. Complete this task: {description}\n\n"
        f"Language: {language}\n\n"
        "Steps:\n"
        "1. Use read_file to understand existing code\n"
        "2. Use search_files to find relevant files\n"
        "3. Use execute_code to test your implementation\n"
        "4. Use write_file to save the final code\n"
        "5. Use execute_sandboxed for safety-critical code\n"
    )


@nexus_mcp.prompt()
def analysis_task(data_description: str, analysis_type: str = "general") -> str:
    """Template for data analysis tasks."""
    return (
        f"You are NEXUS, a universal AI analysis agent. Analyze: {data_description}\n\n"
        f"Analysis type: {analysis_type}\n\n"
        "Steps:\n"
        "1. Use read_file to load data\n"
        "2. Use execute_code to run analysis scripts\n"
        "3. Use knowledge_query to check related concepts\n"
        "4. Use store_memory to save insights\n"
        "5. Present findings with clear structure\n"
    )


# ═════════════════════════════════════════════════════════════════════
# SERVER RUNNER
# ═════════════════════════════════════════════════════════════════────

def run_mcp_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the NEXUS MCP server."""
    logger.info("Starting NEXUS MCP Server on %s:%d with 43 tools", host, port)
    nexus_mcp.run(transport="streamable-http")


if __name__ == "__main__":
    run_mcp_server()