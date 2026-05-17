<div align="center">

# 🧠 NEXUSAgent

### Agent IA Souverain Universel — Zéro Cloud. Zéro Compromis. Production-Ready.

**NEXUSAgent** est un agent IA personnel qui vit sur **ton PC**. Pas de cloud imposé, pas de compte obligatoire, pas de données qui fuient. Tu choisis tes modèles, tes clés, tes permissions. Architecture 3-tier complète : backend Python, frontend Next.js, bureau Electron.

[![License: MIT](https://img.shields.io/badge/License-MIT-emerald?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&style=flat-square)]()
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=next.js&style=flat-square)]()
[![Electron](https://img.shields.io/badge/Electron-33-47848F?logo=electron&style=flat-square)]()
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-0078D6?style=flat-square)]()
[![Tests](https://img.shields.io/badge/Tests-40%20%E2%9C%85%20%E2%80%94%2022k%2B%20lignes-22c55e?style=flat-square)]()

[📥 Installation](#-installation-rapide) · [🚀 Démarrage](#-démarrage-rapide) · [🎯 Fonctionnalités](#-fonctionnalités) · [📖 Documentation](docs/) · [🤝 Contribuer](CONTRIBUTING.md)

</div>

---

## 🌟 Vision

NEXUSAgent vise à démocratiser l'accès à l'IA en offrant un agent souverain, extensible et gratuit. Chaque utilisateur possède son propre agent IA complet — avec mémoire persistante, raisonnement avancé, outils MCP, et une interface immersive — sans dépendre d'aucun cloud tiers. Trois providers gratuits intégrés permettent un démarrage immédiat sans clé API.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    NEXUSAgent — Architecture 3-Tier             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐   ┌──────────────────┐   ┌────────────┐ │
│  │   Electron App   │   │   Next.js 16 UI  │   │  CLI Typer │ │
│  │  (Bureau natif)  │──▶│   (Frontend)     │──▶│  (Terminal)│ │
│  │  nexus-desktop/  │   │   nexus-web/     │   │  nexus/cli │ │
│  └──────────────────┘   └────────┬─────────┘   └─────┬──────┘ │
│                                  │ HTTP/WS            │        │
│                                  ▼                    ▼        │
│                    ┌──────────────────────────────────────┐     │
│                    │     FastAPI Gateway (port 8080)      │     │
│                    │     nexus/api/gateway.py             │     │
│                    ├──────────────────────────────────────┤     │
│                    │  Chat │ Run │ Tools │ Memory │ WS    │     │
│                    └──────────────┬───────────────────────┘     │
│                                   │                             │
│          ┌────────────────────────┼─────────────────────────┐   │
│          │                        │                         │   │
│  ┌───────▼──────┐  ┌─────────────▼──────┐  ┌──────────────▼┐ │
│  │  LLM Router  │  │  MCP Tool Server   │  │   Sécurité    │ │
│  │  13 providers │  │  43+ outils        │  │  Vault/Guard  │ │
│  │  + 3 gratuits │  │  12 catégories     │  │  Sandbox      │ │
│  └───────┬──────┘  └─────────────┬──────┘  └───────────────┘ │
│          │                       │                             │
│  ┌───────▼───────────────────────▼───────────────────────────┐ │
│  │                   Noyau Nexus (nexus/)                     │ │
│  ├──────────┬──────────┬───────────┬──────────┬──────────────┤ │
│  │ Mémoire  │ Agents   │ Raisonne- │ Connais- │ Orchestr.    │ │
│  │ 5 niveaux│ 5 types  │ ment      │ sances   │ 3 moteurs    │ │
│  │ ChromaDB │ BaseAgent│ ReAct/ToT │ Graphe   │ 6 patterns   │ │
│  │          │ Registry │ LATS/MCTS │ RAG      │ Skills       │ │
│  └──────────┴──────────┴───────────┴──────────┴──────────────┘ │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │  Dev Tools   │  │  Computer    │  │  Avatar VRM            │ │
│  │  Code/Git/   │  │  Use         │  │  VOICEVOX + Lip-Sync   │ │
│  │  Terminal    │  │  GUI/OCR     │  │  100+ voix             │ │
│  └──────────────┘  └──────────────┘  └────────────────────────┘ │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │  Navigateur  │  │  Comms       │  │  Docker                │ │
│  │  Playwright  │  │  Telegram/   │  │  docker-compose.yml    │ │
│  │  Scraping    │  │  Voice/Email │  │  ChromaDB + Browser    │ │
│  └──────────────┘  └──────────────┘  └────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Stats : 30 000+ lignes Python · 22 000+ lignes tests · 110+ fichiers · 22 modules
```

| Couche | Technologie | Répertoire |
|--------|------------|------------|
| **Backend** | Python 3.11+, FastAPI, LiteLLM, ChromaDB | `nexus/` |
| **Frontend Web** | Next.js 16, React 19, shadcn/ui, Zustand | `nexus-web/` |
| **Bureau** | Electron 33, electron-builder | `nexus-desktop/` |
| **CLI** | Typer, Rich | `nexus/cli/` |
| **Conteneurs** | Docker, docker-compose | `docker/`, `docker-compose.yml` |

---

## 🎯 Fonctionnalités

### 🧠 Multi-LLM — 13 Providers (dont 3 gratuits)

| Provider | Gratuit ? | Modèles principaux |
|----------|-----------|-------------------|
| **Pollinations.ai** 🆓 | ✅ Sans clé | 29 modèles (GPT, Claude, Gemini, DeepSeek...) |
| **G4F.dev** 🆓 | ✅ Sans clé | 200+ modèles (Llama 4, Qwen, Mistral, Grok...) |
| **DeepInfra** 🆓 | ✅ Sans clé | Llama 4, Qwen 3, DeepSeek V3 |
| OpenAI | ❌ Clé API | GPT-4o, GPT-4o-mini, o1, o3 |
| Anthropic | ❌ Clé API | Claude 3.5/4 Sonnet, Opus |
| Google Gemini | ❌ Clé API | Gemini 2.5 Pro/Flash, Gemma 4 (+thinking) |
| GLM / ZAI | ❌ Clé API | GLM-5, GLM-4 |
| Ollama (local) | ✅ Local | Llama, Mistral, CodeLlama... |
| Groq | ❌ Clé API | Llama 3.3 70B, Gemma 2 |
| OpenRouter | ❌ Clé API | Routeur multi-modèles |
| NVIDIA | ❌ Clé API | Nemotron 70B |
| Cerebras | ❌ Clé API | Llama 3.1 8B (inférence ultra-rapide) |
| Together AI | ❌ Clé API | Llama 3.3 70B Turbo |

**Routage intelligent** : sélection automatique par complexité de tâche, chaîne de fallback configurable, retry exponentiel sur rate-limit.

### 🗃️ Mémoire 5 Niveaux (ChromaDB)

| Niveau | Type | Usage | Persistance |
|--------|------|-------|-------------|
| L1 | Working | Contexte de session, compression automatique | Session |
| L2 | Episodic | Journal d'expériences vécues | Persistant |
| L3 | Semantic | Faits et connaissances structurés | Persistant |
| L4 | Procedural | Compétences cristallisées | Persistant |
| L5 | Identity | Profil utilisateur, préférences | Persistant |

Compaction automatique, recherche vectorielle, namespaces séparés, orchestrateur de mémoire unifié.

### 🎯 Orchestration & Raisonnement

- **3 moteurs d'orchestration** : LangGraph (plan-execute-reflect), CrewAI (collaboratif), Google ADK
- **6 patterns** : Pipeline, Parallel, Supervisor, Swarm, Routage, Skills
- **3 modes de raisonnement** : ReAct (Reason+Act), Tree-of-Thought (exploration arborescente), LATS/MCTS (Monte Carlo Tree Search)
- **5 agents spécialisés** : General, Researcher, Developer, Analyst, Operator
- **BaseAgent** abstrait avec cycle de vie complet (initialize → plan → execute → reflect → finalize)
- **OpenAI Agents SDK** intégré (couche de compatibilité)

### 🔧 43+ Outils MCP (12 catégories)

| Catégorie | Outils | Description |
|-----------|--------|-------------|
| **Mémoire** (5) | search_memory, store_memory, delete_memory, list_namespaces, memory_stats | Recherche vectorielle ChromaDB |
| **Connaissances** (5) | knowledge_query, knowledge_add_entity, knowledge_add_relation, knowledge_search, knowledge_paths | Graphe de connaissances NetworkX |
| **LLM** (4) | llm_complete, llm_stream, llm_list_models, llm_provider_status | Routage multi-providers |
| **Agents** (5) | spawn_agent, list_agents, agent_status, agent_delegate, a2a_discover | Spawning et délégation |
| **Code** (3) | execute_code, execute_sandboxed, install_package | Exécution locale et sandboxée |
| **Fichiers** (7) | read_file, write_file, list_files, delete_file, move_file, copy_file, search_files | Opérations filesystem sécurisées |
| **Web** (3) | web_search, web_scrape, web_screenshot | Recherche et scraping |
| **Raisonnement** (3) | reason_react, reason_tot, reason_lats | Structured reasoning |
| **Orchestration** (4) | run_pipeline, run_parallel, run_supervisor, run_swarm | Patterns multi-agents |
| **Système** (3) | get_status, get_config, health_check | Surveillance système |
| **Bonus** (4) | audit_query, rate_limit_status, deep_research, rag_query | Audit, recherche approfondie |
| **Avatar** (8) | avatar_start, avatar_speak, avatar_set_vrm, avatar_set_expression, avatar_list_voices, avatar_set_speaker, avatar_start_conversation, avatar_expression_from_text | Contrôle VRM/TTS |

### 🛡️ Sécurité & Souveraineté

- **Mode permissions** : auto-approuve ou confirmation manuelle par action
- **Sandbox** : exécution de code isolée (local subprocess + Docker par action)
- **Audit trail** : toutes les actions tracées avec niveau, catégorie, horodatage
- **Vault** : stockage chiffré des secrets (Fernet/cryptography)
- **Guardrails** : protection contre les injections de prompt
- **Rate Limiter** : limitation par IP et par action (token bucket)
- **Path Traversal Protection** : validation stricte des chemins fichiers
- **Auth** : Bearer token en production, CORS configuré

### 🥰 Avatar Waifu VRM

- Avatar 3D anime avec **VOICEVOX** (100+ voix japonaises)
- **Lip-sync** audio → visèmes en temps réel
- **Expressions faciales** détectées dans les réponses LLM (joie, tristesse, réflexion, etc.)
- Support **VRM** / VRoidHub — charge tes propres modèles
- Bridge **VRChat** via OSC
- Pipeline STS complet : VAD → STT → NEXUS LLM → TTS → VRM

### 🖥️ Interface Brick-by-Brick

- Visualisation en temps réel de la construction des réponses (code, fichiers, actions)
- Build steps animés montrant chaque action de l'agent
- WebSocket temps réel pour les événements agent
- 10 panneaux : Chat, Tasks, Memory, Knowledge, Agents, Tools, Code, Security, Status, Settings

### 🔧 Dev & Computer Use

- **Code Engine** : génération, review, refactoring, exécution sandboxée
- **Browser** : Playwright automatisé, screenshots, scraping de pages
- **Computer Use** : contrôle GUI (pyautogui), OCR, vision d'écran
- **Git** : commits, PRs, review intégrés
- **Terminal** : shell autonome avec sécurité

### 💬 Communications

- **Telegram Bot** : agent accessible via Telegram
- **Voice I/O** : entrée/sortie vocale (STT/TTS)
- **Email/Calendar** : intégration messagerie
- **Channels** : canaux de communication multi-protocoles
- **A2A Protocol** : communication inter-agents standardisée

### 📊 Interface Complète (Next.js 16 + shadcn/ui)

| Vue | Description |
|-----|-------------|
| 💬 **Chat** | Conversation markdown avec streaming temps réel, sélection provider |
| 📋 **Tasks** | Mode texte + Visual Flow Builder (drag-and-drop) |
| 🧠 **Memory** | Navigation 5-niveaux avec stats et recherche |
| 🔗 **Knowledge** | Graphe de connaissances interactif, RAG, deep research |
| 🤖 **Agents** | Spawn, monitor, delegate aux sous-agents |
| 🛠️ **Tools** | Catalogue des 43+ outils MCP |
| 💻 **Code** | Éditeur + terminal sandboxé |
| 🛡️ **Security** | Audit, permissions, vault |
| ⚙️ **Settings** | Providers, modèles, API keys, configuration |

---

## 📥 Installation Rapide (3 étapes)

### Méthode 1 : Installation manuelle

```bash
# 1. Cloner le dépôt
git clone https://github.com/YOUR_USERNAME/NexusAgent.git
cd NexusAgent

# 2. Installer les dépendances Python
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install -e ".[dev]"

# 3. Configurer l'environnement
cp .env.example .env
# Éditer .env avec vos clés API (au moins un provider)
```

### Méthode 2 : Script universel (Windows / macOS / Linux)

```bash
git clone https://github.com/YOUR_USERNAME/NexusAgent.git
cd NexusAgent
python install.py
```

> 💡 **Astuce** : Les 3 providers gratuits (Pollinations, G4F, DeepInfra) fonctionnent immédiatement sans clé API !

---

## 🚀 Démarrage Rapide

```bash
# Lance tout (backend + frontend) en une commande
python start.py
# → http://localhost:3000

# Ou manuellement :
python -m nexus serve    # Backend seul
npm run dev              # Frontend seul

# Mode CLI interactif
python -m nexus chat
npm start
```

### Docker

```bash
# Lancer toute la stack avec Docker
docker-compose up -d

# Services disponibles :
# - NEXUS Core API : http://localhost:8080
# - ChromaDB       : http://localhost:8000
# - Browser Service : http://localhost:8001
```

---

## ⚙️ Configuration

Créer un fichier `.env` à la racine (voir `.env.example`) :

```env
# ── Environnement ──
NEXUS_ENV=development          # development | staging | production
NEXUS_SECRET_KEY=change-me     # Obligatoire en production !
NEXUS_HOST=0.0.0.0
NEXUS_PORT=8080

# ── LLM Providers (au moins un requis, 3 gratuits sans clé) ──
GOOGLE_API_KEY=your-key        # Gemini / Gemma
OPENAI_API_KEY=your-key        # GPT-4o, o1
ANTHROPIC_API_KEY=your-key     # Claude 3.5/4
GROQ_API_KEY=your-key          # Llama 3.3 70B
OPENROUTER_API_KEY=your-key    # Routeur multi-modèles
NVIDIA_API_KEY=your-key        # Nemotron
CEREBRAS_API_KEY=your-key      # Inférence rapide
TOGETHER_API_KEY=your-key      # Llama Turbo
ZAI_API_KEY=your-key           # GLM-4/5

# ── Ollama (local, gratuit) ──
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_DEFAULT_MODEL=llama3.1:8b

# ── Mémoire (ChromaDB) ──
CHROMA_PERSIST_DIR=./nexus_data/chroma

# ── Sécurité ──
RATE_LIMIT_RPM=60
SANDBOX_ENABLED=true

# ── Router LLM ──
LLM_DEFAULT_PROVIDER=gemini
LLM_DEFAULT_MODEL=gemini-2.5-flash
LLM_FALLBACK_CHAIN=gemini,groq,openrouter,nvidia,cerebras,openai,anthropic,glm,ollama,pollinations
```

> 🆓 **Pas de clé API ?** Pollinations, G4F et DeepInfra fonctionnent sans clé. Démarrez immédiatement !

---

## 📡 API Documentation

Le backend expose une API REST complète sur le port 8080. Le frontend Next.js proxy les requêtes via `/api/nexus/*`.

### Endpoints principaux

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/chat` | Chat completion (LLM multi-provider) |
| `POST` | `/chat/stream` | Chat completion en streaming SSE |
| `POST` | `/run` | Exécuter une tâche (orchestrateur Plan-Execute-Reflect) |
| `POST` | `/tools/{tool_name}` | Exécuter un outil MCP (43+ outils) |
| `GET`  | `/tools/search_memory` | Recherche mémoire (query params) |
| `GET`  | `/tools/{tool_name}` | Exécuter un outil en GET |
| `GET`  | `/memory/stats` | Statistiques mémoire par namespace |
| `GET`  | `/memory/namespaces` | Lister les namespaces mémoire |
| `GET`  | `/knowledge/query` | Requête graphe de connaissances |
| `GET`  | `/knowledge/search` | Recherche d'entités |
| `POST` | `/agents/spawn` | Créer un sous-agent |
| `GET`  | `/agents/list` | Lister les agents actifs |
| `POST` | `/code/execute` | Exécuter du code (sandboxé) |
| `GET`  | `/status` | Statut complet de l'agent |
| `GET`  | `/providers` | Statut des providers LLM |
| `GET`  | `/health` | Health check |
| `GET`  | `/config` | Configuration actuelle |
| `POST` | `/config` | Mettre à jour la configuration |
| `GET`  | `/security/audit` | Journal d'audit |
| `WS`   | `/ws` | WebSocket temps réel (événements agent) |
| `GET`  | `/ws/status` | Statut des connexions WebSocket |

### Exemples de requêtes

```bash
# Chat simple
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Bonjour !"}], "provider": "gemini"}'

# Exécuter une tâche complexe
curl -X POST http://localhost:8080/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Analyse ce dataset et génère un rapport"}'

# Recherche web via outil MCP
curl -X POST http://localhost:8080/tools/web_search \
  -H "Content-Type: application/json" \
  -d '{"query": "NexusAgent AI", "num_results": 5}'

# Statut de l'agent
curl http://localhost:8080/status
```

📚 Documentation complète : [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md)

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [`docs/INSTALLATION.md`](docs/INSTALLATION.md) | Guide d'installation complet (Windows, macOS, Linux, Docker) |
| [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) | Référence API exhaustive (endpoints, formats, exemples) |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Architecture détaillée avec descriptions des modules |
| [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) | Toutes les options de configuration et variables .env |
| [`PLAN.md`](PLAN.md) | Plan directeur du projet |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Guide de contribution |
| [`SECURITY.md`](SECURITY.md) | Politique de sécurité |
| [`CHANGELOG.md`](CHANGELOG.md) | Journal des modifications |

---

## 🧪 Tests

```bash
# 40 tests d'acceptance — prêts à l'emploi
pytest tests/test_user_acceptance.py -v

# Suite complète
pytest tests/ -v

# Couverture de code
pytest --cov=nexus --cov-report=html

# Tests par module
pytest tests/llm/ -v         # Tests LLM Router
pytest tests/memory/ -v      # Tests Mémoire
pytest tests/security/ -v    # Tests Sécurité
pytest tests/agents/ -v      # Tests Agents
pytest tests/reasoning/ -v   # Tests Raisonnement
```

---

## 🔑 Obtenir des clés API

| Provider | Obtenir une clé |
|----------|----------------|
| OpenAI | https://platform.openai.com/api-keys |
| Anthropic | https://console.anthropic.com |
| Google Gemini | https://aistudio.google.com |
| Zhipu / GLM | https://open.bigmodel.cn |
| Groq | https://console.groq.com |
| OpenRouter | https://openrouter.ai |
| NVIDIA | https://build.nvidia.com |
| Cerebras | https://cloud.cerebras.ai |
| Together AI | https://api.together.xyz |
| **Pollinations** 🆓 | ✅ **Aucune clé nécessaire** |
| **G4F** 🆓 | ✅ **Aucune clé nécessaire** |
| **DeepInfra** 🆓 | ✅ **Aucune clé nécessaire** |
| Ollama | Installation locale (gratuit) |

---

## 🛠️ Développement

```bash
# Installer les dépendances de développement
pip install -e ".[dev]"

# Linter
ruff check nexus/

# Type checking
mypy nexus/

# Frontend
cd nexus-web
npm install
npm run dev          # http://localhost:3000

# Bureau
cd nexus-desktop
npm install
npm start
```

### Structure du projet

```
NexusAgent/
├── nexus/                    # Backend Python
│   ├── __init__.py
│   ├── __main__.py           # Point d'entrée CLI
│   ├── core/                 # Config, DI, Gateway, Registry, A2A, Events
│   ├── llm/                  # Routeur LLM + 13 providers
│   │   └── providers/
│   │       ├── openai_provider.py
│   │       ├── anthropic_provider.py
│   │       ├── gemini_provider.py
│   │       ├── glm_provider.py
│   │       ├── ollama_provider.py
│   │       └── free/         # Providers gratuits
│   │           ├── pollinations_provider.py
│   │           ├── g4f_provider.py
│   │           └── deepinfra_provider.py
│   ├── memory/               # Mémoire 5 niveaux ChromaDB
│   ├── mcp_tools/            # 43+ outils MCP (12 catégories)
│   ├── mcp_server.py         # Serveur MCP FastMCP
│   ├── agents/               # 5 types d'agents spécialisés
│   ├── orchestrator/         # 3 moteurs + 6 patterns
│   ├── reasoning/            # ReAct, ToT, LATS
│   ├── security/             # Vault, Guardrails, Sandbox, Audit
│   ├── knowledge/            # Graphe, RAG, Deep Research, Web Search
│   ├── dev/                  # Code Engine, Git, Terminal, Deploy
│   ├── computer/             # GUI Control, Screen, Process Manager
│   ├── comms/                # Telegram, Voice, Email, Avatar VRM
│   ├── browser/              # Playwright, Browser Service
│   ├── api/                  # FastAPI Gateway, Puter Proxy
│   ├── cli/                  # Interface CLI Typer
│   ├── a2a/                  # Agent-to-Agent Protocol
│   ├── patterns/             # Patterns réutilisables
│   └── workflows/            # Workflows nommés
├── nexus-web/                # Frontend Next.js 16
│   ├── src/
│   │   ├── app/              # Pages Next.js
│   │   ├── components/
│   │   │   ├── nexus/        # Composants NEXUS (chat, memory, agents...)
│   │   │   └── ui/           # Composants shadcn/ui
│   │   ├── hooks/            # Hooks React (WebSocket, API)
│   │   ├── lib/              # Utilitaires, store Zustand, client API
│   │   └── types/            # Types TypeScript
│   └── package.json
├── nexus-desktop/            # Application bureau Electron
│   ├── src/main.js
│   └── package.json
├── tests/                    # Suite de tests (22k+ lignes)
│   ├── llm/
│   ├── memory/
│   ├── security/
│   ├── agents/
│   ├── reasoning/
│   ├── orchestrator/
│   ├── knowledge/
│   ├── mcp_tools/
│   ├── gateway/
│   ├── core/
│   └── cli/
├── docker/                   # Dockerfiles
├── docs/                     # Documentation technique
├── scripts/                  # Scripts utilitaires
├── pyproject.toml            # Configuration Python
├── docker-compose.yml        # Stack Docker
├── requirements.txt          # Dépendances Python
└── .env.example              # Template de configuration
```

---

## 📜 Licence

MIT — voir [`LICENSE`](LICENSE)

---

<div align="center">

**NEXUSAgent** — *L'IA souveraine pour tous.*

</div>
