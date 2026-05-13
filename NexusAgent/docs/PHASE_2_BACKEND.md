# Phase 2 — Backend FastAPI Gateway

## Résumé
Création du backend FastAPI complet qui expose toutes les capacités NEXUS via une API REST que le frontend Next.js peut appeler. Le frontend proxie toutes les requêtes `/api/nexus/*` vers `http://localhost:8080/*`.

## Ce qui a été fait

### 2.1 Gateway API (22+ endpoints)

| Catégorie | Endpoint | Méthode | Description |
|-----------|----------|---------|-------------|
| **Chat** | `/chat` | POST | Complétion LLM avec provider explicite |
| **Tâches** | `/run` | POST | Exécution via Plan-Execute-Reflect |
| **Mémoire** | `/memory/stats` | GET | Statistiques mémoire |
| **Mémoire** | `/memory/namespaces` | GET | Liste des namespaces |
| **Outils** | `/tools/{tool_name}` | POST | Exécution d'outil MCP (28 outils) |
| **Outils** | `/tools/search_memory` | GET | Recherche mémoire |
| **Outils** | `/tools/{tool_name}` | GET | Outil via query params |
| **Knowledge** | `/knowledge/query` | GET | Query Knowledge Graph |
| **Knowledge** | `/knowledge/search` | GET | Recherche d'entités |
| **Agents** | `/agents/spawn` | POST | Créer un sous-agent |
| **Agents** | `/agents/list` | GET | Lister les agents |
| **Code** | `/code/execute` | POST | Exécuter du code |
| **Système** | `/status` | GET | Statut complet |
| **Système** | `/providers` | GET | Statut des providers LLM |
| **Système** | `/health` | GET | Health check |
| **Système** | `/config` | GET | Configuration (non-sensible) |
| **Système** | `/config` | POST | Mise à jour config runtime |
| **Sécurité** | `/security/audit` | GET | Audit log |

### 2.2 28 Outils MCP Disponibles via API

Mémoire (3) : search_memory, store_memory, delete_memory
Knowledge (5) : knowledge_query, knowledge_add_entity, knowledge_search, knowledge_paths, knowledge_add_relation
Agents (2) : spawn_agent, list_agents
Code (3) : execute_code, execute_sandboxed, install_package
Fichiers (7) : read_file, write_file, list_files, delete_file, move_file, copy_file
Web (1) : web_search
Raisonnement (2) : reason_react, reason_tot
Orchestration (4) : run_pipeline, run_parallel, run_supervisor, run_swarm
Système (2) : audit_query, get_status

### 2.3 Principes de Design

- **Imports lazy** : ChromaDB, NetworkX, etc. chargés uniquement à la première requête
- **Compatible Windows** : Pas de module `resource`, pas de signaux Unix
- **Provider explicite** : Pas de fallback silencieux, les erreurs remontent au frontend
- **Audit léger** : Chaque action est loguée, ne bloque jamais l'API
- **Messages lisibles** : Erreurs techniques transformées en messages humains
- **CORS activé** : Pour le frontend Next.js

### 2.4 Scripts de Lancement Windows

- `run_nexus.py` — Lanceur Python avec args (--host, --port, --reload)
- `start_nexus.bat` — Vérifie Python → installe deps → crée .env → lance backend
- `start_web.bat` — Vérifie Node.js → installe deps → lance frontend Next.js

### 2.5 Fichier .env Auto-généré

Le script `start_nexus.bat` crée automatiquement un `.env` avec :
- NEXUS_ENV=development
- NEXUS_PORT=8080
- Clés API commentées (OpenAI, Anthropic, Google, ZAI)
- Ollama URL par défaut

## Architecture Backend

```
nexus/
├── api/
│   ├── __init__.py        → Exporte l'app FastAPI
│   └── gateway.py         → 22+ endpoints REST
├── llm/router.py          → Routeur multi-LLM (5 providers)
├── memory/chroma_service.py → Mémoire vectorielle ChromaDB
├── knowledge/knowledge_graph.py → Knowledge Graph (NetworkX)
├── orchestrator/langgraph_engine.py → Plan-Execute-Reflect
├── dev/code_executor.py   → Exécution de code multi-langage
├── security/sandbox.py    → Sandbox local (Windows-compatible)
├── security/audit.py      → Audit logging
├── core/config.py         → Configuration pydantic-settings
└── core/registry.py       → Registre d'agents

run_nexus.py               → Lanceur backend
start_nexus.bat            → Script Windows backend
start_web.bat              → Script Windows frontend
```

## Démarrage sur Windows

```batch
# Terminal 1 : Backend
start_nexus.bat

# Terminal 2 : Frontend
start_web.bat
```

Ou manuellement :
```batch
# Backend
python run_nexus.py --port 8080

# Frontend
cd nexus-web && npm run dev
```
