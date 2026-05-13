"""
NEXUS MCP Tools - Modular tool implementations.

This package contains all MCP tool implementations organized by domain:
- memory_tools: Memory search, store, delete, namespaces, stats
- knowledge_tools: Knowledge graph query, add entity/relation, search, paths
- llm_tools: LLM completion, model listing, provider status, streaming
- agent_tools: Agent spawning, listing, status, delegation, A2A
- code_tools: Code execution, sandboxed commands, package installation
- file_tools: File read, write, list, delete, move, copy, search
- web_tools: Web search, scrape, screenshot
- reasoning_tools: ReAct, ToT, LATS reasoning
- orchestration_tools: Pipeline, parallel, supervisor, swarm
- system_tools: Status, config, health check
- bonus_tools: Audit, rate limiting, deep research, RAG
"""

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
    avatar_tools,
)

__all__ = [
    "memory_tools",
    "knowledge_tools",
    "llm_tools",
    "agent_tools",
    "code_tools",
    "file_tools",
    "web_tools",
    "reasoning_tools",
    "orchestration_tools",
    "system_tools",
    "bonus_tools",
    "avatar_tools",
]


def get_all_tools() -> list[tuple[str, callable]]:
    """Get all MCP tools as a list of (name, function) tuples."""
    tools = []

    # Memory tools
    tools.extend([
        ("search_memory", memory_tools.search_memory),
        ("store_memory", memory_tools.store_memory),
        ("delete_memory", memory_tools.delete_memory),
        ("list_namespaces", memory_tools.list_namespaces),
        ("memory_stats", memory_tools.memory_stats),
    ])

    # Knowledge tools
    tools.extend([
        ("knowledge_query", knowledge_tools.knowledge_query),
        ("knowledge_add_entity", knowledge_tools.knowledge_add_entity),
        ("knowledge_add_relation", knowledge_tools.knowledge_add_relation),
        ("knowledge_search", knowledge_tools.knowledge_search),
        ("knowledge_paths", knowledge_tools.knowledge_paths),
    ])

    # LLM tools
    tools.extend([
        ("llm_complete", llm_tools.llm_complete),
        ("llm_list_models", llm_tools.llm_list_models),
        ("llm_provider_status", llm_tools.llm_provider_status),
        ("llm_stream", llm_tools.llm_stream),
    ])

    # Agent tools
    tools.extend([
        ("spawn_agent", agent_tools.spawn_agent),
        ("list_agents", agent_tools.list_agents),
        ("agent_status", agent_tools.agent_status),
        ("agent_delegate", agent_tools.agent_delegate),
        ("a2a_discover", agent_tools.a2a_discover),
    ])

    # Code tools
    tools.extend([
        ("execute_code", code_tools.execute_code),
        ("execute_sandboxed", code_tools.execute_sandboxed),
        ("install_package", code_tools.install_package),
    ])

    # File tools
    tools.extend([
        ("read_file", file_tools.read_file),
        ("write_file", file_tools.write_file),
        ("list_files", file_tools.list_files),
        ("delete_file", file_tools.delete_file),
        ("move_file", file_tools.move_file),
        ("copy_file", file_tools.copy_file),
        ("search_files", file_tools.search_files),
    ])

    # Web tools
    tools.extend([
        ("web_search", web_tools.web_search),
        ("web_scrape", web_tools.web_scrape),
        ("web_screenshot", web_tools.web_screenshot),
    ])

    # Reasoning tools
    tools.extend([
        ("reason_react", reasoning_tools.reason_react),
        ("reason_tot", reasoning_tools.reason_tot),
        ("reason_lats", reasoning_tools.reason_lats),
    ])

    # Orchestration tools
    tools.extend([
        ("run_pipeline", orchestration_tools.run_pipeline),
        ("run_parallel", orchestration_tools.run_parallel),
        ("run_supervisor", orchestration_tools.run_supervisor),
        ("run_swarm", orchestration_tools.run_swarm),
    ])

    # System tools
    tools.extend([
        ("get_status", system_tools.get_status),
        ("get_config", system_tools.get_config),
        ("health_check", system_tools.health_check),
    ])

    # Bonus tools
    tools.extend([
        ("audit_query", bonus_tools.audit_query),
        ("rate_limit_status", bonus_tools.rate_limit_status),
        ("deep_research", bonus_tools.deep_research),
        ("rag_query", bonus_tools.rag_query),
    ])

    # Avatar tools
    tools.extend([
        ("avatar_start", avatar_tools.avatar_start),
        ("avatar_speak", avatar_tools.avatar_speak),
        ("avatar_set_vrm", avatar_tools.avatar_set_vrm),
        ("avatar_set_expression", avatar_tools.avatar_set_expression),
        ("avatar_list_voices", avatar_tools.avatar_list_voices),
        ("avatar_set_speaker", avatar_tools.avatar_set_speaker),
        ("avatar_start_conversation", avatar_tools.avatar_start_conversation),
        ("avatar_expression_from_text", avatar_tools.avatar_expression_from_text),
    ])

    return tools