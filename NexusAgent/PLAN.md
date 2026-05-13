# 🧠 PLAN NEXUS 2.0 — L'Agent IA Ultime

## Objectif

Dépasser **Hermes Agent**, **OpenClaw**, **Space Agent**, et **Bolt.diy** en combinant leurs meilleures features dans une architecture native, cohérente, et souveraine.

---

## 📊 Benchmark Concurrentiel

| Feature | **NEXUS** | Hermes | OpenClaw | Space | Bolt.diy |
|---------|-----------|--------|----------|-------|----------|
| **LLM Providers** | 8 (3 gratuits) | 200+ (OpenRouter) | 1 (OpenAI) | 1 | 19+ |
| **Mémoire** | ⭐5 niveaux ChromaDB | FTS5 | FTS5 | Aucune | Aucune |
| **Orchestration** | ⭐3 moteurs | Simple loop | Simple loop | Simple | Simple |
| **Raisonnement** | ⭐ReAct+ToT+LATS | ReAct | ReAct | Aucun | Aucun |
| **Multi-Channel** | 3 canaux | 5 canaux | ⭐**23 canaux** | Aucun | Aucun |
| **Avatar Waifu** | ⭐**Unique** | ❌ | ❌ | ❌ | ❌ |
| **Visual Builder** | ⭐**Unique** | ❌ | ❌ | ❌ | ❌ |
| **Sandbox** | ⭐Per-action Docker | Session Docker | Docker non-main | ❌ | ❌ |
| **Computer Use** | ⭐**Unique** | ❌ | ❌ | ❌ | ❌ |
| **Cron/Automation** | ❌ | ✅ | ✅ | ❌ | ❌ |
| **Self-Learning** | ❌ | ✅ | ❌ | ✅ | ❌ |
| **Code Generation** | ⭐Code Engine | ❌ | ❌ | ❌ | ⭐WebContainers |
| **Desktop App** | ⭐Tauri+Next.js | TUI | macOS/iOS | Electron | Electron |
| **Community** | Nouveau | 146k ★ | **371k ★** | 1.2k ★ | 19.3k ★ |
| **Lignes de code** | ⭐**30k Python** | Très large | **Monstre** | Petit | Large |

---

## 🏛️ Architecture NEXUS 2.0

```
                    ┌─────────────────────────────────┐
                    │        USER INTERFACES          │
                    ├─────────────────────────────────┤
                    │  Desktop  │  Web  │  CLI  │  API │
                    │  (Tauri)  │(Next) │(Typer)│(Fast)│
                    └───────────┴───────┴───────┴──────┘
                              │        │
                    ┌─────────▼────────▼─────────┐
                    │     GATEWAY UNIVERSELLE     │ ← NOUVEAU
                    │   WebSocket · REST · MCP    │
                    │    A2P · ACP · 23 canaux    │
                    └─────────┬──────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
    ┌─────────────────┐ ┌──────────┐ ┌──────────────┐
    │   AGENT CORE    │ │ MEMORY   │ │ KNOWLEDGE    │
    │  Reasoning (3)  │ │ 5 Levels │ │ RAG · Graph  │
    │  Orchestr.(3)   │ │ ChromaDB │ │ Deep Research│
    │  Planning (NEW) │ │ Vector   │ │ Web Search   │
    └────────┬────────┘ └──────────┘ └──────────────┘
             │
    ┌────────▼───────────────────────────────┐
    │         CAPABILITIES LAYER             │
    ├────────────────────────────────────────┤
    │ Code Engine │ Browser │ Computer Use   │
    │ Terminal    │ Git     │ Deploy         │
    │ Filesystem  │ Docker  │ Network        │
    └────────┬───────────────────────────────┘
             │
    ┌────────▼───────────────────────────────┐
    │         EXPERIENCE LAYER (NEW)         │
    ├────────────────────────────────────────┤
    │ Self-Learning │ Cron Scheduler         │
    │ Skill Cryst.  │ Multi-Agent Routing    │
    │ Profile Sys   │ Plugin System          │
    │ Voice Wake    │ Live Canvas A2UI       │
    │ Avatar Waifu  │ Activity Viz           │
    └────────────────────────────────────────┘
```

---

## 📋 Phase 1 — Foundation (Semaines 1-2) ✅ FAIT

- ✅ Free Provider Hub (Pollinations, G4F, DeepInfra)
- ✅ Avatar Module (AIAvatarKit + VOICEVOX + VRM)
- ✅ Docker Per-Action Sandbox
- ✅ Benchmark Evaluation Framework
- ✅ Visual Flow Builder (React Flow)
- ✅ Gemma 4 Thinking (HIGH/MINIMAL)
- ✅ Agent Activity View (brick-by-brick)
- ✅ Documentation + GitHub CI/CD

---

## 📋 Phase 2 — Multi-Channel Gateway (Semaines 3-4)

### Objectif : Dépasser OpenClaw sur les canaux

```
nexus/gateway/
├── __init__.py
├── gateway.py           # Hub central WebSocket + REST
├── channels/
│   ├── telegram.py      # ✅ Existe déjà
│   ├── discord.py       # 🔴 NOUVEAU
│   ├── whatsapp.py      # 🔴 NOUVEAU (via whatsapp-web.js)
│   ├── slack.py         # 🔴 NOUVEAU
│   ├── signal.py        # 🔴 NOUVEAU
│   ├── email.py         # ✅ Existe déjà
│   ├── imessage.py      # 🔴 NOUVEAU (macOS only)
│   ├── matrix.py        # 🔴 NOUVEAU
│   ├── irc.py           # 🔴 NOUVEAU
│   ├── webchat.py       # ✅ Intégré dans Next.js
│   ├── voice.py         # ✅ Existe déjà
│   └── wechat.py        # 🔴 NOUVEAU (bridge)
├── channel_base.py      # Interface commune
├── message_router.py    # Routage multi-channel
├── dm_pairing.py        # 🔴 NOUVEAU (pairing codes)
└── security.py          # 🔴 NOUVEAU (allowlists, sandboxing)
```

**Inspiré de** : OpenClaw (23 canaux, DM pairing, gateway architecture)

**Faisabilité** : ✅ Élevée — chaque canal est un adaptateur Python. whatsapp-web.js nécessite Node.js bridge (100 lignes).

### Architecture Gateway

```
Message entrant (Telegram/WhatsApp/Discord/...)
  → Channel Adapter (normalise en format interne)
  → Message Router (routing vers agent/session)
  → Agent Core (traite avec LLM + outils)
  → Channel Adapter (envoie réponse formatée)
  → Canal de sortie
```

---

## 📋 Phase 3 — Self-Learning & Skill Crystallization (Semaine 4)

### Objectif : Dépasser Hermes Agent sur l'apprentissage

Inspiré du **Hermes Agent learning loop** :
1. Agent accomplit une tâche complexe
2. NEXUS analyse la trajectoire et crée un skill
3. Le skill est stocké dans Procedural Memory (L4)
4. À l'usage suivant, le skill s'améliore automatiquement
5. Les skills fréquents sont "cristallisés" → scripts standalone

```
nexus/learning/
├── learning_loop.py       # 🔴 NOUVEAU — boucle principale
├── trajectory_analyzer.py # 🔴 NOUVEAU — analyse les traces
├── skill_crystallizer.py  # 🔴 NOUVEAU — mémoire procédurale → skills
├── skill_improver.py      # 🔴 NOUVEAU — auto-amélioration
├── profile_builder.py     # 🔴 NOUVEAU — modèle utilisateur
└── cron_scheduler.py      # 🔴 NOUVEAU — automations planifiées

nexus/memory/procedural.py # ✅ Existe — à enrichir
```

**Flow** :
```
Tâche accomplie → Trajectory Analyzer → Skill Candidate
  → Procedural Memory (L4) → Skill Improver (next use)
  → Usage fréquent → Skill Crystallizer → standalone script
```

**Faisabilité** : ✅ Élevée — Procedural Memory existe déjà (L4), il faut ajouter l'analyse de trajectoire et la boucle d'amélioration.

---

## 📋 Phase 4 — Cron Scheduler & Automations (Semaine 4)

### Objectif : Dépasser Hermes/OpenClaw sur les tâches planifiées

```
nexus/automation/
├── scheduler.py       # 🔴 NOUVEAU — APScheduler intégré
├── triggers.py        # 🔴 NOUVEAU — cron, interval, webhook, file watch
├── actions.py         # 🔴 NOUVEAU — exécution de tâches
├── templates.py       # 🔴 NOUVEAU — templates prédéfinis
└── mailbox.py         # 🔴 NOUVEAU — Gmail Pub/Sub, inbox
```

**Exemples d'automatismes** :
- `"Tous les jours à 9h, résume mes emails"`
- `"Quand un fichier change dans /projects, commit et push"`
- `"Toutes les heures, check le prix du BTC"`
- `"Quand je reçois un email de X, réponds avec Y"`

**Faisabilité** : ✅ Très élevée — APScheduler est mature, 3 lignes pour un cron.

---

## 📋 Phase 5 — Multi-Agent Routing & Sessions (Semaine 5)

### Objectif : Dépasser OpenClaw sur le routing multi-agent

```
nexus/orchestrator/
├── router.py           # ✅ Existe — à enrichir
├── multi_agent.py      # 🔴 NOUVEAU — routing channel→agent
├── session_manager.py  # 🔴 NOUVEAU — sessions persistantes
├── agent_factory.py    # 🔴 NOUVEAU — spawn agents isolés
└── workspace.py        # 🔴 NOUVEAU — workspaces isolés
```

**Concepts** :
- **Workspace** : environnement isolé (config, mémoire, skills)
- **Session** : conversation avec historique
- **Agent routing** : canal A → workspace X, canal B → workspace Y
- **Sub-agents** : spawn d'agents parallèles pour tâches complexes

**Faisabilité** : ✅ Élevée — architecture existante, à étendre.

---

## 📋 Phase 6 — Voice Wake & Talk Mode (Semaine 5)

### Objectif : Dépasser OpenClaw sur la voix

```
nexus/comms/avatar/
├── avatar_manager.py   # ✅ Existe
├── voice_wake.py       # 🔴 NOUVEAU — wake word detection
├── talk_mode.py        # 🔴 NOUVEAU — conversation continue
├── vad.py              # 🔴 NOUVEAU — Voice Activity Detection
└── stt_tts_pipeline.py # 🔴 NOUVEAU — pipeline STS complet

nexus/comms/voice_io.py # ✅ Existe — à enrichir
```

**Flow** :
```
Wake word détecté → VAD actif → STT (Whisper)
  → NEXUS LLM → TTS (VOICEVOX/XTTS)
  → Audio playback + Lip sync avatar
```

**Faisabilité** : ✅ Élevée — modules existants, `pip install pvporcupine` pour wake word, `webrtcvad` pour VAD.

---

## 📋 Phase 7 — Live Canvas A2UI (Semaine 6)

### Objectif : Dépasser OpenClaw et Space Agent sur l'UI temps réel

Inspiré du **Live Canvas** d'OpenClaw et du **runtime browser** de Space Agent.

```
nexus-web/src/components/
├── nexus/
│   ├── chat-panel.tsx       # ✅ Existe
│   ├── agent-activity-view.tsx  # ✅ Existe
│   ├── live-canvas.tsx      # 🔴 NOUVEAU — canvas piloté par l'agent
│   ├── interactive-view.tsx  # 🔴 NOUVEAU — composants interactifs
│   └── a2ui-bridge.ts       # 🔴 NOUVEAU — A2UI protocol handler

nexus/core/a2a.py            # ✅ Existe — à enrichir en A2UI
```

**Live Canvas Features** :
- L'agent peut dessiner, afficher des graphs, des tableaux
- Composants interactifs (formulaires, boutons, sliders)
- Mise à jour temps réel via WebSocket
- L'agent peut construire des UI dans le canvas pendant qu'il travaille

**A2UI Protocol** (inspiré d'OpenClaw) :
```json
{
  "type": "render",
  "component": "Chart",
  "props": {
    "type": "bar",
    "data": [10, 20, 30],
    "labels": ["A", "B", "C"]
  }
}
```

**Faisabilité** : ✅ Élevée — WebSocket + React permettent ça nativement.

---

## 📋 Phase 8 — Plugin System & Extensions (Semaine 6-7)

### Objectif : Dépasser OpenClaw sur l'extensibilité

Inspiré du **plugin system** d'OpenClaw (extensions/).

```
nexus/plugins/
├── __init__.py
├── plugin_base.py     # 🔴 NOUVEAU — classe de base
├── plugin_manager.py  # 🔴 NOUVEAU — chargement dynamique
├── registry.py        # 🔴 NOUVEAU — catalogue de plugins
└── marketplace.py     # 🔴 NOUVEAU — hub de plugins communautaires

nexus-web/src/components/nexus/plugin-marketplace.tsx  # 🔴 NOUVEAU
```

**Plugin API** (simple) :
```python
class NexusPlugin:
    name: str
    version: str
    tools: list[MCPTool]
    async def on_load(self): ...
    async def on_unload(self): ...
```

**Faisabilité** : ✅ Très élevée — importlib + MCP tools existants.

---

## 📋 Phase 9 — Code Generation Engine (Semaine 7-8)

### Objectif : Dépasser Bolt.diy sur la génération de code

Inspiré de **Bolt.diy** (WebContainers) et **OpenCode**.

```
nexus/dev/
├── code_engine.py        # ✅ Existe — à enrichir
├── code_generator.py     # 🔴 NOUVEAU — génération full-stack
├── preview_server.py     # 🔴 NOUVEAU — aperçu web en temps réel
├── file_watcher.py       # 🔴 NOUVEAU — rebuild auto sur changement
├── project_scaffold.py   # 🔴 NOUVEAU — scaffolding projets
└── deploy.py             # ✅ Existe — à enrichir (Vercel, Netlify)

nexus-web/src/components/nexus/
├── code-preview.tsx      # 🔴 NOUVEAU — preview iframe
├── diff-view.tsx         # 🔴 NOUVEAU — voir les changements
├── file-explorer.tsx     # 🔴 NOUVEAU — explorateur de fichiers
└── terminal-embed.tsx    # 🔴 NOUVEAU — terminal intégré
```

**Architecture Code Generation** :
```
Prompt → Code Generator → File System → Preview Server
                                    ↓
                              Diff View (accept/reject)
                                    ↓
                              Git commit + Deploy
```

**Faisabilité** : ✅ Haute — code_engine existe. WebContainers nécessite licence commerciale (StackBlitz). Alternative: Docker container avec serveur de preview.

---

## 📋 Phase 10 — Profiling & Personalization (Semaine 8)

### Objectif : Dépasser Hermes sur la personnalisation

Inspiré du **profile system** d'Hermes.

```
nexus/memory/
├── identity.py          # ✅ Existe (L5)
├── profile_manager.py   # 🔴 NOUVEAU — profils utilisateur
└── preference_learner.py # 🔴 NOUVEAU — apprentissage des préférences
```

**Features** :
- Profils multiples (personnel, travail, dev)
- Apprentissage automatique des préférences
- Migration entre profils
- Isolation totale des données

**Faisabilité** : ✅ Élevée — Identity Memory existe déjà (L5).

---

## 📋 Phase 11 — Community & Distribution (Semaine 8-9)

### Objectif : Atteindre la masse critique

```
.github/
├── workflows/
│   ├── ci.yml            # ✅ Existe
│   ├── release.yml       # ✅ Existe
│   └── publish.yml       # 🔴 NOUVEAU — PyPI + npm + Homebrew
├── ISSUE_TEMPLATE/       # 🔴 NOUVEAU
├── FUNDING.yml           # 🔴 NOUVEAU
└── CONTRIBUTING.md       # ✅ Existe

nexus-web/src/components/nexus/
├── plugin-marketplace.tsx  # 🔴 NOUVEAU
└── skill-hub.tsx           # 🔴 NOUVEAU — hub de skills communautaire
```

**Distribution** :
| Canal | Commande | Priorité |
|-------|----------|----------|
| PyPI | `pip install nexus-agent` | Haute |
| npm | `npm install -g nexus` | Haute |
| Homebrew | `brew install nexus` | Haute |
| Docker | `docker pull nexus/agent` | Haute |
| GitHub Releases | .exe / .dmg / .AppImage | ✅ Fait |

---

## 📊 Évaluation Finale

### NEXUS 2.0 vs Concurrents (après plan)

| Catégorie | NEXUS 1.0 | **NEXUS 2.0** | Hermes | OpenClaw | Bolt.diy |
|-----------|-----------|---------------|--------|----------|----------|
| **LLM** | ⭐8 providers | ⭐**20+ providers** | 200+ OR | 1 | 19+ |
| **Mémoire** | ⭐5 niveaux | ⭐**5 niveaux** | FTS5 | FTS5 | ❌ |
| **Orchestration** | ⭐3 moteurs | ⭐**3 moteurs + SA** | Simple | Simple | Simple |
| **Raisonnement** | ⭐ReAct+ToT+LATS | ⭐**+ Planning** | ReAct | ReAct | ❌ |
| **Channels** | 3 | ⭐**20+ canaux** | 5 | **23** | ❌ |
| **Self-Learning** | ❌ | ⭐**Oui** | **Oui** | ❌ | ❌ |
| **Cron** | ❌ | ⭐**Oui** | **Oui** | **Oui** | ❌ |
| **Avatar** | ⭐**Unique** | ⭐**+ Voice Wake** | ❌ | ❌ | ❌ |
| **Visual Builder** | ⭐**Unique** | ⭐**+ Live Canvas** | ❌ | ❌ | ❌ |
| **Code Gen** | Code Engine | ⭐**+ Preview + Diff** | ❌ | ❌ | **Oui** |
| **Sandbox** | ⭐Per-action | ⭐**+ Multi-terminal** | Session | Session | ❌ |
| **Computer Use** | ⭐**Unique** | ⭐**+ Remote Desktop** | ❌ | ❌ | ❌ |
| **Plugins** | ❌ | ⭐**Plugin System** | ❌ | **Oui** | ❌ |
| **Profiles** | L5 Identity | ⭐**Multi-profiles** | **Oui** | ❌ | ❌ |
| **Desktop** | Tauri+Next | ⭐**+ macOS/iOS** | TUI | macOS/iOS | Electron |
| **Free Providers** | ⭐**3** | ⭐**3** | ❌ | ❌ | ❌ |

> **Légende** : ⭐ = avantage, **Gras** = meilleur de sa catégorie

---

## ✅ Faisabilité Totale du Plan

| Phase | Faisabilité | Complexité | Dépendances |
|-------|-------------|------------|-------------|
| P2 — Multi-Channel | ✅ 95% | Moyenne | Bibliothèques Python pour chaque canal |
| P3 — Self-Learning | ✅ 85% | Haute | Analyse de trajectoire LLM |
| P4 — Cron | ✅ 99% | Très faible | APScheduler (déjà compatible) |
| P5 — Multi-Agent | ✅ 90% | Moyenne | Architecture existante |
| P6 — Voice Wake | ✅ 80% | Moyenne | Porcupine (gratuit 1h/jour) |
| P7 — Live Canvas | ✅ 85% | Moyenne | WebSocket + React (déjà présents) |
| P8 — Plugins | ✅ 95% | Faible | importlib + MCP (déjà présents) |
| P9 — Code Gen | ✅ 75% | Haute | Docker pour preview serveur |
| P10 — Profiles | ✅ 95% | Faible | Identity Memory existe |
| P11 — Community | ✅ 99% | Très faible | GitHub Actions |

**Conclusion : Tout est faisable.** Chaque composant a un équivalent open-source mature ou existe déjà dans NEXUS. Aucune rupture technologique nécessaire.

---

## 🔑 Différenciateurs Uniques (NEXUS seulement)

1. **Avatar waifu VRM + VOICEVOX** — aucun agent n'a ça
2. **Visual Flow Builder** — aucun agent n'a ça (React Flow)
3. **Computer Use** — aucun agent n'a ça (PyAutoGUI + OCR)
4. **Gemma 4 Thinking natif** — aucun agent n'a ça
5. **Free providers sans clé** — aucun agent n'a ça
6. **Per-action Docker sandbox** — aucun agent n'a ça
7. **Agent Activity View brique-par-brique** — aucun agent n'a ça
8. **Mémoire vectorielle 5 niveaux** — Hermes/OpenClaw ont FTS5 uniquement
9. **Orchestration 3 moteurs** — LangGraph + CrewAI + ADK
10. **Raisonnement 3 modes** — ReAct + ToT + LATS

---

## 🚀 Prochaine Action Recommandée

Commencer par **Phase 2 (Multi-Channel Gateway)** :
```bash
# Discord — le plus gros canal manquant
pip install discord.py

# WhatsApp
npm install whatsapp-web.js  # Bridge Node.js
```

Puis **Phase 4 (Cron Scheduler)** le plus simple et le plus visible :
```bash
pip install apscheduler
# ~50 lignes de code pour un scheduler complet
```
