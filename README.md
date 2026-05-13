# NEXUS Agent

<p align="center">
  <strong>Agent IA Souverain — Chat-Centric, Multi-Provider, 5-Layer Memory</strong>
</p>

---

## Qu'est-ce que NexusAgent ?

NexusAgent est un agent IA souverain full-stack : un backend Python (FastAPI) et un frontend Next.js 16 + Tauri v2. Tout passe par le chat — pas de sidebar, pas de panels permanents. L'agent raisonne, exécute des outils, construit du code, mémorise, et vous le présente en temps réel avec des cartes Génératives UI et une visualisation brique-par-brique.

**En un coup d'oeil :**

- **Chat-centric** — Une seule conversation, tout se passe dedans (comme Cursor/Windsurf)
- **5 couches de mémoire** — Working → Episodic → Semantic → Procedural (crystallisation) → Identity
- **13+ providers LLM** — ZhipuAI GLM-4-Flash (gratuit par défaut), OpenAI, Anthropic, Ollama, G4F, Pollinations...
- **47+ outils MCP** — Code, fichiers, web, mémoire, connaissances, agents, orchestration...
- **4 stratégies de raisonnement** — ReAct, Tree-of-Thought, LATS, sélection automatique
- **5 types d'agents** — Developer, Researcher, Analyst, Operator, General
- **3 moteurs d'orchestration** — LangGraph (Plan-Execute-Reflect), CrewAI, Google ADK
- **Voice Pipeline** — VAD (Silero) → STT (Whisper) → LLM → TTS (Edge TTS / VoiceVOX) → Lip-sync
- **VRM 3D Avatar** — Modèles anime 3D avec expressions, lip-sync, gaze tracking + hologramme fallback
- **Visualisation brique-par-brique** — FileTree, CodePreview, DiffViewer, BuildProgress en temps réel
- **Artéfacts** — Rendu HTML, Code, Image, Chart, Document directement dans le chat
- **Sécurité** — Vault chiffré, guardrails, audit log, sandbox Docker, HITL approvals, rate limiting
- **Desktop** — App native via Tauri v2 (1280×800)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    NEXUS AGENT ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐     WebSocket/SSE     ┌─────────────────┐ │
│  │   FRONTEND        │ ◄──────────────────► │   BACKEND        │ │
│  │   Next.js 16      │     REST API         │   FastAPI        │ │
│  │   + Tauri v2      │                      │   Port 8081      │ │
│  │                    │                      │                   │ │
│  │  ┌─ ChatView ────┐│                      │ ┌─ Gateway ─────┐│ │
│  │  │ Chat + GenUI   ││                      │ │ 45+ endpoints ││ │
│  │  │ VRM Avatar     ││                      │ │ + WebSocket   ││ │
│  │  │ LiveViz        ││                      │ └───────────────┘│ │
│  │  │ Artifacts      ││                      │                   │ │
│  │  │ Voice I/O      ││                      │ ┌─ Memory ──────┐│ │
│  │  └────────────────┘│                      │ │ 5 layers      ││ │
│  │  ┌─ Overlays ─────┐│                      │ │ ChromaDB      ││ │
│  │  │ ⌘K Commands    ││                      │ └───────────────┘│ │
│  │  │ ⌘, Settings    ││                      │                   │ │
│  │  │ VRM Hub        ││                      │ ┌─ LLM ─────────┐│ │
│  │  └────────────────┘│                      │ │ 13+ providers ││ │
│  └──────────────────┘                      │ │ Fallback chain││ │
│                                              │ └───────────────┘│ │
│                                              │                   │ │
│                                              │ ┌─ Agents ──────┐│ │
│                                              │ │ 5 types       ││ │
│                                              │ │ 3 orchestrateurs│
│                                              │ │ 4 raisonnements│
│                                              │ └───────────────┘│ │
│                                              │                   │ │
│                                              │ ┌─ Tools ───────┐│ │
│                                              │ │ 47+ MCP tools ││ │
│                                              │ │ Voice pipeline ││ │
│                                              │ │ Knowledge graph│
│                                              │ │ Security vault │
│                                              │ └───────────────┘│ │
│                                              └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## Démarrage Rapide

### Prérequis

- **Node.js** 18+ et **Bun** (ou npm)
- **Python** 3.11+
- **Git**

### 1. Cloner le dépôt

```bash
git clone https://github.com/DEVGD-glitch/NexusAgent.git
cd NexusAgent
```

### 2. Lancer le Backend (FastAPI)

```bash
cd NexusAgent

# Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Installer les dépendances
pip install -r requirements.txt

# Configurer les variables d'environnement
cp .env.example .env
# Éditez .env avec vos clés API (ZhipuAI est gratuit par défaut)

# Lancer le serveur
python run_nexus.py
# → Backend sur http://127.0.0.1:8081
```

### 3. Lancer le Frontend (Next.js)

```bash
# Depuis la racine du projet
bun install
# ou: npm install

# Lancer en mode développement
bun dev
# ou: npm run dev
# → Frontend sur http://localhost:3000
```

### 4. (Optionnel) App Desktop Tauri

```bash
# Prérequis: Rust + Cargo
cd src-tauri
cargo tauri dev
```

### Configuration par défaut

L'agent fonctionne immédiatement avec **ZhipuAI GLM-4-Flash** (100% gratuit, pas de carte bancaire). Pour utiliser d'autres providers, ajoutez vos clés API dans le fichier `.env`.

---

## Structure du Projet

```
NexusAgent/
├── src/                              # Frontend Next.js 16
│   ├── app/
│   │   ├── page.tsx                  # Page principale (ChatView + overlays)
│   │   ├── layout.tsx                # Layout racine (Inter, dark mode, fr)
│   │   ├── globals.css               # Thème OKLCH, variables CSS
│   │   └── api/nexus/[...path]/      # Proxy API vers backend Python
│   ├── components/
│   │   ├── nexus/                    # Composants NEXUS spécifiques
│   │   │   ├── chat-view.tsx         # Hub central (chat, GenUI, avatar, viz, voice)
│   │   │   ├── gen-ui.tsx            # Cartes génératives (Memory, Web, Code, Build, Activity, Knowledge)
│   │   │   ├── vrm-avatar.tsx        # Avatar 3D VRM + hologramme fallback
│   │   │   ├── vrm-hub.tsx           # Modal sélection VRM (Galerie/Local/URL)
│   │   │   ├── live-viz.tsx          # Visualisation brique-par-brique
│   │   │   ├── artifact-renderer.tsx # Rendu d'artéfacts (HTML/Code/Image/Chart/Doc)
│   │   │   ├── voice-ui.tsx          # Bouton micro + TTS playback + waveform
│   │   │   ├── command-palette.tsx   # ⌘K — 22 commandes
│   │   │   └── settings-popover.tsx  # ⌘, — Provider, Voice, Memory, Capabilities
│   │   └── ui/                       # 42 composants shadcn/ui
│   ├── hooks/
│   │   ├── use-nexus-ws.ts           # WebSocket temps réel (15+ event types)
│   │   ├── use-mobile.ts             # Détection mobile
│   │   └── use-toast.ts              # Notifications toast
│   ├── lib/
│   │   ├── nexus-store.ts            # Zustand store (50+ champs, 30+ actions)
│   │   ├── nexus-api.ts              # Client API (35+ méthodes)
│   │   ├── db.ts                     # Prisma client
│   │   └── utils.ts                  # cn() utility
│   └── types/
│       └── nexus.ts                  # Types TypeScript (254 lignes)
│
├── src-tauri/                        # App Desktop Tauri v2
│   ├── tauri.conf.json               # Config: 1280×800, com.nexus-agent.desktop
│   ├── Cargo.toml                    # Dépendances Rust
│   ├── src/main.rs                   # Point d'entrée Rust
│   └── src/lib.rs                    # Builder Tauri
│
├── NexusAgent/                       # Backend Python FastAPI
│   ├── run_nexus.py                  # Script de lancement principal
│   ├── requirements.txt              # Dépendances Python (70+ packages)
│   ├── pyproject.toml                # Config du package nexus-agent
│   ├── docker-compose.yml            # Docker: core + browser
│   ├── nexus/                        # Package Python principal
│   │   ├── api/
│   │   │   ├── gateway.py            # 45+ endpoints REST + WebSocket (3040 lignes)
│   │   │   └── voice_routes.py       # 4 endpoints voix (STT/TTS/stream)
│   │   ├── memory/                   # Système de mémoire 5 couches
│   │   │   ├── orchestrator.py       # Routeur inter-couches
│   │   │   ├── working.py            # Mémoire de travail (token-limited)
│   │   │   ├── episodic.py           # Mémoire épisodique (expériences)
│   │   │   ├── semantic.py           # Mémoire sémantique (faits)
│   │   │   ├── procedural.py         # Mémoire procédurale (skills cristallisés)
│   │   │   ├── identity.py           # Mémoire d'identité (préférences utilisateur)
│   │   │   ├── chroma_service.py     # ChromaDB vector store
│   │   │   └── compactor.py          # Maintenance/compaction mémoire
│   │   ├── reasoning/                # Stratégies de raisonnement
│   │   │   ├── react.py              # ReAct (Reason + Act)
│   │   │   ├── tot.py                # Tree-of-Thought
│   │   │   ├── lats.py               # Language Agent Tree Search
│   │   │   └── selector.py           # Sélection automatique de stratégie
│   │   ├── agents/                   # Types d'agents
│   │   │   ├── base.py               # Agent de base (lifecycle, outils, HITL)
│   │   │   ├── developer.py          # Agent développeur (code, fichiers, build)
│   │   │   ├── researcher.py         # Agent chercheur (web, connaissances)
│   │   │   ├── analyst.py            # Agent analyste (données, rapports)
│   │   │   └── operator.py           # Agent opérateur (déploiement, ops)
│   │   ├── orchestrator/             # Orchestration multi-agents
│   │   │   ├── langgraph_engine.py   # Plan-Execute-Reflect (LangGraph)
│   │   │   ├── crewai_engine.py      # CrewAI multi-agent
│   │   │   ├── adk_engine.py         # Google ADK
│   │   │   ├── patterns.py           # Pipeline, Parallel, Supervisor, Swarm
│   │   │   ├── router.py             # Routage agent/skill
│   │   │   └── skill_lifecycle.py    # Cycle de vie des skills + auto-amélioration
│   │   ├── llm/                      # Routeur LLM multi-provider
│   │   │   ├── router.py             # Routage par complexité + fallback
│   │   │   ├── fallback.py           # Chaîne de fallback gracieux
│   │   │   └── providers/            # 13+ providers
│   │   │       ├── openai_provider.py
│   │   │       ├── anthropic_provider.py
│   │   │       ├── gemini_provider.py
│   │   │       ├── glm_provider.py   # ZhipuAI (gratuit)
│   │   │       ├── ollama_provider.py
│   │   │       └── free/             # Providers gratuits
│   │   │           ├── g4f_provider.py
│   │   │           ├── pollinations_provider.py
│   │   │           └── deepinfra_provider.py
│   │   ├── mcp_tools/                # 47+ outils MCP
│   │   │   ├── code_tools.py         # Exécution de code
│   │   │   ├── file_tools.py         # Opérations fichiers
│   │   │   ├── web_tools.py          # Recherche web
│   │   │   ├── memory_tools.py       # Opérations mémoire
│   │   │   ├── knowledge_tools.py    # Graphe de connaissances
│   │   │   ├── agent_tools.py        # Spawn d'agents
│   │   │   ├── reasoning_tools.py    # Stratégies de raisonnement
│   │   │   ├── orchestration_tools.py# Patterns d'orchestration
│   │   │   └── ...                   # + 5 autres modules
│   │   ├── comms/                    # Communication
│   │   │   ├── voice_pipeline.py     # VAD → STT → TTS → Lip-sync (1016 lignes)
│   │   │   ├── avatar/               # Gestion avatar VRM
│   │   │   │   ├── avatar_manager.py
│   │   │   │   ├── face_controller.py
│   │   │   │   ├── lip_sync.py
│   │   │   │   ├── voicevox_bridge.py
│   │   │   │   └── vrm_renderer.py
│   │   │   ├── email_calendar.py     # Email + calendrier
│   │   │   └── telegram_bot.py       # Bot Telegram
│   │   ├── knowledge/                # Connaissances & Recherche
│   │   │   ├── knowledge_graph.py    # NetworkX (entités, relations, chemins)
│   │   │   ├── rag_pipeline.py       # RAG auto-correcteur
│   │   │   ├── web_search.py         # Recherche multi-sources
│   │   │   └── deep_research.py      # Recherche itérative profonde
│   │   ├── dev/                      # Outils développeur
│   │   │   ├── code_engine.py        # Génération de code IA
│   │   │   ├── code_executor.py      # Exécution sandboxée
│   │   │   ├── terminal.py           # Terminal interactif
│   │   │   ├── git_integration.py    # Opérations Git
│   │   │   └── deploy.py             # Pipeline de déploiement
│   │   ├── security/                 # Sécurité
│   │   │   ├── vault.py              # Coffre chiffré (Fernet)
│   │   │   ├── secrets.py            # Gestion des clés API
│   │   │   ├── audit.py              # Journal d'audit
│   │   │   ├── guardrails.py         # Filtrage contenu + PII
│   │   │   ├── permissions.py        # Contrôle d'accès RBAC
│   │   │   ├── rate_limiter.py       # Limitation par IP
│   │   │   └── sandbox.py            # Sandbox d'exécution
│   │   ├── browser/                  # Automatisation navigateur
│   │   │   ├── browser_service.py    # Playwright
│   │   │   └── playwright_ext.py     # Opérations avancées
│   │   ├── computer/                 # Computer Use
│   │   │   ├── gui_control.py        # Contrôle GUI (souris/clavier)
│   │   │   ├── screen_understanding.py # OCR + détection UI
│   │   │   └── process_manager.py    # Gestion de processus
│   │   └── core/                     # Infrastructure centrale
│   │       ├── config.py             # Pydantic Settings
│   │       ├── events.py             # EventBroadcaster pub/sub
│   │       ├── registry.py           # Registre d'agents
│   │       ├── viz_events.py         # Système de visualisation
│   │       ├── exceptions.py         # Hiérarchie d'exceptions
│   │       └── ...                   # + 8 autres modules
│   ├── tests/                        # 30+ fichiers de test
│   └── docs/                         # Documentation interne
│
├── package.json                      # Dépendances Node.js (87 packages)
├── next.config.ts                    # Config Next.js (standalone)
├── tailwind.config.ts                # Thème OKLCH + dark mode
└── tsconfig.json                     # Config TypeScript
```

---

## Système de Mémoire — 5 Couches

NexusAgent implémente un système de mémoire hiérarchique inspiré de la cognition humaine :

```
┌──────────────────────────────────────────────┐
│           IDENTITY (Préférences)             │  ← Qui est l'utilisateur
├──────────────────────────────────────────────┤
│         PROCEDURAL (Skills cristallisés)      │  ← Comment faire (auto-extrait)
├──────────────────────────────────────────────┤
│          SEMANTIC (Faits & connaissances)     │  ← Ce qui est vrai
├──────────────────────────────────────────────┤
│           EPISODIC (Expériences vécues)       │  ← Ce qui s'est passé
├──────────────────────────────────────────────┤
│           WORKING (Contexte immédiat)         │  ← Ce qui est actif
└──────────────────────────────────────────────┘
```

| Couche | Stockage | Persistant | Description |
|--------|----------|------------|-------------|
| **Working** | RAM (token-limited) | Non | Messages récents, contexte de conversation, budget de tokens avec eviction par priorité |
| **Episodic** | ChromaDB | Oui | Expériences enregistrées avec contexte, rappel par similarité vectorielle |
| **Semantic** | ChromaDB | Oui | Faits vérifiés avec scores de confiance, filtrage par source et catégorie |
| **Procedural** | ChromaDB | Oui | Skills cristallisés depuis des patterns récurrents, suivi du taux de succès, versionnage |
| **Identity** | ChromaDB | Oui | Profil utilisateur, préférences, historique d'interactions, merge intelligent |

**Crystallisation** : Quand l'agent exécute une tâche avec succès à plusieurs reprises, le pattern est automatiquement extrait et stocké comme un skill réutilisable dans la couche Procedural. C'est le mécanisme d'auto-amélioration.

---

## API — Endpoints

### Chat & Tâches

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/chat` | Chat completion avec sélection de provider |
| `POST` | `/chat/stream` | Chat en streaming (SSE token-par-token) |
| `POST` | `/run` | Exécuter une tâche via Plan-Execute-Reflect |

### Mémoire (5 couches)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/memory/stats` | Statistiques mémoire |
| `POST` | `/memory/recall` | Rappel inter-couches intelligent |
| `POST` | `/memory/store` | Stockage auto-routé |
| `POST` | `/memory/episodic/record` | Enregistrer un épisode |
| `POST` | `/memory/episodic/recall` | Rappeler des expériences similaires |
| `POST` | `/memory/semantic/add_fact` | Ajouter un fait |
| `POST` | `/memory/semantic/query` | Interroger la mémoire sémantique |
| `POST` | `/memory/procedural/crystallize` | Cristalliser un skill |
| `POST` | `/memory/procedural/find_relevant` | Trouver des skills pertinents |
| `POST` | `/memory/identity/update` | Mettre à jour le profil |
| `GET` | `/memory/identity/profile` | Lire le profil |
| `POST` | `/memory/compact` | Compacter la mémoire |

### Voix

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/voice/transcribe` | Audio (base64) → texte |
| `POST` | `/voice/synthesize` | Texte → audio + visèmes |
| `GET` | `/voice/voices` | Liste des voix disponibles |
| `WebSocket` | `/voice/stream` | Streaming voix temps réel |

### Outils & Connaissances

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/tools/{tool_name}` | Exécuter un outil MCP (47+ outils) |
| `GET` | `/tools/{tool_name}` | Exécuter un outil via query params |
| `GET` | `/knowledge/query` | Interroger le graphe de connaissances |
| `GET` | `/knowledge/search` | Chercher des entités |
| `POST` | `/code/execute` | Exécuter du code (sandboxé ou local) |

### Agents & Orchestration

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/agents/spawn` | Créer un sub-agent |
| `GET` | `/agents/list` | Lister les types d'agents |
| `GET` | `/capabilities` | Capacités complètes de l'agent |

### Skills & Crons

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/skills` | Lister les skills cristallisés |
| `POST` | `/skills/crystallize` | Cristalliser un skill manuellement |
| `POST` | `/skills/execute` | Exécuter un skill par nom |
| `POST` | `/crons/schedule` | Planifier une tâche récurrente |
| `GET` | `/crons/list` | Lister les tâches planifiées |
| `DELETE` | `/crons/{id}` | Annuler une tâche |

### Système

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/status` | Statut système complet |
| `GET` | `/providers` | État des providers LLM |
| `GET` | `/config` | Configuration (non-sensible) |
| `GET` | `/security/audit` | Journal d'audit |
| `WebSocket` | `/ws` | Événements temps réel |

---

## Frontend — Composants

### ChatView — Le Hub Central

Le composant `ChatView` est le point d'entrée unique. Tout se passe dans le chat :

- **Messages** avec Markdown, coloration syntaxique, cartes GenUI intégrées
- **Streaming** — Tokens affichés en temps réel avec curseur clignotant
- **GenUI Cards** — Memory, Web, Code, Build, Activity, Knowledge rendues dans les messages
- **Avatar VRM** — Zone gauche avec hologramme ou modèle 3D
- **LiveViz** — Panel latéral avec FileTree, CodePreview, DiffViewer
- **Artifacts** — Rendu HTML/Code/Image/Chart dans un panel latéral
- **Voice** — Bouton micro + TTS playback
- **HITL** — Bannières d'approbation en chat
- **Persistence** — Conversations sauvées dans localStorage

### VRM Avatar

- **Modèle 3D** via `@pixiv/three-vrm` + `GLTFLoader`
- **7 expressions** mappées aux blend shapes : neutral, joy, thinking, surprise, relaxed, sad, angry
- **Lip-sync** — Visèmes A/I/U/E/O avec transitions fluides (~300ms)
- **Gaze tracking** — L'avatar regarde vers le chat quand l'utilisateur tape
- **Hologramme fallback** — Sphère cyan avec anneaux orbitaux, yeux lumineux, bouche animée
- **VRM Hub** — Modal pour sélectionner un avatar (Galerie CC0 / Fichier local / URL)

### Visualisation Brique-par-Brique

Quand l'agent construit quelque chose, la visualisation montre en temps réel :

- **FileTree** — Arborescence avec icônes colorées par type de fichier, indicateurs nouveau/modifié
- **CodePreview** — Code avec coloration syntaxique, curseur streaming, révélation ligne-par-ligne
- **DiffViewer** — Vue côte-à-côte avec ajouts (vert) et suppressions (rouge)
- **BuildProgress** — Barre de progression + liste des étapes avec statuts

---

## Providers LLM

| Provider | Tier | Modèles | Clé API |
|----------|------|---------|---------|
| **ZhipuAI** | Gratuit | glm-4-flash, glm-4.5-flash | Oui (gratuit) |
| **Pollinations** | Gratuit | openai | Non |
| **G4F** | Gratuit | gpt-4 | Non |
| **DeepInfra** | Gratuit | serverless | Oui (gratuit) |
| **Ollama** | Local | llama3.1:8b, etc. | Non |
| **OpenAI** | Payant | gpt-4o, gpt-4 | Oui |
| **Anthropic** | Payant | claude-sonnet-4 | Oui |
| **Gemini** | Payant | gemini-pro, gemini-flash | Oui |
| **Groq** | Payant | mixtral, llama | Oui |
| **OpenRouter** | Payant | multi-model | Oui |

**Fallback chain** : Si un provider échoue, le routeur essaie automatiquement le suivant dans la chaîne. La sélection se fait par complexité de la tâche (simple → modèle rapide, complexe → modèle puissant).

---

## Sécurité

| Composant | Description |
|-----------|-------------|
| **Vault** | Coffre chiffré Fernet pour les secrets |
| **Guardrails** | Filtrage entrées/sorties, détection PII |
| **Audit Log** | Journal complet de toutes les actions |
| **Permissions** | RBAC (Role-Based Access Control) |
| **Rate Limiter** | Limitation par IP (token bucket) |
| **Sandbox** | Exécution de code isolée (Docker ou subprocess restreint) |
| **HITL** | Approbation humaine requise pour les actions à risque |

---

## Outils MCP (47+)

| Catégorie | Outils |
|-----------|--------|
| **Code** | `execute_code`, `execute_sandboxed`, `install_package` |
| **Fichiers** | `read_file`, `write_file`, `list_files`, `delete_file`, `move_file`, `copy_file` |
| **Web** | `web_search` |
| **Mémoire** | `search_memory`, `store_memory`, `delete_memory`, `memory_recall`, `episodic_record`, `semantic_add_fact`, `procedural_crystallize`, `identity_update` |
| **Connaissances** | `knowledge_query`, `knowledge_add_entity`, `knowledge_search`, `knowledge_paths`, `knowledge_add_relation` |
| **Agents** | `spawn_agent`, `list_agents` |
| **Raisonnement** | `reason_react`, `reason_tot` |
| **Orchestration** | `run_pipeline`, `run_parallel`, `run_supervisor`, `run_swarm` |
| **Skills** | `list_skills`, `crystallize_skill`, `execute_skill` |
| **Avatar** | `avatar_start`, `avatar_speak`, `avatar_set_vrm`, `avatar_set_expression`, `avatar_list_voices` |
| **Système** | `audit_query`, `get_status`, `schedule_cron`, `list_crons` |

---

## Variables d'Environnement

```env
# Backend
NEXUS_ENV=development
NEXUS_SECRET_KEY=your-secret-key
NEXUS_PORT=8081
NEXUS_HOST=127.0.0.1

# Frontend
NEXT_PUBLIC_NEXUS_BACKEND=http://127.0.0.1:8081

# ChromaDB
CHROMA_PERSIST_DIR=./data/chroma

# Workspace
NEXUS_WORKING_DIR=./workspace

# Providers LLM (remplissez selon vos besoins)
ZHIPUAI_API_KEY=your-zhipuai-key    # Gratuit — https://open.bigmodel.cn
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key
GOOGLE_API_KEY=your-google-key
```

---

## Technologies

| Côté | Stack |
|------|-------|
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS 4 (OKLCH), shadcn/ui, Zustand, Framer Motion |
| **3D Avatar** | Three.js, @react-three/fiber, @react-three/drei, @pixiv/three-vrm |
| **Desktop** | Tauri v2 (Rust) |
| **Backend** | FastAPI, Uvicorn, Pydantic, WebSocket, SSE |
| **LLM** | LiteLLM, OpenAI, Anthropic, Google GenAI, ZhipuAI |
| **Mémoire** | ChromaDB (vector store), NetworkX (knowledge graph) |
| **Orchestration** | LangGraph, CrewAI, Google ADK |
| **Sécurité** | Fernet (cryptography), Docker sandbox, RBAC |
| **Voix** | Silero VAD, Whisper STT, Edge TTS, VoiceVOX |
| **Browser** | Playwright |
| **Observabilité** | OpenTelemetry, Prometheus |

---

## Raccourcis Clavier

| Raccourci | Action |
|-----------|--------|
| `⌘K` / `Ctrl+K` | Ouvrir la palette de commandes |
| `⌘,` / `Ctrl+,` | Ouvrir les paramètres |
| `Enter` | Envoyer le message |
| `Shift+Enter` | Nouvelle ligne |
| `Escape` | Fermer le modal/panel actif |

---

## Licence

MIT — Utilisez, modifiez, distribuez librement.
