# NEXUS Agent V2 — Installation & Démarrage

## Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Navigateur      │     │  Next.js 16      │     │  Backend Python  │
│  ou Tauri v2     │────▶│  Frontend        │────▶│  FastAPI         │
│  (port 3000)     │     │  /api/nexus/*    │     │  (port 8081)     │
└──────────────────┘     └──────────────────┘     └──────────────────┘
                              │                        │
                        VRM 3D Avatar              ChromaDB
                        Generative UI              LLM Router
                        Cmd+K / Cmd+,              28+ Tools
```

## Prérequis

- **Node.js** 18+ ou **Bun** 1.0+
- **Python** 3.11+
- **Rust** (optionnel, pour Tauri Desktop)

## 1. Backend (Python/FastAPI)

```bash
cd NexusAgent

# Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Installer les dépendances
pip install -r requirements.txt

# Configurer (ZhipuAI GLM-4-Flash = GRATUIT)
# Le fichier .env est déjà configuré avec la clé gratuite

# Lancer le backend
python -m nexus serve --port 8081
```

Le backend démarre sur http://localhost:8081
Documentation API : http://localhost:8081/docs

## 2. Frontend (Next.js 16)

```bash
# À la racine du projet (pas dans NexusAgent/)

# Installer les dépendances
bun install
# ou: npm install

# Lancer en développement
bun run dev
# ou: npm run dev
```

Le frontend démarre sur http://localhost:3000

## 3. Desktop Tauri v2 (optionnel)

```bash
# Installer Tauri CLI
cargo install tauri-cli

# Mode développement (lance Next.js + Tauri)
cargo tauri dev

# Build production
cargo tauri build
```

## Fonctionnalités V2

- **Chat-centrique** : Un seul point d'entrée, le chat. Pas de sidebar, pas de panneaux.
- **Avatar VRM 3D** : @pixiv/three-vrm + React Three Fiber (hologramme par défaut, modèle VRM chargeable)
- **Generative UI** : Les résultats (mémoire, web, code, build) s'affichent comme des cartes DANS le chat
- **Command Palette** : Cmd+K pour accéder à tout au clavier
- **Settings Popover** : Cmd+, pour les paramètres (provider, modèle, mode, avatar)
- **Tauri v2** : Remplace Electron (58% moins de RAM, 96% plus petit)
- **ZhipuAI GLM-4-Flash** : 100% gratuit, provider par défaut
- **WebSocket** : Événements temps réel (agent_thinking, tool_call, file_create, etc.)
- **API Proxy** : /api/nexus/* → http://127.0.0.1:8081/*

## Raccourcis

| Raccourci | Action |
|-----------|--------|
| ⌘K / Ctrl+K | Command Palette |
| ⌘, / Ctrl+, | Settings |
| Enter | Envoyer le message |
| Shift+Enter | Nouvelle ligne |

## Modes

- **Plan** : Lecture seule, l'agent analyse et propose
- **Build** : Accès complet, l'agent peut exécuter du code, créer des fichiers

## Providers LLM

| Provider | Coût | Modèles |
|----------|------|---------|
| ZhipuAI | **Gratuit** | glm-4-flash, glm-4.5-flash |
| Pollinations | **Gratuit** | openai |
| G4F | **Gratuit** | gpt-4 |
| OpenAI | Payant | gpt-4o |
| Anthropic | Payant | claude-sonnet-4 |
| Ollama | Local | llama3.1:8b |
