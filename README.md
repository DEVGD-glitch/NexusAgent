<div align="center">

# 🧠 NEXUS

### Ton Agent IA Souverain — **Zéro Cloud. Zéro Compromis.**

Un agent IA personnel qui vit sur **ton PC**. Pas de cloud imposé, pas de compte obligatoire, pas de données qui fuient. Tu choisis tes modèles, tes clés, tes permissions.

[![License: MIT](https://img.shields.io/badge/License-MIT-emerald?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&style=flat-square)]()
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-0078D6?style=flat-square)]()
[![Tests](https://img.shields.io/badge/Tests-40%20%E2%9C%85%20%E2%80%94%2022k%2B%20lignes-22c55e?style=flat-square)]()
[![Code](https://img.shields.io/badge/Code-30k%20lignes-8b5cf6?style=flat-square)]()

[📥 Installer](#-installer) · [🚀 Démarrer](#-démarrer) · [🎯 Features](#-features) · [📖 Docs](docs/) · [🤝 Contribuer](CONTRIBUTING.md)

</div>

---

## 📥 Installer

```bash
# One-click (Windows) — tout s'installe automatiquement
git clone https://github.com/YOUR_USERNAME/nexus.git
cd nexus
install.bat
```

**Ou télécharge** l'installateur depuis [Releases](https://github.com/YOUR_USERNAME/nexus/releases) :

| Platforme | Installateur |
|-----------|-------------|
| 🪟 Windows | `NEXUS-Setup-x64.exe` |
| 🍎 macOS   | `NEXUS-x64.dmg` |
| 🐧 Linux   | `NEXUS-x86_64.AppImage` |

> Aucune dépendance manuelle. Python, Node.js, VOICEVOX — tout est géré.

---

## 🚀 Démarrer

```bash
# 1. Copie la config
cp .env.example .env
# 2. Ajoute ta clé API (au moins un provider)
# 3. Lance
python -m nexus
```

Ou en mode **web desktop** (recommendé) :

```bash
# Lance l'app web + backend en un clic
start_web.bat
# Ouvre http://localhost:3000
```

---

## 🎯 Features

### 🧠 Multi-LLM — 8 Providers
| Provider | Gratuit ? | Modèles |
|----------|-----------|---------|
| **Pollinations.ai** 🆓 | ✅ Sans clé | 29 modèles (GPT, Claude, Gemini, DeepSeek...) |
| **G4F.dev** 🆓 | ✅ Sans clé | 200+ modèles (Llama 4, Qwen, Mistral, Grok...) |
| **DeepInfra** 🆓 | ✅ Sans clé | Llama 4, Qwen 3, DeepSeek V3 |
| OpenAI | ❌ Clé API | GPT-4o, GPT-4o-mini, o1, o3 |
| Anthropic | ❌ Clé API | Claude 3.5/4 Sonnet, Opus |
| Google Gemini | ❌ Clé API | Gemini 2.5 Pro, Flash — **Gemma 4** (+thinking) |
| GLM / ZAI | ❌ Clé API | GLM-5, GLM-4 |
| Ollama (local) | ✅ Local | Llama, Mistral, CodeLlama... |

### 🗃️ Mémoire 5 Niveaux
| Niveau | Type | Usage |
|--------|------|-------|
| L1 | Working | Contexte de session, compression automatique |
| L2 | Episodic | Journal d'expériences |
| L3 | Semantic | Faits et connaissances structurés |
| L4 | Procedural | Compétences cristallisées |
| L5 | Identity | Profil utilisateur, préférences |

### 🎯 Orchestration & Raisonnement
- **3 moteurs** : LangGraph (plan-execute-reflect), CrewAI (collaboratif), Google ADK
- **6 patterns** : Pipeline, Parallel, Supervisor, Swarm, Routage, Skills
- **3 modes de raisonnement** : ReAct, Tree-of-Thought, LATS (MCTS)
- **5 agents spécialisés** : General, Researcher, Developer, Analyst, Operator

### 🛡️ Sécurité & Souveraineté
- **Mode permissions** : Auto-approuve ou confirmation manuelle
- **Sandbox** : Exécution de code isolée (local + Docker)
- **Audit trail** : Toutes les actions sont tracées
- **Vault** : Stockage chiffré des secrets
- **Guardrails** : Protection contre les injections

### 🥰 Avatar Waifu VRM
- Avatar 3D anime avec **VOICEVOX** (100+ voix japonaises)
- **Lip-sync** audio → visèmes en temps réel
- **Expressions faciales** détectées dans les réponses LLM
- Support VRM / VRoidHub — charge tes propres modèles
- Bridge **VRChat** via OSC
- Pipeline STS complet : VAD → STT → NEXUS LLM → TTS → VRM

### 🖥️ Visual Flow Builder
- Construis des workflows agent en **drag-and-drop**
- 6 types de noeuds : LLM, Memory, Code, Web, Agent, Knowledge
- Export JSON → exécution backend
- Mode texte **et** mode visuel

### 🔧 Dev & Computer Use
- **Code Engine** : Génération, review, refactoring, exécution sandboxée
- **Browser** : Playwright automatisé, screenshots, scraping
- **Computer Use** : Contrôle GUI (pyautogui), OCR, vision
- **Git** : Commits, PRs, review intégrés
- **Terminal** : Shell autonome

### 💬 Communications
- Telegram Bot, Voice I/O, Email/Calendar, Channels
- **MCP Protocol** : 50+ outils, 14 catégories, interface universelle
- **A2A Protocol** : Communication inter-agents

### 📊 Interface Complète
| Vue | Description |
|-----|------------|
| 💬 **Chat** | Conversation markdown avec streaming temps réel |
| 📋 **Tasks** | Mode texte + **Visual Flow Builder** |
| 🧠 **Memory** | Navigation 5-niveaux avec stats |
| 🔗 **Knowledge** | Graphe de connaissances, RAG, deep research |
| 🤖 **Agents** | Spawn, monitor, delegate |
| 🛠️ **Tools** | Catalogue des 50+ outils MCP |
| 💻 **Code** | Éditeur + terminal sandboxé |
| 🛡️ **Security** | Audit, permissions, vault |
| 📊 **Status** | Santé, providers, métriques |
| ⚙️ **Settings** | Providers, modèles, API keys |

---

## 🏗️ Architecture

```
30 000+ lignes Python · 22 000+ lignes de tests · 110+ fichiers · 22 modules
```

| Module | Rôle |
|--------|------|
| `core/` | Config, DI, Gateway, A2A, Evaluation |
| `llm/` | Routeur + 8 providers + hub gratuit 🆓 |
| `memory/` | 5 niveaux ChromaDB |
| `orchestrator/` | 3 moteurs + 6 patterns |
| `reasoning/` | ReAct, ToT, LATS |
| `agents/` | 5 types + OpenAI Agents SDK |
| `security/` | Sandbox, Docker, Vault, Guardrails |
| `knowledge/` | RAG + Graphe + Deep Research |
| `dev/` | Code, Terminal, Git, Deploy |
| `computer/` | GUI + Screen + Process |
| `comms/` | Telegram, Voice, **Avatar** 🆕 |
| `mcp_tools/` | 50+ outils, 14 catégories |
| `nexus-web/` | Next.js 16 + shadcn/ui + React Flow 🆕 |

---

## 📊 Tests

```bash
# 40 tests d'acceptance — prêts à l'emploi
pytest tests/test_user_acceptance.py -v

# Suite complète
pytest tests/ -v

# Couverture
pytest --cov=nexus --cov-report=html
```

---

## 📖 Documentation

| Ressource | Description |
|-----------|------------|
| [`PLAN.md`](PLAN.md) | Plan directeur — 100% vision |
| [`AGENTS.md`](AGENTS.md) | Instructions pour IA agents |
| `docs/` | Documentation technique |
| `NEXUS_Guide_Complet.pdf` | Guide utilisateur (vision) |
| `NEXUS_Architecture_Plan.pdf` | Architecture plan (vision) |

---

## 🔑 API Keys

| Provider | Obtenir une clé |
|----------|----------------|
| OpenAI | https://platform.openai.com/api-keys |
| Anthropic | https://console.anthropic.com |
| Google Gemini | https://aistudio.google.com |
| Zhipu / GLM | https://open.bigmodel.cn |
| **Pollinations** 🆓 | ✅ **Aucune clé nécessaire** |
| **G4F** 🆓 | ✅ **Aucune clé nécessaire** |
| **DeepInfra** 🆓 | ✅ **Aucune clé nécessaire** |
| Ollama | Installation locale (gratuit) |

---

## 📜 License

MIT — voir [`LICENSE`](LICENSE)

---

**NEXUS** — *Sovereign AI for everyone.*
