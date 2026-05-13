# ⚙️ Configuration — NEXUSAgent

> Documentation complète de toutes les options de configuration, variables d'environnement et setup des providers.

---

## 📁 Fichier de configuration

NEXUSAgent utilise **Pydantic Settings** pour la configuration. Toutes les variables sont lues depuis le fichier `.env` et/ou les variables d'environnement système.

### Hiérarchie de chargement

```
1. Variables d'environnement système (priorité maximale)
2. Fichier .env à la racine du projet
3. Valeurs par défaut définies dans NexusConfig
```

### Création du fichier .env

```bash
# Copier le template
cp .env.example .env

# Éditer avec vos valeurs
nano .env        # Linux/macOS
notepad .env     # Windows
```

---

## 🔧 Variables de configuration complètes

### Environnement

| Variable | Type | Défaut | Description |
|----------|------|--------|-------------|
| `NEXUS_ENV` | `enum` | `development` | Environnement d'exécution (`development`, `staging`, `production`) |
| `NEXUS_LOG_LEVEL` | `enum` | `INFO` | Niveau de log (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `NEXUS_SECRET_KEY` | `string` | `change-me-to-a-secure-random-string` | Clé secrète pour l'authentification en production |
| `NEXUS_HOST` | `string` | `0.0.0.0` | Adresse d'écoute du serveur |
| `NEXUS_PORT` | `int` | `8080` | Port d'écoute du serveur (1–65535) |
| `NEXUS_WORKING_DIR` | `string` | `./nexus_data` | Répertoire de travail pour les fichiers |

> ⚠️ **Production** : `NEXUS_SECRET_KEY` doit être changé ! Générer une clé avec :
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

---

### Clés API — Providers LLM

| Variable | Provider | Obligatoire | Obtenir |
|----------|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI | ❌ | https://platform.openai.com/api-keys |
| `ANTHROPIC_API_KEY` | Anthropic | ❌ | https://console.anthropic.com |
| `GOOGLE_API_KEY` | Google Gemini | ❌ | https://aistudio.google.com |
| `ZAI_API_KEY` | GLM / Zhipu | ❌ | https://open.bigmodel.cn |
| `ZAI_BASE_URL` | GLM / Zhipu | ❌ | `https://open.bigmodel.cn/api/paas/v4` |
| `GROQ_API_KEY` | Groq | ❌ | https://console.groq.com |
| `OPENROUTER_API_KEY` | OpenRouter | ❌ | https://openrouter.ai |
| `NVIDIA_API_KEY` | NVIDIA | ❌ | https://build.nvidia.com |
| `CEREBRAS_API_KEY` | Cerebras | ❌ | https://cloud.cerebras.ai |
| `TOGETHER_API_KEY` | Together AI | ❌ | https://api.together.xyz |

> 🆓 **Aucune clé API n'est obligatoire !** Les 3 providers gratuits (Pollinations, G4F, DeepInfra) fonctionnent sans clé.

---

### Ollama (LLM Local)

| Variable | Type | Défaut | Description |
|----------|------|--------|-------------|
| `OLLAMA_BASE_URL` | `string` | `http://127.0.0.1:11434` | URL du serveur Ollama |
| `OLLAMA_DEFAULT_MODEL` | `string` | `llama3.1:8b` | Modèle par défaut |

**Installation d'Ollama :**

```bash
# Linux/macOS
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1:8b

# Windows
# Télécharger depuis https://ollama.com/download/windows
ollama pull llama3.1:8b
```

---

### ChromaDB (Mémoire Vectorielle)

| Variable | Type | Défaut | Description |
|----------|------|--------|-------------|
| `CHROMA_PERSIST_DIR` | `string` | `./nexus_data/chroma` | Répertoire de persistance ChromaDB |
| `CHROMA_HOST` | `string` | `localhost` | Hôte ChromaDB (mode serveur) |
| `CHROMA_PORT` | `int` | `8000` | Port ChromaDB (mode serveur) |

**Modes de fonctionnement :**
- **Mode embarqué** (par défaut) : ChromaDB tourne dans le processus Python, données persistées dans `CHROMA_PERSIST_DIR`
- **Mode serveur** : ChromaDB tourne dans un conteneur Docker séparé, connexion via `CHROMA_HOST`:`CHROMA_PORT`

---

### Service Navigateur

| Variable | Type | Défaut | Description |
|----------|------|--------|-------------|
| `BROWSER_SERVICE_URL` | `string` | `http://localhost:8001` | URL du service navigateur |
| `BROWSER_SERVICE_ENABLED` | `bool` | `true` | Activer/désactiver le service navigateur |

---

### Sécurité

| Variable | Type | Défaut | Description |
|----------|------|--------|-------------|
| `RATE_LIMIT_RPM` | `int` | `60` | Requêtes par minute par IP |
| `RATE_LIMIT_BURST` | `int` | `10` | Burst autorisé (requêtes simultanées) |
| `SANDBOX_ENABLED` | `bool` | `true` | Activer le sandbox de code |
| `SANDBOX_DOCKER_IMAGE` | `string` | `nexus-sandbox:latest` | Image Docker pour le sandbox par action |
| `AUDIT_LOG_DIR` | `string` | `./nexus_data/audit` | Répertoire des logs d'audit |

---

### Bot Telegram

| Variable | Type | Défaut | Description |
|----------|------|--------|-------------|
| `TELEGRAM_BOT_TOKEN` | `string` | None | Token du bot Telegram |
| `TELEGRAM_CHAT_ID` | `string` | None | ID du chat Telegram |

---

### Recherche Web

| Variable | Type | Défaut | Description |
|----------|------|--------|-------------|
| `SERPAPI_KEY` | `string` | None | Clé SerpAPI pour recherche web |
| `BRAVE_SEARCH_KEY` | `string` | None | Clé Brave Search |

> 💡 La recherche web fonctionne aussi sans clé via DuckDuckGo (par défaut).

---

### Observabilité

| Variable | Type | Défaut | Description |
|----------|------|--------|-------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `string` | None | Endpoint OpenTelemetry pour traces |
| `LANGFUSE_PUBLIC_KEY` | `string` | None | Clé publique Langfuse |
| `LANGFUSE_SECRET_KEY` | `string` | None | Clé secrète Langfuse |

---

### Context7

| Variable | Type | Défaut | Description |
|----------|------|--------|-------------|
| `CONTEXT7_API_KEY` | `string` | None | Clé API Context7 pour documentation technique |

---

### Puter.js

| Variable | Type | Défaut | Description |
|----------|------|--------|-------------|
| `PUTER_API_URL` | `string` | `https://api.puter.com` | URL de l'API Puter.js |

---

### Mémoire — Paramètres avancés

| Variable | Type | Défaut | Description |
|----------|------|--------|-------------|
| `MEMORY_MAX_WORKING_TOKENS` | `int` | `30000` | Tokens max en mémoire Working avant compression |
| `MEMORY_COMPRESSION_THRESHOLD` | `float` | `0.8` | Seuil de compression (0.0–1.0) |
| `MEMORY_DEFAULT_TOP_K` | `int` | `5` | Nombre de résultats par défaut pour la recherche |

---

### Routeur LLM — Paramètres avancés

| Variable | Type | Défaut | Description |
|----------|------|--------|-------------|
| `LLM_DEFAULT_PROVIDER` | `string` | `gemini` | Provider par défaut |
| `LLM_DEFAULT_MODEL` | `string` | `gemini-2.5-flash` | Modèle par défaut |
| `LLM_FALLBACK_CHAIN` | `string` | `gemini,groq,openrouter,...` | Chaîne de fallback (séparée par virgules) |
| `LLM_TIMEOUT_SECONDS` | `int` | `120` | Timeout par requête LLM (secondes) |
| `LLM_MAX_RETRIES` | `int` | `3` | Tentatives max par requête |

**Chaîne de fallback complète :**

```
gemini → groq → openrouter → nvidia → cerebras → openai → anthropic → glm → ollama → pollinations
```

---

### Orchestrateur — Paramètres avancés

| Variable | Type | Défaut | Description |
|----------|------|--------|-------------|
| `ORCHESTRATOR_MAX_ITERATIONS` | `int` | `25` | Itérations max par tâche |
| `ORCHESTRATOR_CHECKPOINTER` | `string` | `memory` | Type de checkpointer (`memory`, `sqlite`) |
| `ORCHESTRATOR_INTERRUPT_BEFORE_EXECUTOR` | `bool` | `true` | Pause avant exécution (pour approval) |

---

## 🔑 Configuration des Providers

### Google Gemini (Recommandé)

```env
GOOGLE_API_KEY=AIza...
LLM_DEFAULT_PROVIDER=gemini
LLM_DEFAULT_MODEL=gemini-2.5-flash
```

**Modèles disponibles :**
- `gemini-2.5-flash` — Rapide, économique (recommandé)
- `gemini-2.5-pro` — Plus capable, plus coûteux
- `gemma-4-31b-it` — Open-source, function calling

### OpenAI

```env
OPENAI_API_KEY=sk-...
```

**Modèles disponibles :**
- `gpt-4o` — Multimodal, performant
- `gpt-4o-mini` — Économique
- `o1` — Raisonnement avancé
- `o3` — Dernière génération

### Anthropic

```env
ANTHROPIC_API_KEY=sk-ant-...
```

**Modèles disponibles :**
- `claude-3-5-sonnet-20241022` — Équilibré
- `claude-3-opus-20240229` — Plus capable

### Groq

```env
GROQ_API_KEY=gsk_...
```

**Modèles disponibles :**
- `llama-3.3-70b-versatile` — Inférence ultra-rapide
- `llama-3.1-8b-instant` — Rapide et économique

### OpenRouter

```env
OPENROUTER_API_KEY=sk-or-...
```

**Modèle :**
- `openrouter/auto` — Sélection automatique du meilleur modèle

### NVIDIA

```env
NVIDIA_API_KEY=nvapi-...
```

**Modèle :**
- `nvidia/llama-3.1-nemotron-70b-instruct`

### Cerebras

```env
CEREBRAS_API_KEY=csk-...
```

**Modèle :**
- `llama3.1-8b` — Inférence la plus rapide du marché

### Together AI

```env
TOGETHER_API_KEY=together-...
```

**Modèle :**
- `meta-llama/Llama-3.3-70B-Instruct-Turbo`

### GLM / Zhipu

```env
ZAI_API_KEY=your-key
ZAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
```

**Modèles :**
- `glm-4-plus`
- `glm-5`

### Ollama (Local)

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_DEFAULT_MODEL=llama3.1:8b
```

**Modèles populaires :**
- `llama3.1:8b` — Général (8GB RAM)
- `llama3.1:70b` — Plus capable (40GB RAM)
- `mistral:7b` — Alternatif
- `codellama:13b` — Code
- `qwen2:7b` — Multilingue

---

## 🆓 Providers Gratuits (Sans clé API)

### Pollinations.ai

- **Accès** : Aucune clé nécessaire
- **Modèles** : 29 modèles (GPT, Claude, Gemini, DeepSeek...)
- **Modèle par défaut** : `openai`
- **Limites** : Rate limit généreux, qualité variable

### G4F.dev

- **Accès** : Aucune clé nécessaire
- **Modèles** : 200+ modèles
- **Modèle par défaut** : `gpt-4o-mini`
- **Limites** : Disponibilité variable selon les providers sous-jacents

### DeepInfra

- **Accès** : Aucune clé nécessaire (tier gratuit)
- **Modèles** : Llama 4 Maverick, Qwen 3, DeepSeek V3
- **Modèle par défaut** : `meta-llama/Llama-4-Maverick-17B`
- **Limites** : Rate limit sur le tier gratuit

---

## 🐳 Configuration Docker

### docker-compose.yml

```yaml
services:
  nexus-core:
    environment:
      - NEXUS_ENV=production
      - NEXUS_SECRET_KEY=${NEXUS_SECRET_KEY}
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    ports:
      - "8080:8080"

  chromadb:
    image: chromadb/chroma:1.15.3
    ports:
      - "8000:8000"

  browser-service:
    ports:
      - "8001:8001"
```

### Variables Docker spécifiques

Créer un fichier `.env` avec vos clés API. Docker Compose lit automatiquement ce fichier.

---

## 🔒 Configuration Production

### Checklist de sécurité

- [ ] `NEXUS_ENV=production`
- [ ] `NEXUS_SECRET_KEY` changé (générer avec `secrets.token_hex(32)`)
- [ ] Clés API configurées dans `.env` (pas de clés par défaut)
- [ ] `SANDBOX_ENABLED=true`
- [ ] Rate limiting configuré (`RATE_LIMIT_RPM=60`)
- [ ] CORS vérifié (origins autorisées dans `gateway.py`)
- [ ] Swagger/ReDoc désactivés (automatique en production)
- [ ] Authentification Bearer Token active (automatique en production)
- [ ] Logs d'audit activés (`AUDIT_LOG_DIR`)
- [ ] Docker utilisé pour l'isolation

### Exemple .env production

```env
NEXUS_ENV=production
NEXUS_SECRET_KEY=a1b2c3d4e5f6...your-64-char-hex-key
NEXUS_HOST=0.0.0.0
NEXUS_PORT=8080
NEXUS_LOG_LEVEL=WARNING

GOOGLE_API_KEY=AIza...
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

RATE_LIMIT_RPM=60
SANDBOX_ENABLED=true
SANDBOX_DOCKER_IMAGE=nexus-sandbox:latest
AUDIT_LOG_DIR=/var/log/nexus/audit

CHROMA_HOST=chromadb
CHROMA_PORT=8000

LLM_DEFAULT_PROVIDER=gemini
LLM_DEFAULT_MODEL=gemini-2.5-flash
LLM_TIMEOUT_SECONDS=120
```

---

## 🎨 Configuration Frontend

### Variables d'environnement Next.js

Créer `nexus-web/.env.local` :

```env
NEXT_PUBLIC_NEXUS_API=http://localhost:8080
NEXT_PUBLIC_NEXUS_WS=ws://localhost:8081/ws
```

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_NEXUS_API` | URL du backend API |
| `NEXT_PUBLIC_NEXUS_WS` | URL du WebSocket |

---

## 🖥️ Configuration Bureau (Electron)

Le fichier `nexus-desktop/package.json` contient la configuration electron-builder :

```json
{
  "build": {
    "appId": "com.nexus-agent.desktop",
    "productName": "NEXUS Agent",
    "win": { "target": ["nsis"] },
    "mac": { "target": ["dmg"] },
    "linux": { "target": ["AppImage"] }
  }
}
```

---

## 🔄 Rechargement de configuration

La configuration est mise en cache par `get_settings()` (LRU cache). Pour recharger :

```python
from nexus.core.config import reload_settings
settings = reload_settings()
```

Ou via l'API :

```bash
curl -X POST http://localhost:8080/config \
  -H "Content-Type: application/json" \
  -d '{"llm_default_provider": "anthropic"}'
```
