# NEXUS Agent — Plan de Transformation en Agent IA Souverain Professionnel

> **Objectif :** Transformer NexusAgent en un agent IA souverain de niveau production, comparable à Cursor/Windsurf/Devin, avec installation one-click.

---

## 📊 État Actuel — Résumé Exécutif

| Aspect | Score | Problème Principal |
|--------|-------|-------------------|
| Multi-LLM Router | ✅ 9/10 | 13 providers, fallback intelligent |
| Architecture mémoire | ✅ 8/10 | 5 couches ChromaDB bien conçu |
| MCP / Outils | ⚠️ 6/10 | 43 outils définis, plusieurs non implémentés |
| Frontend | ⚠️ 5/10 | Chat-centric mais pas de routes, pas de SSR |
| Backend API | ⚠️ 6/10 | 50+ endpoints mais fichier de 1300+ lignes |
| Sécurité | ❌ 3/10 | Auth API key unique, pas de JWT, pas de RBAC |
| Base de données | ❌ 1/10 | Schema Prisma vide (User/Post génériques) |
| Installation | ❌ 3/10 | Bugs dans start.py, pas de health check |
| Infrastructure | ⚠️ 5/10 | Docker compose existe mais incomplet |
| Tests | ❌ 0/10 | Aucun test E2E frontend |
| Production | ❌ 2/10 | Pas de TLS, pas de CI/CD, pas de monitoring |

**Score global : 4.3/10** — Bon potentiel, beaucoup de travail pour la production.

---

## 🎯 PHASE 1 — Fondations Critiques (P0)

### 1.1 Refonte du Schema Prisma

**Problème :** Le schema actuel n'a que `User` et `Post` — rien lié à NexusAgent.

**Nouveau schema complet :**

```prisma
// ── Users & Auth ──
model User {
  id            String    @id @default(cuid())
  email         String    @unique
  name          String?
  avatarUrl     String?
  role          UserRole  @default(USER)
  apiKey        String?   @unique  // API key for programmatic access
  apiKeyHash    String?   // bcrypt hash
  createdAt     DateTime  @default(now())
  updatedAt     DateTime  @updatedAt
  lastLoginAt   DateTime?
  conversations Conversation[]
  auditLogs     AuditLog[]
  apiKeys       ApiKey[]
  plugins       UserPlugin[]
  skills        UserSkill[]
  settings      UserSettings?
}

enum UserRole {
  ADMIN
  USER
  READONLY
}

model ApiKey {
  id          String   @id @default(cuid())
  userId      String
  user        User     @relation(fields: [userId], references: [id])
  name        String
  keyHash     String
  permissions String[] // ["chat", "memory", "tools", "admin"]
  expiresAt   DateTime?
  lastUsedAt  DateTime?
  createdAt   DateTime @default(now())
}

model UserSettings {
  id              String   @id @default(cuid())
  userId          String   @unique
  user            User     @relation(fields: [userId], references: [id])
  theme           String   @default("dark")
  language        String   @default("fr")
  defaultProvider String   @default("gemini")
  defaultModel    String   @default("gemma-4-31b-it")
  avatarEnabled   Boolean  @default(true)
  avatarUrl       String?
  ttsEnabled      Boolean  @default(false)
  ttsEngine       String   @default("edge")
  ttsVoice        String   @default("fr-FR-DeniseNeural")
  autoRead        Boolean  @default(false)
  agentMode       String   @default("plan")
  professionalMode Boolean @default(false)
  updatedAt       DateTime @updatedAt
}

// ── Conversations ──
model Conversation {
  id          String    @id @default(cuid())
  userId      String
  user        User      @relation(fields: [userId], references: [id])
  title       String    @default("Nouvelle conversation")
  agentMode   String    @default("plan")
  provider    String?
  model       String?
  isPinned    Boolean   @default(false)
  isArchived  Boolean   @default(false)
  createdAt   DateTime  @default(now())
  updatedAt   DateTime  @updatedAt
  messages    Message[]
}

model Message {
  id              String    @id @default(cuid())
  conversationId  String
  conversation    Conversation @relation(fields: [conversationId], references: [id], onDelete: Cascade)
  role            MessageRole
  content         String
  toolCalls       Json?     // [{id, name, args}]
  toolResults     Json?     // [{id, name, result}]
  tokenCount      Int?
  provider        String?
  model           String?
  latency         Int?      // ms
  cost            Float?    // USD
  artifacts       Json?     // Generated UI artifacts
  createdAt       DateTime  @default(now())
}

enum MessageRole {
  user
  assistant
  system
  tool
}

// ── Agents & Sessions ──
model AgentSession {
  id          String      @id @default(cuid())
  userId      String
  user        User        @relation(fields: [userId], references: [id])
  agentType   String      // "code", "research", "analysis", "creative"
  status      AgentStatus @default(IDLE)
  task        String
  plan        String?
  result      String?
  provider    String?
  model       String?
  tokensUsed  Int         @default(0)
  cost        Float       @default(0)
  startedAt   DateTime    @default(now())
  completedAt DateTime?
  error       String?
  logs        Json?       // Execution trace
}

enum AgentStatus {
  IDLE
  THINKING
  PLANNING
  EXECUTING
  WAITING_APPROVAL
  COMPLETED
  FAILED
  CANCELLED
}

// ── Memory ──
model MemoryEntry {
  id          String      @id @default(cuid())
  userId      String
  user        User        @relation(fields: [userId], references: [id])
  layer       MemoryLayer
  content     String
  embedding   Bytes?      // Vector embedding (optional, ChromaDB is primary)
  metadata    Json
  hash        String      @unique  // SHA-256 for dedup
  source      String?     // "conversation", "file", "manual"
  importance  Float       @default(0.5)
  accessCount Int         @default(0)
  lastAccessed DateTime?
  createdAt   DateTime    @default(now())
  expiresAt   DateTime?   // TTL

  @@index([userId, layer])
  @@index([hash])
}

enum MemoryLayer {
  working
  episodic
  semantic
  procedural
  identity
}

// ── Tools & MCP ──
model Tool {
  id          String     @id @default(cuid())
  name        String     @unique
  category    String
  description String
  schema      Json       // JSON Schema for inputs
  enabled     Boolean    @default(true)
  isBuiltin   Boolean    @default(true)
  pluginId    String?
  plugin      Plugin?    @relation(fields: [pluginId], references: [id])
  usageCount  Int        @default(0)
  avgLatency  Float?     // ms
  createdAt   DateTime   @default(now())
  updatedAt   DateTime   @updatedAt
}

model Plugin {
  id          String     @id @default(cuid())
  name        String     @unique
  version     String
  description String
  author      String
  manifest    Json       // plugin.json content
  enabled     Boolean    @default(false)
  isVerified  Boolean    @default(false)
  trustLevel  TrustLevel @default(UNKNOWN)
  installedAt DateTime   @default(now())
  updatedAt   DateTime   @updatedAt
  tools       Tool[]
  users       UserPlugin[]
}

enum TrustLevel {
  UNKNOWN
  MEDIUM
  HIGH
  VERIFIED
}

model UserPlugin {
  userId   String
  user     User   @relation(fields: [userId], references: [id])
  pluginId String
  plugin   Plugin @relation(fields: [pluginId], references: [id])
  enabled  Boolean @default(true)
  config   Json?
  @@id([userId, pluginId])
}

model UserSkill {
  userId    String
  user      User   @relation(fields: [userId], references: [id])
  skillId   String
  name      String
  enabled   Boolean @default(true)
  config    Json?
  @@id([userId, skillId])
}

// ── Audit & Security ──
model AuditLog {
  id          String     @id @default(cuid())
  userId      String?
  user        User?      @relation(fields: [userId], references: [id])
  action      String     // "chat", "tool_call", "file_read", "config_change"
  resource    String?    // Resource affected
  details     Json?
  ipAddress   String?
  userAgent   String?
  severity    Severity   @default(INFO)
  blocked     Boolean    @default(false)
  blockReason String?
  createdAt   DateTime   @default(now())

  @@index([userId, createdAt])
  @@index([action, createdAt])
}

enum Severity {
  DEBUG
  INFO
  WARNING
  ERROR
  CRITICAL
}

// ── Workflows ──
model Workflow {
  id          String        @id @default(cuid())
  userId      String
  user        User          @relation(fields: [userId], references: [id])
  name        String
  description String?
  definition  Json          // triggers, conditions, steps
  enabled     Boolean       @default(true)
  isTemplate  Boolean       @default(false)
  version     Int           @default(1)
  runCount    Int           @default(0)
  lastRunAt   DateTime?
  lastRunStatus WorkflowRunStatus?
  createdAt   DateTime      @default(now())
  updatedAt   DateTime      @updatedAt
}

enum WorkflowRunStatus {
  SUCCESS
  FAILED
  RUNNING
  CANCELLED
}

// ── Cron Jobs ──
model CronJob {
  id          String   @id @default(cuid())
  userId      String
  user        User     @relation(fields: [userId], references: [id])
  name        String
  schedule    String   // Cron expression
  task        String
  enabled     Boolean  @default(true)
  lastRunAt   DateTime?
  lastRunStatus String?
  nextRunAt   DateTime?
  createdAt   DateTime @default(now())
  updatedAt   DateTime @updatedAt
}

// ── Metrics & Analytics ──
model DailyMetric {
  id            String   @id @default(cuid())
  date          DateTime @db.Date
  userId        String?
  tokensUsed    Int      @default(0)
  toolCalls     Int      @default(0)
  conversations Int      @default(0)
  messagesSent  Int      @default(0)
  errors        Int      @default(0)
  cost          Float    @default(0)
  avgLatency    Float?
  createdAt     DateTime @default(now())

  @@unique([date, userId])
  @@index([date])
}
```

---

### 1.2 Système d'Authentification Professionnel

**Remplacer l'API key unique par :**

1. **JWT Auth** avec refresh tokens
2. **RBAC** (Admin / User / Readonly)
3. **Multi-API keys** avec permissions granulaires
4. **OAuth2** pour intégrations tierces
5. **Rate limiting par utilisateur/clé**

**Fichiers à créer/modifier :**
- `NexusAgent/nexus/api/auth.py` — Refonte complète
- `NexusAgent/nexus/api/middleware.py` — Nouveaux middlewares
- `src/lib/auth.ts` — Client-side auth
- `src/app/api/auth/[...nextauth]/route.ts` — NextAuth integration

---

### 1.3 Correction de start.py

```python
#!/usr/bin/env python3
"""NEXUS Agent — Universal Launcher (FIXED)"""

import os
import shutil  # ← Déplacé en haut
import signal
import subprocess
import sys
import time
import socket
from pathlib import Path

def check_port_available(port):
    """Check if port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) != 0

def wait_for_health(url, timeout=30):
    """Wait for service to be healthy."""
    import httpx
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = httpx.get(url, timeout=2)
            if r.status_code == 200:
                return True
        except:
            pass
        time.sleep(0.5)
    return False
```

**Corrections :**
- `import shutil` en haut du fichier
- Health check réel au lieu de `time.sleep(3)`
- Détection de port conflict
- Gestion correcte des signaux Windows
- Lecture des stdout/stderr pour éviter le deadlock

---

### 1.4 Cohérence des Ports

| Service | Config | start.py | Proxy | Docker | → Unifier à |
|---------|--------|----------|-------|--------|-------------|
| Backend | 8080 | 8081 | 8081 | 8080 | **8081** |
| Frontend | 3000 | 3000 | 3000 | - | **3000** |
| ChromaDB | 8000 | - | - | 8000 | **8000** |

---

### 1.5 Installation One-Click

**Nouveau `install.py` complet :**

```python
#!/usr/bin/env python3
"""
NEXUS Agent — One-Click Installer
Supports: Windows, macOS, Linux
Python 3.11+ | Node 20+ | Bun (optional)
"""

import sys
import os
import subprocess
import platform
import secrets
import json
from pathlib import Path

class Installer:
    def __init__(self):
        self.root = Path(__file__).resolve().parent
        self.backend = self.root / "NexusAgent"
        self.errors = []
        self.warnings = []

    def run(self):
        self.banner()
        self.check_system()
        self.setup_backend()
        self.setup_frontend()
        self.setup_database()
        self.generate_env()
        self.verify()
        self.done()

    def check_system(self):
        """Check Python, Node, system requirements."""
        # Python 3.11+
        py_ver = sys.version_info
        if py_ver < (3, 11):
            self.fail(f"Python 3.11+ required, found {py_ver.major}.{py_ver.minor}")

        # Node.js
        try:
            node_ver = subprocess.check_output(["node", "--version"], text=True).strip()
            major = int(node_ver.lstrip("v").split(".")[0])
            if major < 20:
                self.warn(f"Node 20+ recommended, found {node_ver}")
        except:
            self.fail("Node.js not found. Install from nodejs.org")

        # Bun (optional)
        self.has_bun = shutil.which("bun") is not None

        # Docker (optional)
        self.has_docker = shutil.which("docker") is not None

    def setup_backend(self):
        """Create venv and install Python dependencies."""
        venv_python = self.backend / "venv" / ("Scripts" if sys.platform == "win32" else "bin") / "python"

        if not venv_python.exists():
            self.step("Creating Python virtual environment...")
            subprocess.run([sys.executable, "-m", "venv", str(self.backend / "venv")], check=True)

        self.step("Installing Python dependencies...")
        pip = self.backend / "venv" / ("Scripts" if sys.platform == "win32" else "bin") / "pip"
        subprocess.run([str(pip), "install", "-r", str(self.backend / "requirements.txt")], check=True)

    def setup_frontend(self):
        """Install Node.js dependencies."""
        self.step("Installing frontend dependencies...")
        cmd = ["bun", "install"] if self.has_bun else ["npm", "install"]
        subprocess.run(cmd, cwd=str(self.root), check=True)

    def setup_database(self):
        """Setup Prisma database."""
        self.step("Setting up database...")
        subprocess.run(["npx", "prisma", "generate"], cwd=str(self.root), check=True)
        subprocess.run(["npx", "prisma", "db", "push"], cwd=str(self.root), check=True)

    def generate_env(self):
        """Generate .env files with secure defaults."""
        secret_key = secrets.token_hex(32)

        # Backend .env
        backend_env = self.backend / ".env"
        if not backend_env.exists():
            backend_env.write_text(f"""# NEXUS Backend Configuration
NEXUS_ENV=development
NEXUS_PORT=8081
NEXUS_SECRET_KEY={secret_key}

# LLM Providers (add your keys)
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# GOOGLE_API_KEY=AIza...

# ChromaDB
CHROMA_HOST=localhost
CHROMA_PORT=8000

# CORS
ALLOWED_ORIGINS=http://localhost:3000
""")

        # Frontend .env
        frontend_env = self.root / ".env.local"
        if not frontend_env.exists():
            frontend_env.write_text("""# NEXUS Frontend Configuration
NEXT_PUBLIC_NEXUS_BACKEND=http://localhost:8081
DATABASE_URL="file:./dev.db"
""")

    def verify(self):
        """Run verification checks."""
        self.step("Running verification...")
        result = subprocess.run(
            [str(self.backend / "venv" / ("Scripts" if sys.platform == "win32" else "bin") / "python"),
             "-m", "nexus", "verify"],
            cwd=str(self.backend),
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            self.warn(f"Verification warnings:\n{result.stderr}")

    def done(self):
        """Print completion message."""
        print("\n" + "=" * 60)
        print("  ✅ NEXUS Agent installed successfully!")
        print("=" * 60)
        print(f"\n  Start with:  python start.py")
        print(f"  Frontend:    http://localhost:3000")
        print(f"  Backend:     http://localhost:8081/docs")
        print(f"  API Docs:    http://localhost:8081/docs")
        if self.warnings:
            print(f"\n  ⚠️  Warnings ({len(self.warnings)}):")
            for w in self.warnings:
                print(f"     - {w}")
        print()
```

---

## 🎯 PHASE 2 — Backend Production-Ready

### 2.1 Modularisation de l'API Gateway

**Problème :** `api/gateway.py` fait 1300+ lignes.

**Solution — Découpage en routers :**

```
nexus/api/
├── __init__.py
├── app.py              # FastAPI app factory
├── middleware.py       # Auth, rate limit, CORS, logging
├── routers/
│   ├── __init__.py
│   ├── chat.py         # /chat, /chat/stream
│   ├── tasks.py        # /run, /tasks/*
│   ├── memory.py       # /memory/*
│   ├── agents.py       # /agents/*
│   ├── tools.py        # /tools/*
│   ├── mcp.py          # /mcp/*
│   ├── plugins.py      # /plugins/*
│   ├── rules.py        # /rules/*
│   ├── workflows.py    # /workflows/*
│   ├── voice.py        # /voice/*
│   ├── viz.py          # /viz/*
│   ├── approvals.py    # /approvals/*
│   ├── config.py       # /config/*
│   ├── metrics.py      # /metrics/*
│   └── health.py       # /health, /ready
├── deps.py             # Dependency injection
├── models.py           # Pydantic models
├── exceptions.py       # Custom exceptions
└── websocket.py        # WebSocket endpoint
```

---

### 2.2 Streaming Endpoint

**Implémenter `/chat/stream` dans `routers/chat.py` :**

```python
@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, auth: User = Depends(verify_auth)):
    """SSE streaming chat endpoint."""
    async def event_generator():
        router = get_router()
        async for chunk in router.chat_stream(
            messages=request.messages,
            provider=request.provider,
            model=request.model,
        ):
            yield f"data: {json.dumps(chunk)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
```

---

### 2.3 WebSocket Endpoint

**Créer `websocket.py` :**

```python
from fastapi import WebSocket, WebSocketDisconnect
from nexus.core.broadcaster import get_broadcaster

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = None):
    await websocket.accept()
    broadcaster = get_broadcaster()

    try:
        # Auth via token
        user = await verify_ws_auth(token)
        await broadcaster.connect(websocket, user.id)

        while True:
            data = await websocket.receive_json()
            await handle_ws_message(data, user, broadcaster)
    except WebSocketDisconnect:
        await broadcaster.disconnect(websocket)
```

---

### 2.4 API Versioning

```python
# nexus/api/app.py
app = FastAPI(
    title="NEXUS Agent API",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Mount v1 router
from nexus.api.routers.v1 import chat, memory, agents, tools
app.include_router(chat.router, prefix="/v1")
app.include_router(memory.router, prefix="/v1")
```

---

### 2.5 Request/Response Logging

```python
# nexus/api/middleware.py
import logging
import time
from fastapi import Request, Response

logger = logging.getLogger("nexus.api")

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    start = time.time()
    request_id = str(uuid.uuid4())[:8]

    response = await call_next(request)

    duration = time.time() - start
    logger.info(
        f"[{request_id}] {request.method} {request.url.path} "
        f"{response.status_code} {duration:.3f}s"
    )

    response.headers["X-Request-ID"] = request_id
    return response
```

---

## 🎯 PHASE 3 — Frontend Production-Ready

### 3.1 Architecture de Routes

```
src/app/
├── layout.tsx              # Root layout with auth provider
├── page.tsx                # Home → redirect to /chat
├── chat/
│   ├── page.tsx            # Chat list / new conversation
│   └── [id]/
│       └── page.tsx        # Single conversation
├── settings/
│   └── page.tsx            # Settings page (providers, keys, profile)
├── dashboard/
│   └── page.tsx            # Metrics dashboard
├── api/
│   ├── auth/
│   │   └── [...nextauth]/
│   │       └── route.ts    # NextAuth
│   ├── nexus/
│   │   └── [...path]/
│   │       └── route.ts    # Proxy to backend
│   └── health/
│       └── route.ts        # Health check
└── globals.css
```

---

### 3.2 NextAuth Integration

```typescript
// src/app/api/auth/[...nextauth]/route.ts
import NextAuth from "next-auth"
import CredentialsProvider from "next-auth/providers/credentials"

const handler = NextAuth({
  providers: [
    CredentialsProvider({
      name: "NEXUS API Key",
      credentials: {
        apiKey: { label: "API Key", type: "password" }
      },
      async authorize(credentials) {
        const res = await fetch(`${process.env.NEXUS_BACKEND}/v1/auth/verify`, {
          headers: { Authorization: `Bearer ${credentials?.apiKey}` }
        })
        if (res.ok) return { id: "nexus-user", name: "NEXUS User" }
        return null
      }
    })
  ],
  session: { strategy: "jwt" },
  pages: { signIn: "/login" }
})

export { handler as GET, handler as POST }
```

---

### 3.3 Security Headers

```typescript
// next.config.ts
import type { NextConfig } from "next"

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  images: {
    domains: ["localhost", "avatars.githubusercontent.com"],
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Content-Security-Policy",
            value: "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; connect-src 'self' ws: wss: http://localhost:* https:; frame-src 'self';"
          },
        ],
      },
    ]
  },
}

export default nextConfig
```

---

### 3.4 Persistance des Conversations

**Remplacer localStorage par IndexedDB + sync backend :**

```typescript
// src/lib/db/conversations.ts
import { openDB } from 'idb'

const DB_NAME = 'nexus-db'
const DB_VERSION = 1

export async function getDB() {
  return openDB(DB_NAME, DB_VERSION, {
    upgrade(db) {
      if (!db.objectStoreNames.contains('conversations')) {
        db.createObjectStore('conversations', { keyPath: 'id' })
      }
      if (!db.objectStoreNames.contains('messages')) {
        const store = db.createObjectStore('messages', { keyPath: 'id' })
        store.createIndex('conversationId', 'conversationId')
      }
    },
  })
}
```

---

## 🎯 PHASE 4 — Infrastructure Production

### 4.1 Docker Compose Complet

```yaml
# docker-compose.yml (racine du projet)
services:
  # ── Frontend (Next.js) ──
  nexus-web:
    build:
      context: .
      dockerfile: docker/Dockerfile.web
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_NEXUS_BACKEND=http://nexus-api:8081
      - DATABASE_URL=file:/app/data/dev.db
    depends_on:
      nexus-api:
        condition: service_healthy
    restart: unless-stopped
    volumes:
      - web-data:/app/data

  # ── Backend API ──
  nexus-api:
    build:
      context: ./NexusAgent
      dockerfile: ../docker/Dockerfile.core
    ports:
      - "8081:8081"
    environment:
      - NEXUS_ENV=production
      - NEXUS_PORT=8081
      - CHROMA_HOST=chromadb
      - CHROMA_PORT=8000
      - DATABASE_URL=postgresql://nexus:nexus@postgres:5432/nexus
    depends_on:
      chromadb:
        condition: service_healthy
      postgres:
        condition: service_healthy
    restart: unless-stopped
    volumes:
      - nexus-data:/app/nexus_data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8081/health"]
      interval: 15s
      timeout: 5s
      retries: 3

  # ── PostgreSQL ──
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: nexus
      POSTGRES_PASSWORD: nexus
      POSTGRES_DB: nexus
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U nexus"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ── ChromaDB ──
  chromadb:
    image: chromadb/chroma:1.15.3
    volumes:
      - chroma-data:/chroma/chroma
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:8000/api/v1/heartbeat"]
      interval: 15s
      timeout: 5s
      retries: 5

  # ── Caddy (Reverse Proxy + TLS) ──
  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy-data:/data
      - caddy-config:/config
    depends_on:
      - nexus-web
      - nexus-api

  # ── Monitoring (optional) ──
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana

networks:
  default:
    name: nexus-network

volumes:
  web-data:
  nexus-data:
  postgres-data:
  chroma-data:
  caddy-data:
  caddy-config:
  prometheus-data:
  grafana-data:
```

---

### 4.2 Caddyfile avec TLS

```
# Caddyfile
{
    email admin@nexus-agent.local
}

# HTTP → HTTPS redirect
http://localhost {
    redir https://localhost{uri}
}

# Main site
localhost {
    # Frontend
    reverse_proxy /api/* nexus-api:8081
    reverse_proxy /ws/* nexus-api:8081
    reverse_proxy nexus-web:3000

    # Security headers
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Frame-Options "DENY"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
    }

    # WebSocket support
    @websocket {
        header Connection *Upgrade*
        header Upgrade    websocket
    }
    reverse_proxy @websocket nexus-api:8081 {
        header_up Host {host}
        header_up X-Real-IP {remote}
        header_up X-Forwarded-For {remote}
        header_up X-Forwarded-Proto {scheme}
    }
}
```

---

### 4.3 CI/CD GitHub Actions

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - run: pip install ruff mypy
      - run: ruff check NexusAgent/
      - run: mypy NexusAgent/
      - run: npm ci
      - run: npm run lint

  test-backend:
    runs-on: ubuntu-latest
    services:
      chromadb:
        image: chromadb/chroma:1.15.3
        ports:
          - 8000:8000
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r NexusAgent/requirements.txt
      - run: pytest NexusAgent/tests/ -v --cov=nexus

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - run: npm ci
      - run: npm run build
      - run: npx playwright install
      - run: npm run test:e2e

  docker:
    runs-on: ubuntu-latest
    needs: [lint, test-backend, test-frontend]
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - run: docker compose build
      - run: docker compose up -d
      - run: sleep 30 && curl -f http://localhost:3000
```

---

## 🎯 PHASE 5 — Fonctionnalités Agent Souverain

### 5.1 Git Integration

```python
# nexus/tools/git_tools.py
@tool(name="git_status", category="version_control")
async def git_status(path: str = ".") -> dict:
    """Get git status of a repository."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=path, capture_output=True, text=True
    )
    return {"status": result.stdout, "clean": result.returncode == 0}

@tool(name="git_commit", category="version_control")
async def git_commit(message: str, path: str = ".") -> dict:
    """Commit changes with a message."""
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=path, capture_output=True, text=True
    )
    return {"success": result.returncode == 0, "output": result.stdout}
```

### 5.2 Terminal Access

```python
# nexus/tools/terminal.py
@tool(name="terminal_exec", category="system")
async def terminal_exec(command: str, timeout: int = 30, cwd: str = ".") -> dict:
    """Execute a command in the terminal with sandboxing."""
    # Validate command against allowlist
    if not is_command_allowed(command):
        return {"error": "Command not allowed in safe mode"}

    process = await asyncio.create_subprocess_shell(
        command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
        return {
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
            "returncode": process.returncode,
        }
    except asyncio.TimeoutError:
        process.kill()
        return {"error": f"Command timed out after {timeout}s"}
```

### 5.3 Browser Automation

```python
# nexus/tools/browser.py
from playwright.async_api import async_playwright

@tool(name="browser_navigate", category="web")
async def browser_navigate(url: str, wait_for: str = "load") -> dict:
    """Navigate to a URL and return page content."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until=wait_for)
        content = await page.content()
        title = await page.title()
        await browser.close()
        return {"title": title, "content": content[:10000]}
```

### 5.4 File System Operations Sécurisées

```python
# nexus/tools/filesystem.py
from pathlib import Path

ALLOWED_ROOTS = [Path.cwd(), Path.home() / "nexus-workspace"]

def validate_path(path: str) -> Path:
    """Validate path is within allowed roots."""
    resolved = Path(path).resolve()
    for root in ALLOWED_ROOTS:
        if resolved.is_relative_to(root.resolve()):
            return resolved
    raise PermissionError(f"Path {path} is outside allowed directories")

@tool(name="read_file", category="filesystem")
async def read_file(path: str) -> dict:
    """Read a file with path traversal protection."""
    safe_path = validate_path(path)
    if not safe_path.exists():
        return {"error": f"File not found: {path}"}
    if safe_path.is_dir():
        return {"error": f"Path is a directory: {path}"}
    content = safe_path.read_text(encoding="utf-8")
    return {"content": content, "size": len(content)}
```

---

## 🎯 PHASE 6 — UX/UI Professionnelle

### 6.1 Réduire la Sphère Hologramme

Déjà fait — radius réduit de 0.5 à 0.22.

### 6.2 Settings Page Dédiée

```
src/app/settings/page.tsx
├── Profile Settings (name, avatar, theme)
├── LLM Providers (select, API keys, test connection)
├── Models (per-provider model selection)
├── Voice Settings (engine, voice, language, auto-read)
├── Memory Settings (compact, clear layers)
├── Security (API keys, sessions, 2FA)
└── About (version, changelog, links)
```

### 6.3 Onboarding Flow

```
src/app/onboarding/
├── page.tsx          # Welcome screen
├── step-1/           # Choose LLM provider
├── step-2/           # Enter API key
├── step-3/           # Test connection
├── step-4/           # Choose avatar / professional mode
└── complete/         # Ready to use
```

### 6.4 Command Palette Améliorée

```
⌘K — Command Palette
├── 🔄 New Conversation
├── 📋 Recent Conversations
├── ️ Settings
├── 🎨 Change Theme
├── 🤖 Switch Provider
├── 📊 Open Dashboard
├── 🔧 Agent Actions
│   ├── Plan mode
│   ├── Build mode
│   └── Research mode
└── ❓ Help & Shortcuts
```

---

## 📋 Roadmap d'Exécution

| Phase | Tâches | Priorité | Effort |
|-------|--------|----------|--------|
| **1. Fondations** | Prisma schema, Auth JWT, start.py fix, ports, install.py | P0 | 3 jours |
| **2. Backend** | Modular API, streaming, WebSocket, versioning, logging | P0 | 4 jours |
| **3. Frontend** | Routes, NextAuth, security headers, IndexedDB, settings page | P1 | 3 jours |
| **4. Infrastructure** | Docker complet, Caddy TLS, CI/CD, monitoring | P1 | 2 jours |
| **5. Agent Features** | Git, terminal, browser, filesystem sécurisé | P1 | 3 jours |
| **6. UX/UI** | Onboarding, command palette, mobile responsive | P2 | 2 jours |

**Total estimé : 17 jours de travail**

---

## 🚀 Quick Wins (à faire en premier)

1. ✅ **Réduire la sphère** — Fait (0.5 → 0.22)
2. **Fix start.py** — `import shutil` en haut, health check réel
3. **Unifier les ports** — Tout à 8081
4. **Prisma schema** — Remplacer User/Post par les vrais modèles
5. **install.py** — Génération de secret key, vérification complète
6. **Bouton settings visible** — Fait (header + bottom-left)
7. **Avatar centré** — Fait (flex center)

---

## 📁 Structure Finale du Projet

```
NexusAgent/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── release.yml
├── docker/
│   ├── Dockerfile.web
│   ├── Dockerfile.core
│   └── Dockerfile.browser
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/
├── NexusAgent/               # Backend Python
│   ├── nexus/
│   │   ├── api/
│   │   │   ├── app.py
│   │   │   ├── middleware.py
│   │   │   ├── deps.py
│   │   │   ├── models.py
│   │   │   ├── websocket.py
│   │   │   └── routers/      # 15 routers modulaires
│   │   ├── core/
│   │   ├── agents/
│   │   ├── llm/
│   │   ├── memory/
│   │   ├── tools/
│   │   ├── mcp/
│   │   ├── plugins/
│   │   ├── rules/
│   │   ├── hooks/
│   │   ├── workflows/
│   │   ├── modes/
│   │   ├── monitoring/
│   │   └── cli/
│   ├── tests/
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── docker-compose.yml
├── prisma/
│   └── schema.prisma         # Schema complet NexusAgent
├── src/                      # Frontend Next.js
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── chat/[id]/page.tsx
│   │   ├── settings/page.tsx
│   │   ├── dashboard/page.tsx
│   │   ├── onboarding/
│   │   └── api/
│   ├── components/nexus/
│   ├── lib/
│   │   ├── store/
│   │   ├── db/               # IndexedDB
│   │   ├── auth.ts
│   │   └── nexus-api.ts
│   ├── hooks/
│   └── types/
├── docker-compose.yml        # Compose complet (racine)
├── Caddyfile
├── install.py                # One-click installer
├── start.py                  # Fixed launcher
├── package.json
├── next.config.ts
├── tailwind.config.ts
└── README.md
```

---

## ✅ Checklist de Validation Production

- [ ] Prisma schema complet avec tous les modèles
- [ ] JWT auth avec refresh tokens
- [ ] RBAC (Admin/User/Readonly)
- [ ] API versioning (/v1/)
- [ ] Streaming endpoint fonctionnel
- [ ] WebSocket avec auth
- [ ] Request/response logging
- [ ] Rate limiting avec headers
- [ ] Security headers (CSP, HSTS, etc.)
- [ ] TLS/HTTPS via Caddy
- [ ] Docker compose complet (web + api + db + chroma)
- [ ] CI/CD GitHub Actions
- [ ] Health checks sur tous les services
- [ ] Backup strategy pour ChromaDB + PostgreSQL
- [ ] Monitoring Prometheus + Grafana
- [ ] Error tracking (Sentry)
- [ ] E2E tests (Playwright)
- [ ] One-click install fonctionnel
- [ ] Onboarding flow
- [ ] Settings page complète
- [ ] Mobile responsive
- [ ] Git integration
- [ ] Terminal access avec sandbox
- [ ] Browser automation
- [ ] Filesystem operations sécurisées
- [ ] Path traversal protection partout
- [ ] Input sanitization
- [ ] Output validation
- [ ] Token cost tracking
- [ ] Conversation persistence (IndexedDB + sync)
- [ ] i18n complet (FR/EN/JA)
