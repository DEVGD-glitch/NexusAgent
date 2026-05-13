# 🏗️ Architecture — NEXUSAgent

> Documentation détaillée de l'architecture, des modules et des flux de données de NEXUSAgent.

---

## Vue d'ensemble

NEXUSAgent est un agent IA souverain de classe production, organisé en architecture 3-tier :

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Electron App │────▶│  Next.js 16  │────▶│  FastAPI GW  │
│  (Bureau)     │     │  (Frontend)  │     │  (Backend)   │
│  Port: libre  │     │  Port: 3000  │     │  Port: 8080  │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                  │
                                    ┌─────────────┼──────────────┐
                                    │             │              │
                              ┌─────▼─────┐ ┌────▼─────┐ ┌─────▼──────┐
                              │ LLM Router │ │ MCP Tools│ │  Sécurité  │
                              │ 13 prov.   │ │ 43+      │ │ Vault/Grd  │
                              └───────────┘ └──────────┘ └────────────┘
```

---

## Modules du Backend (`nexus/`)

### 📦 `nexus/core/` — Noyau et Infrastructure

Le module central qui fournit les fondations partagées par tous les autres modules.

| Fichier | Rôle | Description |
|---------|------|-------------|
| `config.py` | Configuration | Pydantic Settings, lecture .env, validation, propriétés dérivées |
| `di.py` | Injection de dépendances | Conteneur DI pour les services partagés |
| `gateway.py` | Passerelle principale | Logique de routage interne des requêtes |
| `registry.py` | Registre d'agents | Enregistrement, spawning et suivi des agents |
| `a2a.py` | Agent-to-Agent | Protocole de communication inter-agents standardisé |
| `events.py` | Événements | EventBroadcaster pour WebSocket temps réel |
| `exceptions.py` | Exceptions | Hiérarchie d'exceptions typées (LLMError, AgentError, MCPToolError...) |
| `observability.py` | Observabilité | Intégration OpenTelemetry |
| `telemetry.py` | Télémétrie | Collecte de métriques d'utilisation |
| `evaluation.py` | Évaluation | Métriques de qualité des réponses |
| `resource_manager.py` | Ressources | Gestion des ressources système (mémoire, CPU) |
| `supervisor.py` | Superviseur | Supervision des processus et agents |
| `error_messages.py` | Messages d'erreur | Messages d'erreur humains en français |

**Flux de configuration :**
```
.env → NexusConfig (Pydantic Settings) → get_settings() [LRU cache singleton]
                                         → available_providers (propriété dérivée)
                                         → fallback_providers (propriété dérivée)
```

---

### 🧠 `nexus/llm/` — Routeur Multi-LLM

Système de routage intelligent avec fallback automatique entre 13 providers.

| Fichier | Rôle |
|---------|------|
| `router.py` | Routeur principal — sélection de provider, fallback, retry, streaming |
| `fallback.py` | Logique de chaîne de fallback |
| `providers/openai_provider.py` | Provider OpenAI (GPT-4o, o1, o3) |
| `providers/anthropic_provider.py` | Provider Anthropic (Claude 3.5/4) |
| `providers/gemini_provider.py` | Provider Google (Gemini 2.5, Gemma 4) |
| `providers/glm_provider.py` | Provider GLM/ZAI (GLM-4/5) |
| `providers/ollama_provider.py` | Provider Ollama (modèles locaux) |
| `providers/free/pollinations_provider.py` | Provider gratuit Pollinations.ai |
| `providers/free/g4f_provider.py` | Provider gratuit G4F.dev |
| `providers/free/deepinfra_provider.py` | Provider gratuit DeepInfra |
| `providers/free/free_router.py` | Routeur des providers gratuits |

**Routage par complexité :**

```
SIMPLE  → Pollinations → G4F → DeepInfra → Groq → Cerebras → Gemini → OpenAI
MEDIUM  → Gemini → Groq → OpenRouter → NVIDIA → Cerebras → OpenAI → Anthropic
COMPLEX → Gemini → OpenRouter → NVIDIA → Anthropic → OpenAI → GLM
```

**Modes de fonctionnement :**
- **Mode Provider Unique** : quand `provider` est spécifié, pas de fallback, retry 5x avec backoff exponentiel
- **Mode Auto-Routing** : sélection par complexité, fallback vers le provider suivant en cas d'échec

---

### 🗃️ `nexus/memory/` — Mémoire 5 Niveaux

Système de mémoire hiérarchique persistante basé sur ChromaDB.

| Fichier | Niveau | Description |
|---------|--------|-------------|
| `working.py` | L1 — Working | Mémoire de session, compression automatique au seuil de tokens |
| `episodic.py` | L2 — Episodic | Journal d'expériences vécues par l'agent |
| `semantic.py` | L3 — Semantic | Faits et connaissances structurés |
| `procedural.py` | L4 — Procedural | Compétences cristallisées et automatisées |
| `identity.py` | L5 — Identity | Profil utilisateur, préférences, personnalité |
| `chroma_service.py` | — | Service ChromaDB unifié (CRUD, recherche vectorielle) |
| `compactor.py` | — | Compaction et résumé automatique des mémoires |
| `orchestrator.py` | — | Orchestrateur de mémoire — décide quel niveau utiliser |

**Flux de stockage :**
```
Input → MemoryOrchestrator → Identification du type
  → Working (si session) → Compression si seuil dépassé
  → Episodic (si expérience) → Horodatage + contexte
  → Semantic (si fait) → Extraction d'entités → ChromaDB
  → Procedural (si compétence) → Cristallisation
  → Identity (si préférence) → Mise à jour profil
```

**Flux de recherche :**
```
Query → MemoryOrchestrator → Recherche multi-niveaux
  → ChromaDB vector search (cosine similarity)
  → Fusion et classement par pertinence
  → Retour des top-k résultats
```

---

### 🎯 `nexus/orchestrator/` — Orchestration Multi-Agents

Système d'orchestration avec 3 moteurs et 6 patterns.

| Fichier | Rôle |
|---------|------|
| `langgraph_engine.py` | Moteur LangGraph — cycle Plan-Execute-Reflect |
| `crewai_engine.py` | Moteur CrewAI — collaboration multi-agents |
| `adk_engine.py` | Moteur Google ADK — Agents Development Kit |
| `patterns.py` | 6 patterns d'orchestration (Pipeline, Parallel, Supervisor, Swarm, Routing, Skills) |
| `router.py` | Routeur d'orchestration — sélection du moteur approprié |
| `skill_lifecycle.py` | Gestion du cycle de vie des compétences |

**Patterns d'orchestration :**

```
Pipeline   : [Agent1] → [Agent2] → [Agent3]     (séquentiel)
Parallel   : [Agent1] ─┐                          (simultané)
             [Agent2] ─┤→ [Fusion]
             [Agent3] ─┘
Supervisor : [Supervisor] → [Worker1], [Worker2]  (délégation centralisée)
Swarm      : [Agent1] ↔ [Agent2] ↔ [Agent3]      (auto-organisation)
Routing    : [Router] → Agent sélectionné          (routage par type)
Skills     : [Skill1] → [Skill2] → [Skill3]       (cycle de vie)
```

---

### 🤖 `nexus/agents/` — Agents Spécialisés

Cinq types d'agents avec une base abstraite commune.

| Fichier | Type | Spécialité |
|---------|------|-----------|
| `base.py` | BaseAgent | Classe abstraite — cycle de vie complet, accès services |
| `researcher.py` | Researcher | Recherche web, deep research, synthèse |
| `developer.py` | Developer | Code, refactoring, tests, déploiement |
| `analyst.py` | Analyst | Analyse de données, rapports, visualisation |
| `operator.py` | Operator | Opérations système, automatisation |
| `openai_layer.py` | Compatibilité | Couche OpenAI Agents SDK |

**Cycle de vie d'un agent :**

```
initialize → plan → [execute_step → reflect]* → finalize → AgentResult
                              ↓                        ↑
                         _call_llm()           should_continue?
                              ↓
                        tool_calls? ──→ _use_tool() ──→ result → prochain tour
```

**Accès aux services (lazy-initialized) :**
- `self.llm_router` : Routeur LLM
- `self.memory` : Service ChromaDB
- `self.security` : Guardrails
- `self.mcp_client` : Serveur MCP (43+ outils)
- `self.audit_logger` : Journal d'audit

---

### 💡 `nexus/reasoning/` — Raisonnement Structuré

Trois modes de raisonnement avancé.

| Fichier | Mode | Description |
|---------|------|-------------|
| `react.py` | ReAct | Reason + Act — boucle de pensée-action-observation |
| `tot.py` | Tree-of-Thought | Exploration arborescente de solutions alternatives |
| `lats.py` | LATS/MCTS | Monte Carlo Tree Search — recherche arborescente avec simulations |
| `selector.py` | Sélecteur | Choix automatique du mode de raisonnement |

**ReAct :**
```
Thought → Action → Observation → Thought → Action → ... → Answer
```

**Tree-of-Thought :**
```
           ┌─ Branche A → Score: 0.8
Root ──────┼─ Branche B → Score: 0.9 ← meilleur
           └─ Branche C → Score: 0.5
```

**LATS (MCTS) :**
```
Selection → Expansion → Simulation → Backpropagation → Repeat
```

---

### 🔧 `nexus/mcp_tools/` — Outils MCP (43+)

Outils organisés en 12 catégories, servis via le protocole MCP (FastMCP).

| Fichier | Catégorie | Outils |
|---------|-----------|--------|
| `memory_tools.py` | Mémoire | search_memory, store_memory, delete_memory, list_namespaces, memory_stats |
| `knowledge_tools.py` | Connaissances | knowledge_query, knowledge_add_entity, knowledge_add_relation, knowledge_search, knowledge_paths |
| `llm_tools.py` | LLM | llm_complete, llm_stream, llm_list_models, llm_provider_status |
| `agent_tools.py` | Agents | spawn_agent, list_agents, agent_status, agent_delegate, a2a_discover |
| `code_tools.py` | Code | execute_code, execute_sandboxed, install_package |
| `file_tools.py` | Fichiers | read_file, write_file, list_files, delete_file, move_file, copy_file, search_files |
| `web_tools.py` | Web | web_search, web_scrape, web_screenshot |
| `reasoning_tools.py` | Raisonnement | reason_react, reason_tot, reason_lats |
| `orchestration_tools.py` | Orchestration | run_pipeline, run_parallel, run_supervisor, run_swarm |
| `system_tools.py` | Système | get_status, get_config, health_check |
| `bonus_tools.py` | Bonus | audit_query, rate_limit_status, deep_research, rag_query |
| `avatar_tools.py` | Avatar | avatar_start, avatar_speak, avatar_set_vrm, avatar_set_expression, avatar_list_voices, avatar_set_speaker, avatar_start_conversation, avatar_expression_from_text |
| `context7.py` | Context7 | Intégration Context7 pour documentation technique |

**Architecture MCP :**
```
FastMCP Server (nexus_mcp_server.py)
  ├── @nexus_mcp.tool() → Exposition HTTP
  ├── @nexus_mcp.resource() → Ressources (config, status, tools list)
  ├── @nexus_mcp.prompt() → Templates (research_task, code_task, analysis_task)
  └── Handlers → mcp_tools/* (implémentation modulaire)
```

---

### 🛡️ `nexus/security/` — Sécurité

Système de sécurité en profondeur avec audit complet.

| Fichier | Rôle |
|---------|------|
| `vault.py` | Vault chiffré — stockage sécurisé des secrets (Fernet) |
| `guardrails.py` | Guardrails — protection contre les injections de prompt |
| `sandbox.py` | Sandbox local — exécution isolée de code avec limites ressources |
| `rate_limiter.py` | Rate Limiter — limitation par IP et par action (token bucket) |
| `permissions.py` | Permissions — système de permissions par action |
| `secrets.py` | Secrets — gestionnaire de secrets d'environnement |
| `audit.py` | Audit Trail — journalisation complète avec catégories et niveaux |
| `docker/per_action_sandbox.py` | Sandbox Docker — isolation par action dans un conteneur |

**Niveaux d'audit :**
```
DEBUG → INFO → WARNING → ERROR → CRITICAL
```

**Catégories d'audit :**
```
AGENT_ACTION │ TOOL_CALL │ SECURITY_EVENT │ DATA_ACCESS │ SYSTEM_EVENT
```

---

### 🔗 `nexus/knowledge/` — Connaissances

Graphe de connaissances, RAG et recherche approfondie.

| Fichier | Rôle |
|---------|------|
| `knowledge_graph.py` | Graphe de connaissances NetworkX (entités, relations, chemins, recherche) |
| `rag_pipeline.py` | Pipeline RAG — Retrieval Augmented Generation |
| `deep_research.py` | Recherche approfondie multi-sources |
| `web_search.py` | Recherche web multi-moteur |
| `watchdog.py` | Surveillance de fichiers pour mise à jour automatique |

**Pipeline RAG :**
```
Query → Vector Search (ChromaDB) → Context Retrieval → LLM Generation → Response
```

**Deep Research :**
```
Topic → Multi-source Search → Content Extraction → Analysis → Synthesis → Report
```

---

### 💻 `nexus/dev/` — Outils Développeur

| Fichier | Rôle |
|---------|------|
| `code_executor.py` | Exécution de code (local subprocess) |
| `code_engine.py` | Moteur de code — génération, review, refactoring |
| `terminal.py` | Terminal autonome avec sécurité |
| `git_integration.py` | Intégration Git — commits, PRs, review |
| `deploy.py` | Déploiement automatisé |

---

### 🖥️ `nexus/computer/` — Computer Use

| Fichier | Rôle |
|---------|------|
| `computer_use.py` | Interface Computer Use principale |
| `gui_control.py` | Contrôle GUI via pyautogui |
| `screen_understanding.py` | Compréhension d'écran (OCR, vision) |
| `process_manager.py` | Gestionnaire de processus système |

---

### 💬 `nexus/comms/` — Communications

| Fichier | Rôle |
|---------|------|
| `channels.py` | Canaux de communication multi-protocoles |
| `telegram_bot.py` | Bot Telegram |
| `voice_io.py` | Entrée/sortie vocale (STT/TTS) |
| `email_calendar.py` | Intégration email et calendrier |
| `avatar/` | Sous-module Avatar VRM |

**Avatar VRM :**

| Fichier | Rôle |
|---------|------|
| `avatar_manager.py` | Gestionnaire d'avatar principal |
| `face_controller.py` | Contrôleur d'expressions faciales |
| `lip_sync.py` | Synchronisation labiale audio → visèmes |
| `voicevox_bridge.py` | Pont VOICEVOX (100+ voix japonaises) |
| `vrm_renderer.py` | Rendu de modèles VRM |

---

### 🌐 `nexus/browser/` — Navigateur Automatisé

| Fichier | Rôle |
|---------|------|
| `browser_service.py` | Service de navigateur HTTP |
| `playwright_ext.py` | Extension Playwright pour automatisation |

---

### 📡 `nexus/api/` — API Gateway

| Fichier | Rôle |
|---------|------|
| `gateway.py` | Gateway FastAPI — tous les endpoints REST + WebSocket |
| `puter_proxy.py` | Proxy Puter.js pour services cloud |

---

### 🖥️ `nexus/cli/` — Interface CLI

| Fichier | Rôle |
|---------|------|
| `app.py` | Application CLI Typer avec commandes `serve`, `chat`, etc. |

---

## 🎨 Frontend (`nexus-web/`)

Application Next.js 16 avec React 19, shadcn/ui et Zustand.

### Architecture Frontend

```
nexus-web/
├── src/
│   ├── app/
│   │   ├── page.tsx              # Page principale (dashboard)
│   │   ├── layout.tsx            # Layout racine
│   │   ├── globals.css           # Styles globaux + Tailwind
│   │   └── api/nexus/[...path]/  # Proxy API vers backend
│   ├── components/
│   │   ├── nexus/                # Composants métier
│   │   │   ├── chat-panel.tsx    # Panel de chat
│   │   │   ├── memory-panel.tsx  # Panel mémoire
│   │   │   ├── knowledge-panel.tsx # Panel connaissances
│   │   │   ├── agents-panel.tsx  # Panel agents
│   │   │   ├── tools-panel.tsx   # Panel outils
│   │   │   ├── code-panel.tsx    # Panel code
│   │   │   ├── security-panel.tsx # Panel sécurité
│   │   │   ├── settings-panel.tsx # Panel paramètres
│   │   │   ├── sidebar.tsx       # Navigation latérale
│   │   │   └── avatar.tsx        # Avatar 3D
│   │   └── ui/                   # 40+ composants shadcn/ui
│   ├── hooks/
│   │   └── use-nexus-ws.ts      # Hook WebSocket temps réel
│   ├── lib/
│   │   ├── nexus-api.ts         # Client API backend
│   │   ├── nexus-store.ts       # Store Zustand (état global)
│   │   └── utils.ts             # Utilitaires
│   └── types/
│       └── nexus.ts             # Types TypeScript
```

### Flux de données Frontend

```
User Action → Zustand Store → API Client → Backend (port 8080)
                                      ↓
                              WebSocket Events
                                      ↓
                              useNexusWebSocket Hook
                                      ↓
                              Zustand Store Update → React Re-render
```

### WebSocket Events Handling

Le hook `useNexusWebSocket` traite les événements en temps réel :

```
agent_thinking → setAgentStatus("thinking") + setAvatarExpression("thinking")
agent_action   → setAgentStatus("working")  + addActivity()
tool_call      → addActivity()
tool_result    → addActivity()
task_step      → addActivity()
task_done      → setAgentStatus("idle") + setAvatarExpression("joy")
error          → setAgentStatus("idle") + setAvatarExpression("sad")
file_create    → addBuildStep() + setAvatarExpression("joy")
code_building  → addBuildStep() (brick-by-brick visualization)
avatar_expression → setAvatarExpression()
```

---

## 🖥️ Application Bureau (`nexus-desktop/`)

Application Electron qui encapsule le frontend web.

```javascript
// main.js — Electron main process
// - Charge le frontend Next.js (localhost:3000 ou build statique)
// - Packagé avec electron-builder
// - Distribué comme installateur NSIS (Windows), DMG (macOS), AppImage (Linux)
```

---

## 🐳 Architecture Docker

```yaml
Services:
  nexus-core:         # Backend FastAPI
    depends_on: [chromadb]
    volumes: [nexus-data]
    
  chromadb:           # Base vectorielle
    image: chromadb/chroma:1.15.3
    volumes: [chroma-data]
    
  browser-service:    # Service navigateur isolé
    # Environnement séparé avec browser-use
```

---

## 🔄 Flux de données principaux

### Chat Completion

```
Frontend → POST /chat → Gateway → LLMRouter
  → Select Provider → Call Provider (LiteLLM/Direct)
  → Response → Broadcast WS Events → Frontend Update
```

### Task Execution

```
Frontend → POST /run → Gateway → LangGraph Engine
  → Plan → Execute Steps → Reflect
  → Each Step: LLM Call → Tool Use → Result
  → Final Result → Broadcast → Frontend
```

### Tool Execution

```
Frontend → POST /tools/{name} → Gateway → TOOL_HANDLERS[name]
  → Execute Tool → Return Result → Audit Log
```

### Memory Operations

```
Tool Call → MemoryOrchestrator → Identify Level
  → L1 (Working): In-memory + ChromaDB
  → L2-L5: ChromaDB persistent
  → Search: Vector similarity (cosine) → Top-K results
```

---

## 📈 Métriques et Observabilité

- **OpenTelemetry** : traces distribuées pour les appels LLM
- **Langfuse** : évaluation et monitoring des réponses LLM
- **Audit Trail** : journalisation complète de toutes les actions
- **Rate Limiter** : métriques de consommation par IP
- **Provider Status** : suivi de santé et latence par provider
