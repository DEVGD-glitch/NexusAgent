# NEXUS Agent Instructions

## Entry Points

| Command | What it does |
|---------|-------------|
| `python -m nexus` | Desktop app (CustomTkinter) or fallback to CLI |
| `python -m nexus serve` | Start FastAPI backend on :8080 |
| `python -m nexus chat` | Interactive CLI chat |
| `nexus <cmd>` | CLI (via `pyproject.toml` `[project.scripts]`) |
| `python run_nexus.py` | Start API server (alternative) |
| `start_web.bat` | Launch backend + Next.js frontend + browser |
| `start.sh` | Launch backend + frontend (macOS/Linux) |
| `install.bat` | One-click installer (Windows) |
| `install.ps1` | One-click installer (PowerShell) |
| `install.sh` | One-click installer (macOS/Linux) |
| `deploy.ps1` | Git add/commit/push + optional release |
| `install_build.bat` | Full build → `dist/NEXUS.exe` |
| `start_nexus.bat` | Backend-only (no frontend) |

## Test & Quality

```bash
pytest tests/ -v --tb=short                          # all tests
pytest tests/test_user_acceptance.py -v               # pre-flight checks
pytest tests/memory/test_memory_complete.py -v        # single module
pytest -k "test_name_pattern"                         # filtered
pytest --cov=nexus --cov-report=html                  # coverage (fail_under=70)
ruff check nexus/ tests/                               # lint (line-length=120)
mypy nexus/                                            # typecheck (strict)
```

- `pytest-asyncio` mode: `auto` (no `@pytest.mark.asyncio` needed)
- `pytest-cov` omits: desktop, browser, comms, computer, dev (large modules, tested at integration level)
- CI runs on `windows-latest`, Python 3.11, pip cache

## Architecture

**29,506 lines** `nexus/` + **22,551 test lines**. 110+ Python files, 22 modules.

```
nexus/
├── core/           Config (pydantic-settings), DI, gateway, registry, A2A, observability, eval
├── llm/            Router + 8 providers (openai/anthropic/gemini/glm/ollama/pollinations/g4f/deepinfra)
│   └── providers/free/  Pollinations, G4F, DeepInfra (no-cost-ai hub)
├── memory/         5-tier: working → episodic → semantic → procedural → identity, ChromaDB
├── orchestrator/   LangGraph + CrewAI + ADK engines, dynamic router, 6 patterns, skill lifecycle
├── reasoning/      ReAct, Tree-of-Thought, LATS/MCTS, adaptive selector
├── agents/         Base + researcher + developer + analyst + operator + OpenAI Agents SDK layer
├── security/       Sandbox, per-action Docker, audit, guardrails, rate limiter, vault, secrets, permissions
│   └── docker/     PerActionSandbox (ephemeral containers per risky action)
├── knowledge/      Web search, RAG pipeline, deep research, knowledge graph (NetworkX), watchdog
├── dev/            Code engine, code executor, terminal, git integration, deploy
├── computer/       GUI control (PyAutoGUI), screen understanding (OCR+vision), process manager
├── comms/          Telegram bot, voice I/O, email/calendar, channels, **avatar/** 🆕
│   └── avatar/     AIAvatarKit VAD→STT→LLM→TTS→LipSync→VRM pipeline
├── browser/        Browser service + Playwright extensions
├── desktop/        CustomTkinter app (2543 lines), panels/
├── api/            FastAPI gateway (1029 lines), puter proxy
├── cli/            Typer CLI + subcommands (agents, skills, eval, context7, memory)
├─┬ mcp_tools/      16 tool files: system, web, memory, knowledge, agent, code, llm, reasoning,
│ │                 orchestration, file, bonus, context7, **avatar** 🆕
└── mcp_server.py   MCP protocol server (50+ tools, 14 categories)
```
nexus/
├── core/          Config (pydantic-settings), DI, gateway, registry, A2A, observability, supervisor
├── llm/           Router + 5 providers (openai/anthropic/gemini/glm/ollama) + fallback chain
├── memory/        5-tier: working → episodic → semantic → procedural → identity, all on ChromaDB
├── orchestrator/  LangGraph + CrewAI + ADK engines, dynamic router, 6 patterns, skill lifecycle
├── reasoning/     ReAct, Tree-of-Thought, LATS/MCTS, adaptive selector
├── agents/        Base + researcher + developer + analyst + operator + OpenAI Agents SDK layer
├── security/      Sandbox, audit, guardrails, rate limiter, vault, secrets, permissions
├── knowledge/     Web search, RAG pipeline, deep research, knowledge graph (NetworkX), watchdog
├── dev/           Code engine, code executor, terminal, git integration, deploy
├── computer/      GUI control (PyAutoGUI), screen understanding (OCR+vision), process manager
├── comms/         Telegram bot, voice I/O, email/calendar, channels
├── browser/       Browser service + Playwright extensions
├── desktop/       CustomTkinter app (2543 lines), panels/
├── api/           FastAPI gateway (1029 lines), puter proxy
├── cli/           Typer CLI + subcommands (agents, skills, eval, context7, memory)
├─┬ mcp_tools/     15 tool files: system, web, memory, knowledge, agent, code, llm, reasoning,
│ │                orchestration, file, bonus, context7
└── mcp_server.py  MCP protocol server (46 tools, 10 categories)
```

**Config**: `nexus/core/config.py` — pydantic-settings singleton via `get_settings()`, loaded from `.env`. This is the most-connected module in the entire codebase (betweenness 0.233, bridges 38 communities).

**DI**: `nexus/core/di.py` — dependency injection container wiring all services.

## Key Conventions

- **All text in French**: UI, error messages, docs, CLI output. Exceptions: code identifiers, logs
- **Permissions model**: 2-mode (auto-approve / confirm). System paths always require confirmation
- **MCP is the universal protocol**: every capability is exposed as an MCP tool, consumed by all interfaces
- **A2A protocol** in `nexus/core/a2a.py` — inter-agent communication
- **Design pattern**: layered modules communicating through MCP, not direct imports between layers
- **Async-first**: FastAPI + async everywhere in services

## Dependency Details

- `crewai`, `google-adk`, `openai-agents` — now uncommented and required in requirements.txt
- `browser-use` remains in Docker (openai version conflict: browser-use pins `openai==2.16.0`, others need `>=2.26.0`)
- `aiavatar` (AIAvatarKit) commented out — install manually: `pip install aiavatar`
- `docker-compose.yml` runs 3 services: `nexus-core`, `chromadb`, `browser-service` (isolated)
- Optional extras via `pyproject.toml`: `[browser]`, `[desktop]`, `[avatar]`, `[multiagent]`, `[dev]`

## New Modules to Know

### Free Provider Hub (`nexus/llm/providers/free/`)
- Pollinations.ai (29 models, unlimited, no key) → Router enum `Provider.POLLINATIONS`
- G4F.dev (200+ models, rate-limited) → `Provider.G4F`
- DeepInfra (open-source models) → `Provider.DEEPINFRA`
- `FreeProviderRouter` auto-fallbacks: Pollinations → G4F
- All zero-cost, added to COMPLEXITY_ROUTING: SIMPLE tries free providers first

### Avatar Module (`nexus/comms/avatar/`)
- `AvatarManager` → orchestrates full VAD→STT→LLM→TTS→LipSync→VRM pipeline
- Integrates AIAvatarKit (`pip install aiavatar`) for autonomous voice convos
- `VRMRenderer` → Three.js + WebSocket, opens viewer HTML in browser
- `VoiceVoxBridge` → Japanese anime TTS via VOICEVOX (free, 100+ voices)
- `LipSyncEngine` → audio→visemes (energy-based + phoneme-based)
- `FaceController` → detects `[face:joy]` tags in LLM output, VRChat OSC bridge
- 8 MCP tools registered: avatar_start, avatar_speak, avatar_set_vrm, etc.

### Per-Action Docker Sandbox (`nexus/security/docker/`)
- `PerActionSandbox` → fresh ephemeral Docker container per risky action
- Usage: `async with sandbox.isolate("python", code=...) as ctx:`
- Supports python, node, alpine, browser images
- Auto-cleanup on context exit (even on crash)

### Visual Flow Builder (`nexus-web/src/components/nexus/visual-flow-builder.tsx`)
- React Flow drag-drop workflow builder
- 6 node types: LLM, Memory, Code, Web, Agent, Knowledge Graph
- Accessible from TasksPanel → "Visual Flow" tab
- Exports JSON workflows for backend execution
- Requires `reactflow` in npm deps (added to package.json)

### Benchmark Evaluation (`nexus/core/evaluation.py`)
- `SWEBenchEval` (target ≥75% on Verified)
- `HumanEvalEval` (target ≥92%)
- `EvalRunner` → runs all benchmarks, generates markdown report
- CLI: `python -c "from nexus.core.evaluation import EvalRunner; import asyncio; asyncio.run(EvalRunner().run_all())"`

## Desktop & Packaging

- `nexus-desktop/` — Tauri v2 app (Rust sidecar for Python backend)
  - Build: `cd nexus-desktop && npm run build` → produces `.exe`/`.dmg`/`.AppImage`
  - Release: GitHub Actions builds installers for all platforms
  - Sidecar: Python backend bundled via PyInstaller
- `install.bat` / `install.ps1` / `install.sh` — one-click installers (clone → deps → build)
- `start.sh` — backend + frontend launcher for macOS/Linux
- `deploy.ps1` — `git add/commit/push` + optional `git tag` for release

## Frontend Components

| Component | Path | Description |
|-----------|------|-------------|
| `chat-panel.tsx` | `nexus-web/src/components/nexus/` | Chat markdown with streaming |
| `tasks-panel.tsx` | same | Text + **Visual Flow Builder** tabs |
| `avatar-panel.tsx` 🆕 | same | Waifu avatar with expression/voice controls |
| `agent-activity-view.tsx` 🆕 | same | Real-time "brick-by-brick" agent activity |
| `visual-flow-builder.tsx` 🆕 | same | React Flow drag-drop workflow builder |
| Store: `lib/nexus-store.ts` | Zustand state (todo lists, avatar, activity stream) |

## Repo Structure Notes

- `nexus-web/` — Next.js 16 + React 19 + shadcn/ui + Prisma + React Flow
- `nexus-desktop/` — Tauri v2 app (Rust + sidecar Python)
- `nexus_data/` — runtime data (ChromaDB vectors, audit logs, etc.) — gitignored
- `graphify-out/` — knowledge graph from codebase analysis (3,554 nodes, 5,946 edges)
- `PLAN.md` — master project plan with checklist
- `docs/` — technical documentation
- `.coveragerc` — intentionally omits desktop/browser/comms/computer from unit coverage (integration-level testing)
- `INSTALL.md`, `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE` — standard OSS docs

## What NOT To Do

- Do not hardcode API keys — always use `.env` loaded via `nexus/core/config.py`
- Do not add features that send data to third-party servers without explicit user consent (sovereignty principle)
- Do not use raw print() for user-facing output — use `rich` (CLI) or the MCP tool system
- Do not add new providers without implementing in `nexus/llm/providers/` and adding to the router
- Do not add avatar features without going through `AvatarManager` (it handles the full pipeline)
- Do not add free providers to the paid-only routing — free providers go in SIMPLE tier first

## Session Resume (12 Mai 2026)

### État actuel
- **Port backend**: 8081 (le 8080 est pris par Windows svchost)
- **Interface**: chat-centric unifiée (plus que Chat + Paramètres comme panneaux)
- **VRM avatar**: toggle dans sidebar, visible à droite du chat
- **Desktop**: Tauri v2 dans `nexus-desktop/` (`npm run tauri dev`)
- **Frontend**: ~1,500 lignes de code custom + 25 composants shadcn/ui

### Providers LLM (13)
| Provider | Clé | Gratuit | Priorité |
|----------|-----|---------|----------|
| Gemini | GOOGLE_API_KEY | ✅ (défaut) | TOUS |
| Groq | GROQ_API_KEY | ✅ 14k req/j | SIMPLE |
| OpenRouter | OPENROUTER_API_KEY | ✅ 20+ modèles | MEDIUM |
| NVIDIA NIM | NVIDIA_API_KEY | ✅ 100+ modèles | MEDIUM |
| Cerebras | CEREBRAS_API_KEY | ✅ 1M t/j | SIMPLE |
| Together | TOGETHER_API_KEY | ✅ | MEDIUM |
| Pollinations | aucune | ✅ illimité | SIMPLE |
| G4F | aucune | ✅ 200+ modèles | SIMPLE |
| DeepInfra | aucune | ✅ | SIMPLE |
| OpenAI | OPENAI_API_KEY | ❌ | COMPLEX |
| Anthropic | ANTHROPIC_API_KEY | ❌ | COMPLEX |
| GLM | ZAI_API_KEY | ❌ | MEDIUM |
| Ollama | aucune | ✅ local | TOUS |

### Tâches
- Forcé `_run_simple_loop` dans `langgraph_engine.py` (le graphe LangGraph avait des problèmes de state update)
- Les tâches s'exécutent réellement (plan → execute → reflect → résultat)

### Agent awareness
- System prompt injecté dans `/chat` listant tous les outils disponibles
- L'agent sait qu'il peut faire: web_search, execute_code, search_memory, knowledge_query, etc.

### Prochaines étapes
1. Build Tauri desktop: `cd nexus-desktop && npm run tauri build`
2. Streaming temps réel des réponses LLM (SSE)
3. Améliorer rendu VRM 3D (three-vrm + Three.js)
4. Télégram bot (déjà dans nexus/comms/telegram_bot.py)
5. Live Canvas A2UI pour visualisations générées par l'agent
