# Phase 1 — App Web NEXUS Intégrée

## Résumé
Intégration complète d'une interface web moderne (Next.js 16 + React + shadcn/ui) dans NEXUS, remplaçant l'ancien prototype Tkinter comme interface principale. L'app web communique avec le backend Python via un proxy API. Le desktop Tkinter reste disponible comme alternative.

## Ce qui a été fait

### 1.1 Interface Web Moderne (Next.js 16)
- **Framework** : Next.js 16 avec App Router, TypeScript 5, Tailwind CSS 4
- **Composants UI** : shadcn/ui (50+ composants pré-installés)
- **Design** : Thème sombre (zinc-950), accent émeraude (#10b981), responsive mobile+desktop
- **Structure** : Sidebar avec navigation, 10 onglets fonctionnels, barre de statut
- **Langue** : Interface entièrement en français

### 1.2 10 Panneaux Fonctionnels

| Panneau | Fonctionnalité | Description |
|---------|---------------|-------------|
| **Chat** | Chat multi-LLM | Markdown, copie, typing animation, streaming WebSocket, badges provider/model |
| **Tasks** | Exécution de tâches | Plan-Execute-Reflect avec affichage du plan et de la réflexion |
| **Memory** | Mémoire vectorielle | Recherche/stockage dans 6 namespaces ChromaDB |
| **Knowledge** | Knowledge Graph | Query, search, add entities/relations, paths |
| **Agents** | Agents + orchestration | Spawn agents, pipeline/parallel/supervisor/swarm |
| **Tools** | Navigateur d'outils MCP | 46+ outils organisés par catégorie (10 catégories) |
| **Code** | Éditeur de code | Exécution sandboxed (5 langages), sortie stdout/stderr |
| **Security** | Sécurité + audit | Audit log, mode de permissions, guardrails |
| **Status** | Dashboard système | Statut, providers, uptime, auto-refresh 10s |
| **Settings** | Configuration complète | API keys, providers, permissions, export/import JSON |

### 1.3 Onboarding Wizard (4 étapes)
1. **Bienvenue** — Présentation de NEXUS et ses fonctionnalités
2. **Fournisseurs** — Choix des providers LLM (Ollama coché par défaut)
3. **Clés API** — Saisie des clés pour les providers sélectionnés
4. **Lancement** — Confirmation et démarrage

### 1.4 Système de Permissions (Toasts)
- **Auto-approuve** : Flux libre, confirmation uniquement pour les actions dangereuses
- **Confirmation** : Toute action importante demande confirmation
- **Actions dangereuses** : `delete_file`, `execute_code`, `write_file`, `install_package`, etc.
- **Chemins système** : `C:\Windows`, `Program Files` → toujours confirmation
- **Toast UI** : Notification en bas à droite avec bouton Approuver/Refuser

### 1.5 WebSocket Streaming
- **Service** : `mini-services/nexus-ws/` sur port 3003
- **Protocole** : `chat` → `stream chunks` → `stream_end`
- **Hook React** : `use-nexus-ws.ts` avec reconnexion exponentielle
- **Heartbeat** : Ping/pong toutes les 30s
- **Fallback** : Si WebSocket indisponible, bascule sur REST API

### 1.6 Scripts de Lancement
- **`start_web.bat`** : Lance backend + frontend dans des terminaux séparés
  - Vérifie Python + Node.js
  - Installe les dépendances si nécessaire
  - Ouvre 2 terminaux (backend :8080 + frontend :3000)
  - Ouvre le navigateur automatiquement
- **`install_build.bat`** : Installation complète + build Windows .exe
- **`start_nexus.bat`** : Backend uniquement

## Architecture Frontend

```
nexus-web/src/
├── app/
│   ├── api/nexus/[...path]/route.ts  → Proxy vers backend:8080
│   ├── globals.css                    → Thème dark custom
│   ├── layout.tsx                     → Layout NEXUS (FR, dark)
│   └── page.tsx                       → App principale (sidebar + panels)
├── components/
│   ├── nexus/
│   │   ├── chat-panel.tsx             → Chat avec markdown + streaming
│   │   ├── tasks-panel.tsx            → Exécution de tâches
│   │   ├── memory-panel.tsx           → Mémoire vectorielle
│   │   ├── knowledge-panel.tsx        → Knowledge Graph
│   │   ├── agents-panel.tsx           → Agents + orchestration
│   │   ├── tools-panel.tsx            → Navigateur d'outils MCP
│   │   ├── code-panel.tsx             → Éditeur de code
│   │   ├── security-panel.tsx         → Sécurité + audit
│   │   ├── status-panel.tsx           → Dashboard système
│   │   ├── settings-panel.tsx         → Configuration complète
│   │   ├── onboarding.tsx             → Wizard d'accueil
│   │   └── toast-container.tsx        → Notifications + permissions
│   └── ui/                            → 50+ composants shadcn/ui
├── hooks/
│   ├── use-nexus-ws.ts               → Hook WebSocket streaming
│   ├── use-toast.ts                   → Notifications
│   └── use-mobile.ts                  → Responsive mobile
└── lib/
    ├── nexus-api.ts                   → Client API (REST + permissions)
    ├── nexus-store.ts                 → State management Zustand
    ├── utils.ts                       → Utilitaires (cn, etc.)
    └── db.ts                          → Prisma (si besoin)
```

## API Gateway (Backend)

Le backend expose 22+ endpoints via `nexus/api/gateway.py` :

| Catégorie | Endpoints | Description |
|-----------|-----------|-------------|
| Chat | `POST /chat` | Chat completion multi-LLM |
| Tasks | `POST /run` | Plan-Execute-Reflect |
| Memory | `GET /memory/stats`, `GET /memory/namespaces` | Statistiques mémoire |
| Tools | `POST /tools/{name}`, `GET /tools/{name}` | 28 outils MCP via API |
| Knowledge | `GET /knowledge/query`, `GET /knowledge/search` | Knowledge Graph |
| Agents | `POST /agents/spawn`, `GET /agents/list` | Gestion des agents |
| Code | `POST /code/execute` | Exécution sandboxed |
| System | `GET /status`, `GET /providers`, `GET /health`, `GET/POST /config` | Status système |

### Design du Backend

- **Lazy imports** : ChromaDB, NetworkX, LLM chargés uniquement à l'utilisation
- **Windows-compatible** : Pas de module `resource`, pas de signaux Unix
- **Pas de fallback silencieux** : Si un provider échoue, l'erreur est retournée au frontend pour toast
- **Audit léger** : Chaque action est journalisée
- **CORS activé** : Pour le frontend Next.js

## Fichiers Clés

| Fichier | Rôle |
|---------|------|
| `src/app/page.tsx` | Point d'entrée, sidebar, routing |
| `src/lib/nexus-store.ts` | Store Zustand global (navigation, chat, memory, settings, toasts) |
| `src/lib/nexus-api.ts` | Client API avec permission gating |
| `src/app/api/nexus/[...path]/route.ts` | Proxy vers backend Python |
| `nexus/api/gateway.py` | Gateway FastAPI complet (22+ endpoints) |
| `run_nexus.py` | Lanceur backend avec argparse |
| `start_web.bat` | Lancement app web (multi-terminales) |
