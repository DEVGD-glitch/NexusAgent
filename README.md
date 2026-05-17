# NEXUS Agent — Universal Sovereign AI Agent

> **The only AI agent combining 13 LLM providers, 3 orchestration engines, 5-layer memory, 43+ MCP tools, 3D avatar, voice pipeline, and full-stack UI — all self-hosted.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org/)

---

## What is NEXUS?

NEXUS is a **sovereign AI agent** — a complete, self-hosted AI assistant that runs entirely on your infrastructure. No cloud dependencies, no data leaks, no vendor lock-in.

### What makes it unique?

| Feature | NEXUS | CrewAI | LangGraph | AutoGen | Dify |
|---------|-------|--------|-----------|---------|------|
| **13 LLM Providers** | ✅ | ❌ | Via LC | ❌ | ✅ |
| **3 Free Providers** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **3 Orchestration Engines** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **5-Layer Memory** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **43+ MCP Tools** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **3D Avatar + Voice** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Full-Stack UI** | ✅ | ❌ | ❌ | ❌ | ✅ |
| **Computer Use** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Sovereign (Self-Hosted)** | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## Quick Start (One-Click)

### Prerequisites

- **Python 3.11+** — [Download](https://www.python.org/downloads/)
- **Node.js 18+** or **Bun** — [Download](https://nodejs.org/)

### 1. Clone & Install (one command)

```bash
git clone https://github.com/your-org/nexus-agent.git
cd nexus-agent
python install.py
```

The installer will:
- Create a Python virtual environment
- Install all backend dependencies
- Install all frontend dependencies
- Set up the database (Prisma/SQLite)
- Create `.env` files with sensible defaults

### 2. Configure (optional)

```bash
# Edit backend config (add your API keys for better models)
# By default, free providers (Pollinations, G4F) work without any key
nano NexusAgent/.env
```

### 3. Start (one command)

```bash
python start.py
```

This launches both the backend (port 8081) and frontend (port 3000).

### 4. Open

- **Web UI**: http://localhost:3000
- **API Docs**: http://localhost:8081/docs
- **TUI**: `nexus tui`

### Alternative: Manual Start

```bash
# Backend
cd NexusAgent
source venv/bin/activate  # or venv\Scripts\activate on Windows
nexus serve --port 8081

# Frontend (in another terminal)
npm run dev
```

### Alternative: Docker

```bash
cd NexusAgent
docker-compose up -d
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Next.js 16)                 │
│  Chat │ Voice │ Avatar 3D │ GenUI │ Dashboard │ Plugins │
└───────────────────────┬─────────────────────────────────┘
                        │ WebSocket + REST
┌───────────────────────┴─────────────────────────────────┐
│                  Backend (FastAPI)                        │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │  LLM    │  │  Memory  │  │  Agents  │  │ Security │ │
│  │ Router  │  │ 5-Layer  │  │ 4 Types  │  │  Vault   │ │
│  │13 Provid│  │ ChromaDB │  │ +OpenAI  │  │Guardrails│ │
│  └─────────┘  └──────────┘  └──────────┘  └──────────┘ │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │Orchestr.│  │  Hooks   │  │  Rules   │  │  Modes   │ │
│  │LangGraph│  │ 19 Points│  │  YAML    │  │Safe/Bal/ │ │
│  │CrewAI   │  │ 3 Builtins│  │ 4 Scopes │  │Auto/Sand │ │
│  │ADK      │  └──────────┘  └──────────┘  └──────────┘ │
│  └─────────┘  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│               │  Plugins │  │ Workflows│  │   MCP    │ │
│               │  Sandbox │  │ Trigger/ │  │Marketplace│ │
│               │  Lifecycle│  │ Cond/Act│  │  Toggle  │ │
│               └──────────┘  └──────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## Features

### Multi-LLM (13 Providers)
- **Free**: Pollinations, G4F, DeepInfra (no API key needed)
- **Paid**: OpenAI, Anthropic, Google, Groq, OpenRouter, NVIDIA, Cerebras, Together, GLM, Ollama
- Automatic fallback chain with health monitoring
- Cost estimation per provider

### 5-Layer Memory (ChromaDB)
1. **Working** — Current conversation context
2. **Episodic** — Past interactions and events
3. **Semantic** — Facts and knowledge
4. **Procedural** — How-to patterns
5. **Identity** — User preferences and profile

### 3 Orchestration Engines
- **LangGraph** — Graph-based workflow orchestration
- **CrewAI** — Multi-agent team collaboration
- **ADK** — Agent Development Kit integration
- 6 patterns: supervisor, pipeline, parallel, hierarchical, mesh, swarm

### 4 Specialized Agents
- **Researcher** — Web search, deep research, synthesis
- **Developer** — Code gen, review, debugging, testing
- **Analyst** — Data analysis, visualization, reporting
- **Operator** — Deployment, monitoring, incident response

### Security
- **Vault** — Encrypted secret storage with atomic writes
- **Guardrails** — Prompt injection detection, PII filtering
- **Sandbox** — Docker-based code execution isolation
- **Rate Limiter** — Per-window token bucket
- **Audit Trail** — Complete action logging
- **Permission Manager** — Per-agent permission control

### UI
- **Web** — Next.js 16 with real-time WebSocket
- **TUI** — Textual-based terminal interface (7 panels)
- **Avatar** — 3D VRM with lip-sync and expressions
- **Voice** — VAD → STT → LLM → TTS pipeline
- **GenUI** — Dynamic cards inline in chat

---

## CLI Commands

```bash
nexus --help              # Show all commands
nexus tui                 # Launch interactive TUI
nexus serve               # Start API server
nexus chat "question"     # One-shot chat
nexus task "task"         # Execute a task
nexus status              # System status
nexus modes               # List agent modes
nexus mode <mode>         # Switch mode (safe/balanced/auto/sandbox)
nexus config              # Show configuration
nexus config --set KEY=VAL # Set config value
nexus plugins             # List plugins
nexus providers           # List LLM providers
nexus models              # List models
```

---

## TUI (Terminal Interface)

Launch with `nexus tui`. Features:

| Panel | Key | Description |
|-------|-----|-------------|
| Chat | F1 | Main conversation interface |
| Terminal | F2 | Execute shell commands |
| Files | F3 | Filesystem browser |
| Logs | F4 | Real-time log viewer |
| Metrics | F5 | CPU, RAM, tokens, agents |
| Approvals | F6 | HITL approval queue |
| Agents | F7 | Multi-agent monitor |

**Commands**: `/help`, `/status`, `/agents`, `/mode`, `/plugins`, `/mcps`, `/clear`, `/quit`

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | Send message (supports streaming) |
| POST | `/task` | Execute a task |
| GET | `/status` | System status |
| GET | `/memory/stats` | Memory layer counts |
| POST | `/memory/compact` | Compact memory |
| GET | `/mcp` | List MCP servers |
| POST | `/mcp/install` | Install MCP |
| GET | `/plugins` | List plugins |
| POST | `/plugins` | Install plugin |
| GET | `/modes` | List modes |
| POST | `/modes/set` | Switch mode |
| WS | `/ws` | Real-time events |

Full API docs at http://localhost:8081/docs

---

## Configuration

### Environment Variables

```bash
# LLM Providers (at least one required)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
GROQ_API_KEY=gsk_...

# Free providers (no key needed)
# Pollinations, G4F, DeepInfra are built-in

# Backend
NEXUS_HOST=0.0.0.0
NEXUS_PORT=8081
NEXUS_DEBUG=false

# Memory
CHROMA_PERSIST_DIR=./nexus_data/chroma

# Security
NEXUS_SECRET_KEY=your-secret-key-here
```

### Agent Modes

| Mode | Confirmation | Code Exec | Network | Agent Spawn |
|------|-------------|-----------|---------|-------------|
| **Safe** | Always | ❌ | ❌ | ❌ |
| **Balanced** | Dangerous only | ✅ | ✅ | ❌ |
| **Auto** | Never | ✅ | ✅ | ✅ |
| **Sandbox** | Always | ✅ | ❌ | ❌ |

---

## Project Structure

```
nexus-agent/
├── NexusAgent/                  # Python backend
│   ├── nexus/
│   │   ├── agents/              # 4 specialized agents
│   │   ├── api/                 # FastAPI gateway
│   │   ├── browser/             # Playwright integration
│   │   ├── cli/                 # CLI + TUI
│   │   ├── comms/               # Voice, avatar, Telegram
│   │   ├── computer/            # Desktop automation
│   │   ├── core/                # Config, DI, registry
│   │   ├── dev/                 # Code gen, git, review
│   │   ├── hooks/               # 19 lifecycle hooks
│   │   ├── knowledge/           # Graph, RAG, research
│   │   ├── llm/                 # 13 LLM providers
│   │   ├── mcp/                 # MCP marketplace
│   │   ├── mcp_tools/           # 43+ MCP tools
│   │   ├── memory/              # 5-layer ChromaDB
│   │   ├── modes/               # Safe/Balanced/Auto/Sandbox
│   │   ├── monitoring/          # Metrics, dashboard
│   │   ├── orchestrator/        # LangGraph/CrewAI/ADK
│   │   ├── plugins/             # Plugin system
│   │   ├── reasoning/           # ReAct, ToT, LATS
│   │   ├── rules/               # YAML rule engine
│   │   ├── security/            # Vault, guardrails, sandbox
│   │   ├── tools/               # Local tool registry
│   │   └── workflows/           # Trigger/condition/action
│   ├── tests/                   # 2200+ test functions
│   └── pyproject.toml
├── src/                         # Next.js frontend
│   ├── app/                     # App router
│   ├── components/nexus/        # 15 custom components
│   ├── hooks/                   # WebSocket, toast, mobile
│   ├── lib/                     # API, store, utils
│   └── types/                   # TypeScript definitions
├── package.json
└── README.md
```

---

## Testing

```bash
# Backend tests
cd NexusAgent
pytest tests/ -v

# With coverage
pytest tests/ --cov=nexus --cov-report=html

# Frontend (when configured)
npm run test
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch
3. Write tests first (TDD)
4. Implement the feature
5. Run tests and lint
6. Submit a pull request

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- [LiteLLM](https://github.com/BerriAI/litellm) — Multi-provider LLM interface
- [ChromaDB](https://github.com/chroma-core/chroma) — Vector database
- [Textual](https://github.com/Textualize/textual) — TUI framework
- [Next.js](https://nextjs.org/) — Frontend framework
- [FastAPI](https://fastapi.tiangolo.com/) — Backend framework
- [Three.js](https://threejs.org/) + [@pixiv/three-vrm](https://github.com/pixiv/three-vrm) — 3D avatar
