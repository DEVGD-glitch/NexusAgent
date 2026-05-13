"""
NEXUS LangGraph Core Engine — Plan-Execute-Reflect orchestrator.

Implements the central orchestration loop using LangGraph's StateGraph:
  1. PLANNER: Decomposes the task into sub-tasks using memory context
  2. EXECUTOR: Dispatches sub-tasks to specialized agents
  3. REFLECTOR: Evaluates results and decides next action

Supports:
  - Automatic checkpointing via MemorySaver
  - Human-in-the-loop via interrupt_before
  - Conditional branching based on task state
  - Max iteration guard to prevent infinite loops
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Literal, Optional, TypedDict

from nexus.core.config import get_settings
from nexus.core.exceptions import MaxIterationsError, OrchestratorError

logger = logging.getLogger(__name__)


# ── State Definition ──────────────────────────────────────────────

class NexusState(TypedDict, total=False):
    """State passed between nodes in the NEXUS orchestration graph."""
    task: str
    sub_tasks: list[str]
    current_sub_task: str
    plan: str
    result: str
    reflection: str
    messages: list[dict[str, str]]
    next_action: Literal["plan", "execute", "reflect", "done", "replan"]
    iteration: int
    metadata: dict[str, Any]


# ── Node Functions ────────────────────────────────────────────────

async def planner_node(state: NexusState) -> dict[str, Any]:
    """
    Planner node: Decompose the task into a plan with sub-tasks.

    Uses the LLM to analyze the task and create a structured plan.
    Loads relevant context from memory.
    """
    task = state.get("task", "")
    iteration = state.get("iteration", 0)

    logger.info("PLANNER: Planning for task (iteration %d): %s", iteration, task[:100])

    # Build planning prompt
    messages = state.get("messages", [])
    planning_prompt = {
        "role": "system",
        "content": (
            "You are NEXUS, a universal AI agent. Your job is to PLAN how to complete the given task.\n"
            "Break the task into concrete, actionable sub-tasks.\n"
            "Consider what tools and information you need.\n"
            "Output your plan as a numbered list of sub-tasks.\n"
            "If the task is simple enough to do in one step, say 'EXECUTE_DIRECTLY'."
        ),
    }
    planning_messages = [planning_prompt] + messages + [
        {"role": "user", "content": f"Task to plan: {task}"}
    ]

    try:
        from nexus.llm.router import LLMRouter, TaskComplexity
        router = LLMRouter()
        response = await router.complete(
            messages=planning_messages,
            task_complexity=TaskComplexity.MEDIUM,
            temperature=0.3,
        )
        plan_text = response.content
    except Exception as e:
        logger.warning("LLM planning failed, using simple plan: %s", e)
        plan_text = f"1. Execute task directly: {task}"

    # Parse plan into sub-tasks
    sub_tasks = []
    for line in plan_text.strip().split("\n"):
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith("-") or line.startswith("*")):
            # Remove numbering/bullets
            clean = line.lstrip("0123456789.-) ").strip()
            if clean:
                sub_tasks.append(clean)

    if not sub_tasks:
        sub_tasks = [task]

    # If only one simple step, go straight to execute
    next_action = "execute" if len(sub_tasks) <= 1 or "EXECUTE_DIRECTLY" in plan_text else "execute"

    return {
        "plan": plan_text,
        "sub_tasks": sub_tasks,
        "current_sub_task": sub_tasks[0] if sub_tasks else task,
        "next_action": next_action,
        "iteration": iteration + 1,
    }


AVAILABLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_code",
            "description": "Execute Python/JS/Bash code and return the output",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Code to execute"},
                    "language": {"type": "string", "enum": ["python", "javascript", "bash"], "default": "python"},
                    "timeout": {"type": "integer", "default": 15},
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "num_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "Search vector memory for stored information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "namespace": {"type": "string", "enum": ["knowledge", "episodes", "conversations", "skills"], "default": "knowledge"},
                    "top_k": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the filesystem",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute file path"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute file path"},
                    "content": {"type": "string", "description": "File content"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Call this when you have completed the task and have a final answer",
            "parameters": {
                "type": "object",
                "properties": {
                    "result": {"type": "string", "description": "Final result or answer"},
                },
                "required": ["result"],
            },
        },
    },
]


async def _execute_tool_call(tc: dict) -> str:
    """Execute a single tool call and return the result."""
    fn_name = tc.get("function", {}).get("name", "")
    try:
        args = json.loads(tc.get("function", {}).get("arguments", "{}"))
    except json.JSONDecodeError:
        args = {}

    import httpx

    backend = f"http://127.0.0.1:8081"

    try:
        if fn_name == "execute_code":
            r = await asyncio.to_thread(
                httpx.post,
                f"{backend}/code/execute",
                json={
                    "code": args.get("code", ""),
                    "language": args.get("language", "python"),
                    "timeout": args.get("timeout", 15),
                    "sandboxed": False,
                },
                timeout=30,
            )
            data = r.json()
            parts = []
            if data.get("stdout"):
                parts.append(f"STDOUT:\n{data['stdout']}")
            if data.get("stderr"):
                parts.append(f"STDERR:\n{data['stderr']}")
            parts.append(f"exit_code: {data.get('exit_code', -1)}")
            return "\n".join(parts)

        elif fn_name == "web_search":
            from nexus.knowledge.web_search import MultiSourceWebSearch
            searcher = MultiSourceWebSearch()
            results = await searcher.search(args.get("query", ""), num_results=args.get("num_results", 5))
            return str(results)[:3000]

        elif fn_name == "search_memory":
            r = await asyncio.to_thread(
                httpx.get,
                f"{backend}/tools/search_memory",
                params={
                    "query": args.get("query", ""),
                    "namespace": args.get("namespace", "knowledge"),
                    "top_k": args.get("top_k", 5),
                },
                timeout=15,
            )
            return r.text

        elif fn_name == "read_file":
            import aiofiles
            path = args.get("path", "")
            if not path:
                return "Error: no path provided"
            loop = asyncio.get_event_loop()
            with open(path, "r") as f:
                content = f.read()
            return f"Content of {path}:\n{content[:5000]}"

        elif fn_name == "write_file":
            path = args.get("path", "")
            content = args.get("content", "")
            with open(path, "w") as f:
                f.write(content)
            return f"File written: {path} ({len(content)} bytes)"

        elif fn_name == "finish":
            return f"TASK_COMPLETE: {args.get('result', '')}"

        else:
            return f"Unknown tool: {fn_name}"
    except Exception as e:
        logger.error("Tool execution failed: %s - %s", fn_name, e)
        return f"Tool {fn_name} failed: {str(e)}"


async def executor_node(state: NexusState) -> dict[str, Any]:
    """
    Executor node: Execute the current sub-task using available tools.

    Uses LLM function calling to decide which tools to invoke.
    Runs tool calls, feeds results back to the LLM, loops until done.
    """
    current_task = state.get("current_sub_task", state.get("task", ""))
    messages = list(state.get("messages", []))

    logger.info("EXECUTOR: Executing sub-task: %s", current_task[:100])

    execution_prompt = {
        "role": "system",
        "content": (
            "You are NEXUS, an AI agent with access to tools. "
            "Complete the given sub-task by calling the appropriate tools. "
            "When you have the final answer, call the finish() tool with your result. "
            "You can use multiple tools in sequence to accomplish complex tasks. "
            "After each tool call, you will receive the result and can decide what to do next."
        ),
    }
    execution_messages = [execution_prompt] + messages + [
        {"role": "user", "content": f"Execute this sub-task: {current_task}"}
    ]

    max_turns = 15
    all_results = []

    try:
        from nexus.llm.router import LLMRouter, TaskComplexity
        router = LLMRouter()

        for turn in range(max_turns):
            response = await router.complete(
                messages=execution_messages,
                task_complexity=TaskComplexity.MEDIUM,
                temperature=0.3,
                tools=AVAILABLE_TOOLS,
            )

            tool_calls = response.tool_calls

            if not tool_calls:
                # LLM responded with text (no tool calls) — use as result
                all_results.append(response.content or "")
                break

            # Execute each tool call
            for tc in tool_calls:
                fn_name = tc.get("function", {}).get("name", "")
                logger.info("EXECUTOR: Calling tool %s (turn %d)", fn_name, turn)

                tool_result = await _execute_tool_call(tc)

                # Check if tool completed the task
                if fn_name == "finish":
                    all_results.append(tool_result.replace("TASK_COMPLETE: ", ""))
                    break

                # Add assistant message with tool call
                execution_messages.append({"role": "assistant", "content": None, "tool_calls": [tc]})
                # Add tool result
                execution_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", f"call_{turn}"),
                    "content": tool_result[:2000],
                })
                all_results.append(f"[{fn_name}] {tool_result[:200]}")

            if fn_name == "finish":
                break

        result_text = "\n".join(all_results) if all_results else response.content

    except Exception as e:
        result_text = f"Execution error: {str(e)}"
        logger.error("Execution failed: %s", e)

    return {
        "result": result_text,
        "next_action": "reflect",
    }


async def reflector_node(state: NexusState) -> dict[str, Any]:
    """
    Reflector node: Evaluate the execution result and decide next action.

    Determines if the task is complete, needs replanning, or should
    continue with the next sub-task.
    """
    task = state.get("task", "")
    result = state.get("result", "")
    sub_tasks = state.get("sub_tasks", [])
    iteration = state.get("iteration", 0)

    logger.info("REFLECTOR: Reflecting on result (iteration %d)", iteration)

    settings = get_settings()
    max_iterations = settings.orchestrator_max_iterations

    if iteration >= max_iterations:
        return {
            "next_action": "done",
            "reflection": f"Max iterations ({max_iterations}) reached. Final result: {result[:500]}",
        }

    reflection_prompt = {
        "role": "system",
        "content": (
            "You are NEXUS reflecting on a task execution.\n"
            "Evaluate the result and decide what to do next.\n"
            "Options:\n"
            "- 'done': Task is fully completed\n"
            "- 'execute': Continue with next sub-task\n"
            "- 'replan': The approach needs to be changed\n\n"
            "Respond with a JSON object: {\"action\": \"done|execute|replan\", \"reason\": \"...\"}\n"
            "Only output valid JSON, nothing else."
        ),
    }

    reflection_messages = [reflection_prompt] + [
        {"role": "user", "content": (
            f"Original task: {task}\n"
            f"Sub-tasks: {sub_tasks}\n"
            f"Current result: {result[:1000]}\n"
            f"Iteration: {iteration}/{max_iterations}\n\n"
            "Evaluate and decide next action."
        )}
    ]

    try:
        from nexus.llm.router import LLMRouter, TaskComplexity
        router = LLMRouter()
        response = await router.complete(
            messages=reflection_messages,
            task_complexity=TaskComplexity.SIMPLE,
            temperature=0.2,
            max_tokens=256,
        )
        reflection_text = response.content.strip()

        # Try to parse JSON from response
        import json
        # Extract JSON from potential markdown code blocks
        json_str = reflection_text
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()

        decision = json.loads(json_str)
        action = decision.get("action", "execute")
        reason = decision.get("reason", "")

        if action not in ("done", "execute", "replan"):
            action = "execute"

    except Exception as e:
        logger.warning("Reflection parsing failed, defaulting to execute: %s", e)
        action = "execute"
        reason = "Could not parse LLM reflection response"

    # Check if all sub-tasks are done
    if action == "execute" and sub_tasks:
        current_idx = -1
        for i, st in enumerate(sub_tasks):
            if st == state.get("current_sub_task", ""):
                current_idx = i
                break
        if current_idx == -1:
            # No matching sub-task found, start from beginning
            current_idx = 0
        if current_idx + 1 >= len(sub_tasks):
            action = "done"
            reason = "All sub-tasks completed"

    return {
        "next_action": action,
        "reflection": reason,
        "current_sub_task": sub_tasks[current_idx + 1] if action == "execute" and current_idx + 1 < len(sub_tasks) else state.get("current_sub_task", ""),
    }


# ── Graph Builder ─────────────────────────────────────────────────

def build_nexus_graph():
    """
    Build the NEXUS Plan-Execute-Reflect StateGraph.

    Graph structure:
        START -> planner -> executor -> reflector -> (conditional)
                                                    ├─ done -> END
                                                    ├─ execute -> executor
                                                    └─ replan -> planner

    Returns:
        Compiled LangGraph with checkpointing.
    """
    try:
        from langgraph.graph import StateGraph, END, START
        from langgraph.checkpoint.memory import MemorySaver
    except ImportError:
        logger.warning("LangGraph not available, returning mock graph")
        return None

    graph = StateGraph(NexusState)

    # Add nodes
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("reflector", reflector_node)

    # Add edges
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "executor")

    # Conditional edges from reflector
    def route_after_reflect(state: NexusState) -> str:
        next_action = state.get("next_action", "execute")
        if next_action == "done":
            return END
        elif next_action == "replan":
            return "planner"
        else:
            return "executor"

    graph.add_conditional_edges("reflector", route_after_reflect, {
        END: END,
        "planner": "planner",
        "executor": "executor",
    })

    graph.add_edge("executor", "reflector")

    # Compile with checkpointing
    settings = get_settings()
    checkpointer = MemorySaver() if settings.orchestrator_checkpointer == "memory" else None

    interrupt_before = ["executor"] if settings.orchestrator_interrupt_before_executor else None

    compiled = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_before,
    )

    return compiled


async def run_nexus_task(
    task: str,
    messages: Optional[list[dict[str, str]]] = None,
    thread_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Run a complete NEXUS task through the Plan-Execute-Reflect loop.

    Args:
        task: The task description.
        messages: Optional prior conversation messages.
        thread_id: Optional thread ID for checkpointing.

    Returns:
        Dict with final result, iterations, and metadata.
    """
    # Use simple loop for now (LangGraph graph has state update issues)
    return await _run_simple_loop(task, messages or [])

    _thread_id = thread_id or f"thread_{uuid.uuid4().hex[:8]}"

    initial_state: NexusState = {
        "task": task,
        "sub_tasks": [],
        "current_sub_task": "",
        "plan": "",
        "result": "",
        "reflection": "",
        "messages": messages or [],
        "next_action": "plan",
        "iteration": 0,
        "metadata": {},
    }

    config = {"configurable": {"thread_id": _thread_id}}

    try:
        # Run the graph
        final_state = await graph.ainvoke(initial_state, config)

        return {
            "task": task,
            "result": final_state.get("result", ""),
            "plan": final_state.get("plan", ""),
            "reflection": final_state.get("reflection", ""),
            "iterations": final_state.get("iteration", 0),
            "thread_id": thread_id,
            "status": "completed",
        }
    except Exception as exc:
        logger.error("NEXUS task failed: %s", exc)
        return {
            "task": task,
            "result": f"Task failed: {str(exc)}",
            "iterations": 0,
            "thread_id": thread_id,
            "status": "failed",
            "error": str(exc),
        }


async def _run_simple_loop(
    task: str,
    messages: list[dict[str, str]],
    max_iterations: int = 10,
) -> dict[str, Any]:
    """Fallback execution without LangGraph — simple loop."""
    state: NexusState = {
        "task": task,
        "sub_tasks": [],
        "current_sub_task": task,
        "plan": "",
        "result": "",
        "reflection": "",
        "messages": messages,
        "next_action": "plan",
        "iteration": 0,
        "metadata": {},
    }

    for _ in range(max_iterations):
        if state["next_action"] == "plan" or state["next_action"] == "replan":
            update = await planner_node(state)
            state.update(update)
        elif state["next_action"] == "execute":
            update = await executor_node(state)
            state.update(update)
        elif state["next_action"] == "reflect":
            update = await reflector_node(state)
            state.update(update)
        elif state["next_action"] == "done":
            break

    return {
        "task": task,
        "result": state.get("result", ""),
        "plan": state.get("plan", ""),
        "reflection": state.get("reflection", ""),
        "iterations": state.get("iteration", 0),
        "status": "completed",
    }
