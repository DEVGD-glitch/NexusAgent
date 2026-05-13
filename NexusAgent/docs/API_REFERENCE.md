# 📡 Référence API Complète — NEXUSAgent

> Documentation exhaustive de tous les endpoints de l'API REST NEXUSAgent.
> Backend FastAPI sur le port 8080. Le frontend Next.js proxy via `/api/nexus/*`.

---

## 🔌 Informations générales

| Propriété | Valeur |
|-----------|--------|
| Base URL | `http://localhost:8080` |
| Protocol | HTTP/1.1 + WebSocket |
| Format | JSON |
| Auth | Bearer Token (production uniquement) |
| Rate Limit | 60 req/min par IP (configurable) |
| CORS | Autorisé pour `localhost:3000` et `localhost:8080` |
| Docs Swagger | `http://localhost:8080/docs` (développement uniquement) |
| Docs ReDoc | `http://localhost:8080/redoc` (développement uniquement) |

---

## 🔐 Authentification

En mode développement (`NEXUS_ENV=development`), l'authentification est optionnelle.
En mode production (`NEXUS_ENV=production`), un Bearer token est requis :

```http
Authorization: Bearer <NEXUS_SECRET_KEY>
```

Le token est validé via `NEXUS_SECRET_KEY` dans le fichier `.env`.

---

## 📊 Codes de statut HTTP

| Code | Signification |
|------|---------------|
| 200 | Succès |
| 400 | Requête invalide (paramètres manquants/incorrects) |
| 401 | Authentification requise (production) |
| 403 | Token invalide |
| 404 | Outil ou endpoint non trouvé |
| 429 | Rate limit dépassé |
| 500 | Erreur interne du serveur |
| 502 | Tous les providers LLM ont échoué |

---

## 💬 Chat

### POST /chat

Chat completion avec routage multi-provider LLM.

**Requête :**

```json
{
  "messages": [
    {"role": "system", "content": "Tu es NEXUS..."},
    {"role": "user", "content": "Bonjour !"}
  ],
  "provider": "gemini",
  "model": "gemini-2.5-flash",
  "temperature": 0.7,
  "max_tokens": 4096
}
```

| Champ | Type | Requis | Défaut | Description |
|-------|------|--------|--------|-------------|
| `messages` | `list[dict]` | ✅ | — | Messages de conversation `[{role, content}]` |
| `provider` | `string` | ❌ | auto | Provider explicite (voir liste ci-dessous) |
| `model` | `string` | ❌ | défaut provider | Modèle spécifique |
| `temperature` | `float` | ❌ | 0.7 | Température d'échantillonnage (0.0–2.0) |
| `max_tokens` | `int` | ❌ | 4096 | Tokens max (1–128000) |

**Providers disponibles :** `gemini`, `groq`, `openrouter`, `nvidia`, `cerebras`, `together`, `openai`, `anthropic`, `glm`, `ollama`, `pollinations`, `g4f`, `deepinfra`

**Réponse :**

```json
{
  "content": "Bonjour ! Je suis NEXUS, votre agent IA souverain...",
  "provider": "gemini",
  "model": "gemini-2.5-flash",
  "usage": {
    "prompt_tokens": 245,
    "completion_tokens": 87,
    "total_tokens": 332
  }
}
```

**Comportement :**
- Si `provider` est spécifié : utilise uniquement ce provider, retry 5 fois sur erreur transitoire
- Si `provider` est absent : routage automatique par complexité, chaîne de fallback
- Un système prompt NEXUS est injecté automatiquement si absent
- Événements diffusés en temps réel via WebSocket

---

### POST /chat/stream

Chat completion en streaming Server-Sent Events (SSE).

**Requête :** Même format que `/chat`.

**Réponse :** Flux SSE avec événements :

```
data: {"type": "token", "content": "Bonjour"}
data: {"type": "token", "content": " !"}
data: {"type": "done", "provider": "gemini", "model": "gemini-2.5-flash"}
```

---

## 🚀 Exécution de tâches

### POST /run

Exécuter une tâche complexe via l'orchestrateur Plan-Execute-Reflect (LangGraph).

**Requête :**

```json
{
  "task": "Analyse ce dataset et génère un rapport complet",
  "provider": "gemini"
}
```

| Champ | Type | Requis | Défaut | Description |
|-------|------|--------|--------|-------------|
| `task` | `string` | ✅ | — | Description de la tâche (min 1 char) |
| `provider` | `string` | ❌ | auto | Provider LLM préféré |

**Réponse :**

```json
{
  "result": "Rapport généré avec succès...",
  "status": "completed",
  "steps": 5,
  "plan": "1. Charger les données\n2. Analyser les tendances...",
  "reflection": "Tâche accomplie avec succès. Résultats cohérents.",
  "thread_id": "abc123",
  "latency_ms": 12543.2
}
```

---

## 🧠 Mémoire

### GET /memory/stats

Statistiques mémoire pour tous les namespaces.

**Réponse :**

```json
{
  "namespaces": {
    "conversations": {"count": 42},
    "episodes": {"count": 15},
    "knowledge": {"count": 128},
    "skills": {"count": 7},
    "identity": {"count": 3},
    "code": {"count": 23}
  }
}
```

---

### GET /memory/namespaces

Lister les namespaces avec leur nombre de documents.

**Réponse :**

```json
{
  "conversations": 42,
  "episodes": 15,
  "knowledge": 128,
  "skills": 7,
  "identity": 3,
  "code": 23
}
```

---

## 🔧 Outils MCP

### POST /tools/{tool_name}

Exécuter un outil MCP générique. Le corps JSON est passé comme arguments à l'outil.

**Format général :**

```http
POST /tools/{tool_name}
Content-Type: application/json

{...paramètres...}
```

### GET /tools/{tool_name}

Exécuter un outil en GET (paramètres via query string).

---

### Outils de Mémoire

#### POST /tools/search_memory

Recherche vectorielle dans la mémoire ChromaDB.

```json
{
  "query": "intelligence artificielle",
  "namespace": "knowledge",
  "top_k": 5
}
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `query` | `string` | requis | Requête de recherche |
| `namespace` | `string` | "knowledge" | Namespace à rechercher |
| `top_k` | `int` | 5 | Nombre de résultats |

**Réponse :**

```json
[
  {
    "id": "doc_abc123",
    "text": "L'intelligence artificielle est...",
    "metadata": {"source": "user"},
    "distance": 0.234
  }
]
```

#### POST /tools/store_memory

Stocker un document en mémoire vectorielle.

```json
{
  "text": "NEXUSAgent est un agent IA souverain",
  "namespace": "knowledge",
  "source": "user"
}
```

**Réponse :**

```json
{
  "doc_id": "doc_xyz789",
  "namespace": "knowledge",
  "status": "stored"
}
```

#### POST /tools/delete_memory

Supprimer un document de la mémoire.

```json
{
  "doc_id": "doc_xyz789",
  "namespace": "knowledge"
}
```

---

### Outils de Connaissances

#### POST /tools/knowledge_query

Requête sur le graphe de connaissances.

```json
{
  "entity_name": "Python",
  "depth": 1
}
```

**Réponse :**

```json
{
  "entity": {"name": "Python", "type": "language", "properties": {...}},
  "relationships": [...],
  "neighbors": [...]
}
```

#### POST /tools/knowledge_add_entity

Ajouter une entité au graphe.

```json
{
  "name": "FastAPI",
  "entity_type": "framework"
}
```

#### POST /tools/knowledge_add_relation

Ajouter une relation entre deux entités.

```json
{
  "source_name": "FastAPI",
  "target_name": "Python",
  "relation_type": "built_with"
}
```

#### POST /tools/knowledge_search

Rechercher des entités par nom.

```json
{
  "query": "Python",
  "entity_type": null,
  "limit": 20
}
```

#### POST /tools/knowledge_paths

Trouver les chemins entre deux entités.

```json
{
  "source_name": "FastAPI",
  "target_name": "HTTP",
  "max_length": 5
}
```

---

### Outils LLM

#### POST /tools/llm_complete

Completion LLM via le routeur.

```json
{
  "prompt": "Explique la programmation asynchrone",
  "model": null,
  "temperature": 0.7,
  "max_tokens": 4096
}
```

#### POST /tools/llm_list_models

Lister les modèles LLM disponibles. Aucun paramètre requis.

#### POST /tools/llm_provider_status

Statut de tous les providers LLM. Aucun paramètre requis.

#### POST /tools/llm_stream

Completion LLM en streaming.

```json
{
  "prompt": "Écris un poème",
  "model": null,
  "temperature": 0.7
}
```

---

### Outils Agents

#### POST /tools/spawn_agent

Créer un sous-agent.

```json
{
  "task": "Recherche les dernières avancées en IA",
  "agent_type": "researcher"
}
```

| `agent_type` | Description |
|-------------|-------------|
| `general` | Agent généraliste |
| `researcher` | Agent de recherche |
| `developer` | Agent développeur |
| `analyst` | Agent analyste |
| `operator` | Agent opérateur |

**Réponse :**

```json
{
  "status": "spawned",
  "instance_id": "agent_abc123",
  "agent_type": "researcher",
  "task": "Recherche les dernières avancées en IA"
}
```

#### POST /tools/list_agents

Lister les agents actifs et leurs types.

#### POST /tools/agent_status

Statut d'un agent spécifique.

```json
{
  "instance_id": "agent_abc123"
}
```

#### POST /tools/agent_delegate

Déléguer une tâche d'un agent à un autre.

```json
{
  "source_agent": "general",
  "target_agent": "researcher",
  "task": "Recherche approfondie sur X",
  "context": {}
}
```

#### POST /tools/a2a_discover

Découvrir les capacités d'un agent A2A distant.

```json
{
  "agent_url": "http://remote-agent:8080"
}
```

---

### Outils Code

#### POST /tools/execute_code

Exécuter du code dans un subprocess local.

```json
{
  "code": "print('Hello, World!')",
  "language": "python",
  "timeout": 30
}
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `code` | `string` | requis | Code à exécuter |
| `language` | `string` | "python" | Langage (python, javascript, bash) |
| `timeout` | `int` | 30 | Timeout en secondes (1–300) |

**Réponse :**

```json
{
  "stdout": "Hello, World!\n",
  "stderr": "",
  "exit_code": 0,
  "language": "python",
  "timed_out": false,
  "execution_time_ms": 45.2
}
```

#### POST /tools/execute_sandboxed

Exécuter du code Python dans un sandbox strict.

```json
{
  "code": "import os; os.listdir('/')",
  "timeout": 30,
  "max_memory_mb": 512
}
```

#### POST /tools/install_package

Installer un package Python via pip.

```json
{
  "package": "requests",
  "version": "2.31.0"
}
```

---

### Outils Fichiers

Tous les outils fichiers sont sécurisés avec protection contre le path traversal. Les chemins doivent être dans le répertoire de travail configuré (`NEXUS_WORKING_DIR`).

#### POST /tools/read_file

```json
{
  "path": "mon_fichier.txt",
  "encoding": "utf-8"
}
```

**Réponse :**

```json
{
  "path": "/app/nexus_data/mon_fichier.txt",
  "size_bytes": 1024,
  "content": "Contenu du fichier..."
}
```

#### POST /tools/write_file

```json
{
  "path": "nouveau_fichier.txt",
  "content": "Contenu à écrire",
  "encoding": "utf-8"
}
```

#### POST /tools/list_files

```json
{
  "directory": ".",
  "pattern": "*.py"
}
```

#### POST /tools/delete_file

```json
{
  "path": "fichier_a_supprimer.txt"
}
```

#### POST /tools/move_file

```json
{
  "source": "ancien_chemin.txt",
  "destination": "nouveau_chemin.txt"
}
```

#### POST /tools/copy_file

```json
{
  "source": "original.txt",
  "destination": "copie.txt"
}
```

---

### Outils Web

#### POST /tools/web_search

Recherche web multi-source.

```json
{
  "query": "NexusAgent AI",
  "num_results": 5
}
```

**Réponse :**

```json
{
  "query": "NexusAgent AI",
  "results": [
    {
      "title": "NEXUSAgent - GitHub",
      "url": "https://github.com/...",
      "snippet": "Agent IA souverain...",
      "engine": "duckduckgo"
    }
  ]
}
```

---

### Outils Raisonnement

#### POST /tools/reason_react

Raisonnement ReAct (Reason + Act).

```json
{
  "task": "Combien de mots dans la réponse ?",
  "max_iterations": 10
}
```

**Réponse :**

```json
{
  "answer": "La réponse contient 42 mots.",
  "iterations": 3,
  "reasoning_trace": ["Thought: Je dois...", "Action: search_memory...", ...]
}
```

#### POST /tools/reason_tot

Raisonnement Tree-of-Thought.

```json
{
  "task": "Résous ce problème d'optimisation",
  "max_depth": 3,
  "branch_factor": 3
}
```

#### POST /tools/reason_lats

Raisonnement LATS (Language Agent Tree Search / MCTS).

```json
{
  "task": "Planifie la meilleure stratégie",
  "max_simulations": 10,
  "max_depth": 4
}
```

---

### Outils Orchestration

#### POST /tools/run_pipeline

Exécuter un pattern Pipeline (chaîne séquentielle d'agents).

```json
{
  "main_task": "Analyse complète du projet",
  "stages_json": "[{\"agent\": \"researcher\", \"description\": \"Recherche\"}, {\"agent\": \"analyst\", \"description\": \"Analyse\"}]"
}
```

#### POST /tools/run_parallel

Exécuter un pattern Parallel (agents travaillant simultanément).

```json
{
  "main_task": "Analyse multi-angle",
  "sub_tasks_json": "[\"Analyse technique\", \"Analyse financière\", \"Analyse légale\"]"
}
```

#### POST /tools/run_supervisor

Exécuter un pattern Supervisor (agent central délègue).

```json
{
  "main_task": "Projet complet",
  "sub_tasks_json": "[\"Tâche 1\", \"Tâche 2\"]"
}
```

#### POST /tools/run_swarm

Exécuter un pattern Swarm (collectif auto-organisé).

```json
{
  "main_task": "Exploration créative",
  "num_agents": 3,
  "iterations": 2
}
```

---

### Outils Avatar

#### POST /tools/avatar_start

Démarrer l'avatar VRM. Aucun paramètre requis.

#### POST /tools/avatar_speak

Faire parler l'avatar avec VOICEVOX.

```json
{
  "text": "Bonjour, je suis NEXUS !",
  "speaker_id": 1
}
```

#### POST /tools/avatar_set_vrm

Charger un modèle VRM.

```json
{
  "vrm_path": "/path/to/avatar.vrm"
}
```

#### POST /tools/avatar_set_expression

Définir l'expression faciale de l'avatar.

```json
{
  "expression": "joy"
}
```

Expressions disponibles : `neutral`, `joy`, `angry`, `sorrow`, `fun`, `surprise`, `thinking`, `sad`

#### POST /tools/avatar_list_voices

Lister les voix VOICEVOX disponibles.

#### POST /tools/avatar_set_speaker

Définir la voix de l'avatar.

```json
{
  "speaker_id": 3
}
```

#### POST /tools/avatar_start_conversation

Démarrer le pipeline de conversation complet (VAD → STT → LLM → TTS → VRM).

---

### Outils Système

#### POST /tools/get_status

Statut complet de l'agent NEXUS.

**Réponse :**

```json
{
  "agent": "NEXUS",
  "version": "1.0.0",
  "status": "running",
  "environment": "development",
  "providers_configured": ["gemini", "pollinations", "g4f", "deepinfra", "ollama"]
}
```

#### POST /tools/audit_query

Requête sur le journal d'audit.

```json
{
  "limit": 50
}
```

---

## 📡 Endpoints directs

### GET /knowledge/query

Requête directe sur le graphe de connaissances.

**Paramètres query :**

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `entity_name` | `string` | requis | Nom de l'entité |
| `depth` | `int` | 1 | Profondeur de voisinage |

### GET /knowledge/search

Recherche d'entités dans le graphe.

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `query` | `string` | requis | Terme de recherche |
| `entity_type` | `string` | null | Filtrer par type |
| `limit` | `int` | 20 | Nombre max de résultats |

### POST /agents/spawn

Créer un agent via un endpoint dédié.

```json
{
  "task": "Analyse les données",
  "agent_type": "analyst"
}
```

### GET /agents/list

Lister tous les agents.

### POST /code/execute

Exécuter du code via un endpoint dédié.

```json
{
  "code": "print('Hello')",
  "language": "python",
  "timeout": 30,
  "sandboxed": true
}
```

### GET /status

Statut complet du système.

### GET /providers

Statut de tous les providers LLM.

**Réponse :**

```json
{
  "gemini": {
    "available": true,
    "default_model": "gemma-4-31b-it",
    "last_status": {"success": true, "latency_ms": 1200}
  },
  "pollinations": {
    "available": true,
    "default_model": "openai",
    "last_status": {}
  }
}
```

### GET /health

Health check simple.

**Réponse :**

```json
{
  "status": "healthy",
  "uptime_seconds": 86400,
  "version": "1.0.0"
}
```

### GET /config

Configuration actuelle (masque les clés API).

### POST /config

Mettre à jour la configuration à chaud.

```json
{
  "llm_default_provider": "anthropic",
  "llm_default_model": "claude-3-5-sonnet-20241022"
}
```

### GET /security/audit

Journal d'audit de sécurité.

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `limit` | `int` | 100 | Nombre max d'entrées |
| `category` | `string` | null | Filtrer par catégorie |

---

## 🌐 WebSocket

### WS /ws

Connexion WebSocket temps réel pour recevoir les événements de l'agent.

**Événements reçus :**

| Type | Description | Données |
|------|-------------|---------|
| `agent_thinking` | L'agent réfléchit | `{action, provider, message_count}` |
| `agent_action` | L'agent exécute une action | `{action, provider, model, content_length}` |
| `tool_call` | Appel d'un outil | `{tool, provider, model}` |
| `tool_result` | Résultat d'un outil | `{tool, provider, model, latency_ms, usage}` |
| `task_step` | Étape de tâche | `{task, step, provider}` |
| `task_done` | Tâche terminée | `{task, status, steps, latency_ms}` |
| `file_create` | Fichier créé | `{path, content, language}` |
| `file_edit` | Fichier modifié | `{path, content, language}` |
| `code_building` | Code en construction | `{label, detail, progress, language, code}` |
| `avatar_expression` | Expression avatar | `{expression}` |
| `error` | Erreur | `{action, error}` |
| `stream_token` | Token de streaming | `{token}` |

**Exemple JavaScript :**

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`[${data.type}]`, data.data);
};

ws.onopen = () => {
  console.log('Connecté à NEXUS WebSocket');
};
```

### GET /ws/status

Statut des connexions WebSocket actives.

---

## 🔒 Rate Limiting

Toutes les requêtes sont soumises au rate limiting :

- **Limite par défaut** : 60 requêtes par minute par IP
- **Burst** : 10 requêtes simultanées
- **Headers de réponse** : aucun (silencieux)
- **Réponse 429** : `{"detail": "Rate limit exceeded. Please wait before making more requests."}`

Configurable via `.env` :

```env
RATE_LIMIT_RPM=60
RATE_LIMIT_BURST=10
```
