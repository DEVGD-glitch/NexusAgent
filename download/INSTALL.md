# NEXUS Agent V3 — Installation & Démarrage

## Architecture V3

```
┌─────────────────────────────────────────────────────────────────────┐
│  Navigateur ou Tauri v2                                             │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  Next.js 16 Frontend                                         │ │
│  │  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌───────────────┐  │ │
│  │  │ VRM 3D   │ │ ChatView  │ │ LiveViz  │ │ ArtifactPanel │  │ │
│  │  │ Avatar   │ │ (hub)     │ │ Panel    │ │ (rendering)   │  │ │
│  │  │ lip-sync │ │ + Voice   │ │ brique   │ │ HTML/Chart/   │  │ │
│  │  │ visemes  │ │ + GenUI   │ │ par      │ │ Image/Code    │  │ │
│  │  │ gaze     │ │ + HITL    │ │ brique   │ │               │  │ │
│  │  └──────────┘ └───────────┘ └──────────┘ └───────────────┘  │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                              │                                      │
│  Zustand Store + WebSocket   │  API Proxy /api/nexus/*             │
│  (viz events, visemes,      │                                      │
│   artifacts, voice)         │                                      │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
                    HTTP/SSE + WebSocket
                               │
┌──────────────────────────────┼──────────────────────────────────────┐
│  NexusAgent Backend (FastAPI, port 8081)                            │
│  ┌──────────┐ ┌──────────────┐ ┌────────────────────────────────┐ │
│  │ LLM      │ │ 5-LAYER      │ │ 35+ MCP Tools                  │ │
│  │ Router   │ │ MEMORY       │ │ (code, web, file, memory, KG,  │ │
│  │ (13 prov)│ │              │ │  agent, voice, viz, skills)    │ │
│  │          │ │ Working      │ └────────────────────────────────┘ │
│  │ Free:    │ │ Episodic     │ ┌────────────────────────────────┐ │
│  │ ZhipuAI  │ │ Semantic     │ │ Voice Pipeline                 │ │
│  │ Pollinat.│ │ Procedural   │ │ VAD + STT + TTS + LipSync      │ │
│  │ G4F      │ │ Identity     │ │ Edge TTS / VoiceVOX            │ │
│  │          │ │              │ └────────────────────────────────┘ │
│  │ Paid:    │ │ +Compactor   │ ┌────────────────────────────────┐ │
│  │ OpenAI   │ │ +Orchestrator│ │ Viz Events                     │ │
│  │ Anthropic│ │ +Crystallize │ │ Brick-by-brick streaming       │ │
│  │ Gemini   │ └──────────────┘ │ File tree + Diff + Artifacts   │ │
│  │ Ollama   │ ┌──────────────┐ └────────────────────────────────┘ │
│  └──────────┘ │ Orchestrator │ ┌────────────────────────────────┐ │
│               │ LangGraph    │ │ Agents                         │ │
│               │ CrewAI       │ │ Developer, Researcher,         │ │
│               │ ADK          │ │ Analyst, Operator              │ │
│               │ 6 Patterns   │ │ + OpenAI Agents SDK            │ │
│               └──────────────┘ └────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

## Nouveautés V3

| Feature | Description |
|---------|-------------|
| **Mémoire 5 couches** | Working → Episodic → Semantic → Procedural (skills) → Identity |
| **Skill Crystallization** | L'agent cristallise les stratégies réussies en skills réutilisables |
| **Visualisation Live** | Brique par brique — fichiers, code, diffs en temps réel |
| **Voice Pipeline** | VAD Silero + STT Whisper + TTS Edge/VoiceVOX + Lip-sync VRM |
| **Artifact Rendering** | HTML, charts, images, code rendus dans l'interface |
| **Environment Awareness** | L'agent connaît ses capacités, tools, skills, memory |
| **HITL Approvals** | Approbation humaine pour les actions sensibles |
| **Crons** | Tâches programmées récurrentes |
| **VRM Lip-Sync** | Visèmes A/I/U/E/O appliqués au modèle VRM |
| **Gaze Tracking** | L'avatar regarde vers le chat quand l'utilisateur tape |
| **CC0 Avatars** | Galerie d'avatars gratuits intégrée |
| **Conversation Persistence** | Sauvegarde localStorage automatique |

## Prérequis

- **Node.js** 18+ ou **Bun** 1.0+
- **Python** 3.11+
- **Rust** (optionnel, pour Tauri Desktop)

## 1. Backend (Python/FastAPI)

```bash
cd NexusAgent
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# Optionnel — pour la voice pipeline:
pip install edge-tts silero-vad

# Lancer le backend
python -m nexus serve --port 8081
```

## 2. Frontend (Next.js 16)

```bash
bun install
bun run dev
```

## 3. Desktop Tauri v2

```bash
cargo install tauri-cli
cargo tauri dev
```

## Raccourcis

| Raccourci | Action |
|-----------|--------|
| ⌘K / Ctrl+K | Command Palette |
| ⌘, / Ctrl+, | Settings |
| Enter | Envoyer |
| Shift+Enter | Nouvelle ligne |
| 🎤 | Voice input |

## Modes Agent

| Mode | Description |
|------|-------------|
| Chat | Conversation normale |
| Plan | Lecture seule, analyse |
| Build | Accès complet, écriture de code |
| Research | Recherche web profonde |
| Review | Audit de code/architecture |

## Providers LLM

| Provider | Coût | Modèles |
|----------|------|---------|
| ZhipuAI | **Gratuit** | glm-4-flash, glm-4.5-flash |
| Pollinations | **Gratuit** | openai |
| G4F | **Gratuit** | gpt-4 |
| OpenAI | Payant | gpt-4o |
| Anthropic | Payant | claude-sonnet-4 |
| Ollama | Local | llama3.1:8b |
