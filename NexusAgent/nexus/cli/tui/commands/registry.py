"""Command Registry — Slash command system for the NEXUS TUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Awaitable, Any


@dataclass(frozen=True)
class Command:
    """A registered slash command."""

    name: str
    description: str
    handler: Callable[..., Awaitable[str | None]]
    aliases: tuple[str, ...] = ()
    args_hint: str = ""


class CommandRegistry:
    """Registry of slash commands available in the TUI."""

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    def register(self, command: Command) -> None:
        self._commands[command.name] = command
        for alias in command.aliases:
            self._commands[alias] = command

    def get(self, name: str) -> Command | None:
        return self._commands.get(name)

    def list_all(self) -> list[Command]:
        seen: set[str] = set()
        result: list[Command] = []
        for cmd in self._commands.values():
            if cmd.name not in seen:
                seen.add(cmd.name)
                result.append(cmd)
        return sorted(result, key=lambda c: c.name)

    async def execute(self, name: str, args: str = "") -> str | None:
        cmd = self.get(name)
        if cmd is None:
            return f"Unknown command: /{name}. Type /help for available commands."
        try:
            return await cmd.handler(args)
        except Exception as exc:
            return f"Error executing /{name}: {exc}"


def _build_default_registry() -> CommandRegistry:
    """Build the default command registry with built-in commands."""
    registry = CommandRegistry()

    async def _help(args: str) -> str | None:
        lines = ["**Available Commands:**\n"]
        for cmd in registry.list_all():
            alias_str = f" (aliases: {', '.join(cmd.aliases)})" if cmd.aliases else ""
            args_str = f" `{cmd.args_hint}`" if cmd.args_hint else ""
            lines.append(f"- `/{cmd.name}`{args_str} — {cmd.description}{alias_str}")
        return "\n".join(lines)

    registry.register(Command(
        name="help",
        description="Show available commands",
        handler=_help,
        aliases=("h", "?"),
    ))

    async def _status(args: str) -> str | None:
        from nexus.monitoring import get_collector
        collector = get_collector()
        metrics = collector.get_system_metrics()
        return (
            f"**NEXUS Status**\n"
            f"- CPU: {metrics.cpu_percent:.1f}%\n"
            f"- Memory: {metrics.memory_mb:.0f} MB\n"
            f"- Tokens today: {metrics.tokens_used_today:,}\n"
            f"- Tool calls today: {metrics.tool_calls_today:,}\n"
            f"- Errors (1h): {metrics.errors_last_hour}\n"
            f"- Active agents: {len(metrics.agents_running)}"
        )

    registry.register(Command(
        name="status",
        description="Show system status",
        handler=_status,
        aliases=("st",),
    ))

    async def _agents(args: str) -> str | None:
        from nexus.core.registry import AgentRegistry
        agent_registry = AgentRegistry()
        instances = agent_registry.list_instances()
        if not instances:
            return "No active agents."
        lines = ["**Active Agents:**\n"]
        for inst in instances:
            status = inst.status.value if hasattr(inst.status, "value") else inst.status
            lines.append(f"- `{inst.agent_id}` [{inst.agent_type}] — {status}")
        return "\n".join(lines)

    registry.register(Command(
        name="agents",
        description="List active agents",
        handler=_agents,
    ))

    async def _modes(args: str) -> str | None:
        from nexus.modes import get_mode_engine
        engine = get_mode_engine()
        if args.strip():
            mode_name = args.strip().lower()
            try:
                from nexus.modes import AgentMode
                mode = AgentMode(mode_name)
                engine.set_mode(mode)
                return f"Mode switched to **{mode.value}**"
            except ValueError:
                valid = ", ".join(m.value for m in AgentMode)
                return f"Invalid mode. Valid: {valid}"
        current = engine.get_current_mode()
        return (
            f"**Current mode:** {current.value}\n"
            f"Switch with: `/mode <safe|balanced|auto|sandbox>`"
        )

    registry.register(Command(
        name="mode",
        description="Show or switch agent mode",
        handler=_modes,
        args_hint="<safe|balanced|auto|sandbox>",
    ))

    async def _plugins(args: str) -> str | None:
        from nexus.plugins import PluginEngine
        engine = PluginEngine()
        summary = engine.get_status_summary()
        lines = [f"**Plugins:** {summary.get('total', 0)} total\n"]
        for name, status in summary.get("plugins", {}).items():
            icon = "✓" if status == "enabled" else "✗"
            lines.append(f"- {icon} {name} [{status}]")
        return "\n".join(lines)

    registry.register(Command(
        name="plugins",
        description="List plugins",
        handler=_plugins,
    ))

    async def _mcps(args: str) -> str | None:
        from nexus.mcp import MCPRegistry
        registry_inst = MCPRegistry()
        mcps = registry_inst.list_mcp()
        if not mcps:
            return "No MCPs registered."
        lines = ["**MCP Servers:**\n"]
        for mcp in mcps:
            icon = "✓" if mcp.status.value == "enabled" else "✗"
            lines.append(f"- {icon} {mcp.name} [{mcp.status.value}] — ~{mcp.token_cost_estimate} tok")
        return "\n".join(lines)

    registry.register(Command(
        name="mcps",
        description="List MCP servers",
        handler=_mcps,
    ))

    async def _provider(args: str) -> str | None:
        from nexus.llm.router import LLMRouter
        router = LLMRouter()
        status = router.get_provider_status()
        if args.strip():
            # Switch provider
            prov_name = args.strip().lower()
            if prov_name not in status:
                valid = ", ".join(status.keys())
                return f"Unknown provider: `{prov_name}`. Valid: {valid}"
            if not status[prov_name].get("available", False):
                return f"Provider `{prov_name}` is not available (missing API key?)."
            # Store in env for this session
            import os
            os.environ["LLM_DEFAULT_PROVIDER"] = prov_name
            default_model = status[prov_name].get("default_model", "")
            return f"Provider switched to **{prov_name}** (model: `{default_model}`)"
        # Show current providers
        lines = ["**Available Providers:**\n"]
        for name, info in sorted(status.items(), key=lambda x: (not x[1].get("available", False), x[0])):
            icon = "✓" if info.get("available", False) else "✗"
            model = info.get("default_model", "N/A")
            lines.append(f"- {icon} `{name}` — model: `{model}`")
        lines.append("\nSwitch with: `/provider <name>`")
        return "\n".join(lines)

    registry.register(Command(
        name="provider",
        description="Show or switch LLM provider",
        handler=_provider,
        aliases=("prov",),
        args_hint="<name>",
    ))

    async def _model(args: str) -> str | None:
        import os
        current = os.environ.get("LLM_DEFAULT_MODEL", "gemini-2.5-flash")
        if args.strip():
            model_name = args.strip()
            os.environ["LLM_DEFAULT_MODEL"] = model_name
            return f"Model switched to **{model_name}**"
        return (
            f"**Current model:** `{current}`\n"
            f"Switch with: `/model <name>`\n\n"
            f"Popular models:\n"
            f"- `gemma-4-31b-it` — Google Gemma 4 (free)\n"
            f"- `gemini-2.0-flash` — Google Gemini (free tier)\n"
            f"- `gpt-4o` — OpenAI\n"
            f"- `claude-sonnet-4-20250514` — Anthropic\n"
            f"- `llama3.1:8b` — Ollama (local)"
        )

    registry.register(Command(
        name="model",
        description="Show or switch LLM model",
        handler=_model,
        aliases=("mod",),
        args_hint="<name>",
    ))

    async def _clear(args: str) -> str | None:
        return "__CLEAR__"

    registry.register(Command(
        name="clear",
        description="Clear chat history",
        handler=_clear,
        aliases=("cls",),
    ))

    async def _quit(args: str) -> str | None:
        return "__QUIT__"

    registry.register(Command(
        name="quit",
        description="Exit the TUI",
        handler=_quit,
        aliases=("exit", "q"),
    ))

    return registry


# Module-level singleton
_default_registry: CommandRegistry | None = None


def get_command_registry() -> CommandRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = _build_default_registry()
    return _default_registry
