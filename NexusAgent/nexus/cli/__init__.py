"""
NEXUS CLI — Command-line interface using Typer.

Commands:
  - nexus run      : Run a task through the orchestrator
  - nexus chat     : Interactive chat mode
  - nexus status   : Show agent status
  - nexus memory   : Memory management commands
  - nexus config   : Show current configuration
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from nexus.core.config import get_settings

console = Console()
app = typer.Typer(
    name="nexus",
    help="NEXUS — Universal Sovereign AI Agent of Production Class",
    add_completion=False,
)

agents_app = typer.Typer(help="Agent management commands")
app.add_typer(agents_app, name="agents")

skills_app = typer.Typer(help="Skill lifecycle management")
app.add_typer(skills_app, name="skills")

eval_app = typer.Typer(help="Evaluation and benchmarking")
app.add_typer(eval_app, name="eval")

context7_app = typer.Typer(help="Context7 documentation queries")
app.add_typer(context7_app, name="context7")

memory_app = typer.Typer(help="Memory management commands")
app.add_typer(memory_app, name="memory")


# ── Agents Commands ────────────────────────────────────────────────

@agents_app.command("list")
def agents_list():
    """List all active NEXUS agents."""
    from nexus.core.registry import AgentRegistry
    registry = AgentRegistry()
    instances = registry.list_instances()

    if not instances:
        console.print("[yellow]No active agents[/]")
        return

    table = Table(title="Active Agents")
    table.add_column("ID", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Status", style="blue")
    table.add_column("Created", style="dim")

    for inst in instances:
        table.add_row(
            str(inst.agent_id),
            str(inst.agent_type),
            str(inst.status.value if hasattr(inst.status, 'value') else inst.status),
            str(inst.created_at.isoformat() if hasattr(inst.created_at, 'isoformat') else inst.created_at),
        )
    console.print(table)


# ── Skills Commands ────────────────────────────────────────────────

@skills_app.command("deploy")
def skills_deploy(
    skill_path: str = typer.Argument(..., help="Path to skill directory or JSON definition"),
    force: bool = typer.Option(False, "--force", "-f", help="Force redeploy even if already deployed"),
):
    """Deploy a skill to NEXUS."""
    async def _deploy():
        from nexus.orchestrator.skill_lifecycle import SkillLifecycleManager
        manager = SkillLifecycleManager()
        return await manager.deploy_skill(skill_path, force=force)

    try:
        console.print(f"[bold blue]Deploying skill from:[/] {skill_path}")
        result = asyncio.run(_deploy())
        if result.get("success"):
            console.print(Panel(
                f"[bold green]Skill deployed successfully![/]\n"
                f"ID: {result.get('skill_id', 'N/A')}",
                title="Deploy",
            ))
        else:
            console.print(Panel(
                f"[bold red]Deploy failed:[/]\n{result.get('error', 'Unknown error')}",
                title="Error",
            ))
    except Exception as e:
        console.print(f"[red]Error deploying skill: {e}[/]")


@app.command()
def run(
    task: str = typer.Argument(..., help="Task description to execute"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="LLM provider"),
    complexity: Optional[str] = typer.Option(None, "--complexity", "-c", help="Task complexity"),
    thread_id: Optional[str] = typer.Option(None, "--thread", "-t", help="Thread ID"),
):
    """Run a task through the NEXUS Plan-Execute-Reflect orchestrator."""
    console.print(Panel(f"[bold blue]NEXUS Task[/]\n{task}", title="Running"))

    result = asyncio.run(_run_task(task, provider, complexity, thread_id))

    if result.get("status") == "completed":
        console.print(Panel(
            f"[bold green]Result[/]\n{result.get('result', 'No result')}",
            title="Completed",
        ))
        if result.get("plan"):
            console.print(Panel(
                result["plan"],
                title="Plan",
                border_style="dim",
            ))
        if result.get("iterations"):
            console.print(f"[dim]Iterations: {result['iterations']} | "
                         f"Thread: {result.get('thread_id', 'N/A')}[/]")
    else:
        console.print(Panel(
            f"[bold red]Failed[/]\n{result.get('result', 'Unknown error')}",
            title="Error",
        ))


async def _run_task(
    task: str,
    provider: Optional[str],
    complexity: Optional[str],
    thread_id: Optional[str],
) -> dict:
    """Async task runner."""
    from nexus.orchestrator.langgraph_engine import run_nexus_task
    return await run_nexus_task(
        task=task,
        thread_id=thread_id,
    )


@app.command()
def chat():
    """Start an interactive chat session with NEXUS."""
    console.print(Panel(
        "[bold]NEXUS Interactive Chat[/]\n"
        "Type your message and press Enter. Type 'exit' to quit.",
        title="Welcome",
    ))

    conversation: list[dict[str, str]] = []

    while True:
        try:
            user_input = console.input("[bold green]You[/]: ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/]")
            break

        if user_input.strip().lower() in ("exit", "quit", "q"):
            console.print("[dim]Goodbye![/]")
            break

        if not user_input.strip():
            continue

        conversation.append({"role": "user", "content": user_input})

        try:
            from nexus.llm.router import LLMRouter, TaskComplexity
            router = LLMRouter()
            response = asyncio.run(router.complete(
                messages=conversation,
                task_complexity=TaskComplexity.SIMPLE,
            ))
            assistant_message = response.content
            conversation.append({"role": "assistant", "content": assistant_message})

            console.print(Panel(
                Markdown(assistant_message),
                title=f"[bold blue]NEXUS[/] ({response.provider.value}/{response.model})",
            ))

        except Exception as e:
            console.print(f"[bold red]Error:[/] {e}")


@app.command()
def status():
    """Show NEXUS agent status."""
    settings = get_settings()

    table = Table(title="NEXUS Agent Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Agent", "NEXUS")
    table.add_row("Version", "0.1.0")
    table.add_row("Environment", settings.nexus_env.value)
    table.add_row("Port", str(settings.nexus_port))
    table.add_row("Providers", ", ".join(settings.available_providers) or "none configured")
    table.add_row("Browser Service", "enabled" if settings.browser_service_enabled else "disabled")
    table.add_row("Sandbox", "enabled" if settings.sandbox_enabled else "disabled")
    table.add_row("Memory Max Tokens", str(settings.memory_max_working_tokens))
    table.add_row("ChromaDB Path", settings.chroma_persist_dir)

    console.print(table)


@app.command()
def config():
    """Show current NEXUS configuration (non-sensitive)."""
    settings = get_settings()

    table = Table(title="NEXUS Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    safe_settings = {
        "nexus_env": settings.nexus_env.value,
        "nexus_log_level": settings.nexus_log_level.value,
        "nexus_host": settings.nexus_host,
        "nexus_port": settings.nexus_port,
        "chroma_persist_dir": settings.chroma_persist_dir,
        "chroma_host": settings.chroma_host,
        "chroma_port": str(settings.chroma_port),
        "browser_service_url": settings.browser_service_url,
        "browser_service_enabled": str(settings.browser_service_enabled),
        "ollama_base_url": settings.ollama_base_url,
        "ollama_default_model": settings.ollama_default_model,
        "llm_default_provider": settings.llm_default_provider,
        "llm_default_model": settings.llm_default_model,
        "llm_fallback_chain": settings.llm_fallback_chain,
        "memory_max_working_tokens": str(settings.memory_max_working_tokens),
        "sandbox_enabled": str(settings.sandbox_enabled),
        "rate_limit_rpm": str(settings.rate_limit_rpm),
        "openai_configured": "yes" if settings.openai_api_key else "no",
        "anthropic_configured": "yes" if settings.anthropic_api_key else "no",
        "google_configured": "yes" if settings.google_api_key else "no",
        "zai_configured": "yes" if settings.zai_api_key else "no",
    }

    for key, value in safe_settings.items():
        table.add_row(key, str(value))

    console.print(table)


@skills_app.command("list")
def skills_list():
    """List all available skills in the registry."""
    from nexus.orchestrator.skill_lifecycle import SkillLifecycleManager
    manager = SkillLifecycleManager()
    skills = manager.list_skills()

    if not skills:
        console.print("[yellow]No skills registered[/]")
        return

    table = Table(title="Available Skills")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Version", style="blue")
    table.add_column("Status", style="yellow")

    for skill in skills:
        table.add_row(
            skill.get("id", "N/A"),
            skill.get("name", "N/A"),
            skill.get("version", "N/A"),
            skill.get("status", "N/A"),
        )
    console.print(table)


# ── Eval Commands ──────────────────────────────────────────────────

@eval_app.command("run")
def eval_run(
    skill_id: str = typer.Option(None, "--skill", "-s", help="Skill ID to evaluate"),
    agent_type: str = typer.Option(None, "--agent", "-a", help="Agent type to evaluate"),
    benchmarks: str = typer.Option(None, "--benchmarks", "-b", help="Comma-separated benchmark names"),
):
    """Run NEXUS evaluation benchmarks."""
    async def _run():
        from nexus.core.evaluation import Evaluator
        evaluator = Evaluator()
        if skill_id:
            return await evaluator.evaluate_skill(skill_id)
        elif agent_type:
            return await evaluator.evaluate_agent(agent_type)
        else:
            return await evaluator.run_benchmark_suite()

    try:
        console.print("[bold blue]Running evaluation...[/]")
        result = asyncio.run(_run())
        score = result.get("score", 0.0)
        score_pct = f"{score * 100:.1f}%"
        color = "green" if score >= 0.8 else "yellow" if score >= 0.5 else "red"

        console.print(Panel(
            f"[bold]Score:[/bold] {score_pct}\n"
            f"Passed: {result.get('test_cases_passed', 0)}/{result.get('test_cases_total', 0)}\n"
            f"Latency: {result.get('latency_ms', 0):.1f}ms",
            title=f"Evaluation Results ({result.get('skill_id') or result.get('agent_type', 'general')})",
            border_style=color,
        ))
    except Exception as e:
        console.print(f"[red]Error running evaluation: {e}[/]")


@eval_app.command("suite")
def eval_suite():
    """Run the full benchmark suite."""
    async def _run():
        from nexus.core.evaluation import Evaluator
        evaluator = Evaluator()
        return await evaluator.run_benchmark_suite()

    try:
        console.print("[bold blue]Running full benchmark suite...[/]")
        results = asyncio.run(_run())

        table = Table(title="Benchmark Results")
        table.add_column("Skill/Agent", style="cyan")
        table.add_column("Score", style="green")
        table.add_column("Passed", style="yellow")
        table.add_column("Latency", style="dim")

        for r in results:
            score_pct = f"{r.get('score', 0) * 100:.1f}%"
            table.add_row(
                r.get("skill_id") or r.get("agent_type", "N/A"),
                score_pct,
                f"{r.get('test_cases_passed', 0)}/{r.get('test_cases_total', 0)}",
                f"{r.get('latency_ms', 0):.1f}ms",
            )
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error running suite: {e}[/]")


# ── Context7 Commands ──────────────────────────────────────────────

@context7_app.command("query")
def context7_query(
    library: str = typer.Argument(..., help="Library name (e.g. fastapi, react, pydantic)"),
    question: str = typer.Option(None, "--question", "-q", help="Specific question about the library"),
):
    """Query Context7 for library documentation."""
    async def _query():
        from nexus.mcp_tools.context7 import Context7MCPServer
        server = Context7MCPServer()
        if question:
            docs = await server.query_docs(library, question)
        else:
            libs = await server.resolve_library(library)
            docs = libs
        return docs

    try:
        console.print(f"[bold blue]Querying Context7 for:[/] {library}")
        result = asyncio.run(_query())
        if isinstance(result, list) and result:
            console.print(Panel(
                "\n".join(str(item) for item in result[:5]),
                title=f"Context7 Results ({library})",
                expand=False,
            ))
        elif isinstance(result, dict):
            console.print(Panel(
                str(result),
                title=f"Context7 Result ({library})",
                expand=False,
            ))
        else:
            console.print(f"[yellow]No results for '{library}'[/]")
    except Exception as e:
        console.print(f"[red]Error querying Context7: {e}[/]")


@context7_app.command("libraries")
def context7_libraries():
    """List known libraries supported by Context7."""
    from nexus.mcp_tools.context7 import KNOWN_LIBRARIES

    table = Table(title="Known Context7 Libraries")
    table.add_column("Name", style="cyan")
    table.add_column("Context7 ID", style="green")

    for lib_name in sorted(KNOWN_LIBRARIES.keys()):
        table.add_row(lib_name, KNOWN_LIBRARIES[lib_name])
    console.print(table)


# ── Memory Commands ───────────────────────────────────────────────

@memory_app.command("stats")
def memory_stats():
    """Show memory statistics."""
    settings = get_settings()

    table = Table(title="NEXUS Memory Statistics")
    table.add_column("Namespace", style="cyan")
    table.add_column("Count", style="green")

    async def _get_stats():
        from nexus.memory.chroma_service import NexusMemoryService
        service = NexusMemoryService(persist_dir=settings.chroma_persist_dir)
        stats = {}
        for ns in ["conversations", "episodes", "knowledge", "skills", "identity", "code"]:
            try:
                count = await service.count(namespace=ns)
                stats[ns] = count
            except Exception:
                stats[ns] = "error"
        return stats

    try:
        stats = asyncio.run(_get_stats())
        for ns, count in stats.items():
            table.add_row(ns, str(count))
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error accessing memory: {e}[/]")


@memory_app.command("search")
def memory_search(
    query: str = typer.Argument(..., help="Search query"),
    namespace: str = typer.Option("knowledge", "--namespace", "-n", help="Namespace to search"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results"),
):
    """Search NEXUS memory."""
    settings = get_settings()

    async def _search():
        from nexus.memory.chroma_service import NexusMemoryService
        service = NexusMemoryService(persist_dir=settings.chroma_persist_dir)
        return await service.search(query=query, namespace=namespace, top_k=top_k)

    try:
        results = asyncio.run(_search())
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]

        if not ids:
            console.print(f"[yellow]No results found for '{query}' in {namespace}[/]")
            return

        for i, (doc_id, doc, dist) in enumerate(zip(ids, documents, distances)):
            console.print(Panel(
                f"{doc[:500]}",
                title=f"#{i+1} (distance: {dist:.3f})",
                subtitle=f"ID: {doc_id}",
            ))
    except Exception as e:
        console.print(f"[red]Error: {e}[/]")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Bind host"),
    port: int = typer.Option(8080, "--port", "-p", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload (dev)"),
    log_level: str = typer.Option("info", "--log-level", "-l", help="Log level"),
):
    """Start the NEXUS FastAPI backend server."""
    import uvicorn

    settings = get_settings()
    bind_host = host or settings.nexus_host
    bind_port = port or settings.nexus_port

    console.print(Panel(
        f"[bold green]NEXUS Backend Server[/]\n"
        f"Host: {bind_host}\n"
        f"Port: {bind_port}\n"
        f"API Docs: http://localhost:{bind_port}/docs",
        title="Starting",
    ))

    uvicorn.run(
        "nexus.api.gateway:app",
        host=bind_host,
        port=bind_port,
        reload=reload,
        log_level=log_level.lower(),
        access_log=True,
    )


if __name__ == "__main__":
    app()
