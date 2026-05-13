# NEXUS — Guide d'Installation Windows

## Prérequis

1. **Python 3.11+** : https://www.python.org/downloads/
   - Cochez "Add Python to PATH" pendant l'installation
2. **Node.js 18+** (pour l'app web) : https://nodejs.org/
   - Version LTS recommandée

## Installation Rapide

### Mode App Web (Recommandé)

Un seul script installe et lance tout :

```batch
start_web.bat
```

Ce script fait TOUT automatiquement :
1. Vérifie Python 3.11+ et Node.js 18+
2. Crée l'environnement virtuel si nécessaire
3. Installe les dépendances Python si nécessaire
4. Installe les dépendances npm si nécessaire
5. Lance le backend FastAPI sur le port 8080 (terminal dédié)
6. Lance le frontend Next.js sur le port 3000 (terminal dédié)
7. Ouvre votre navigateur sur http://localhost:3000

Deux terminaux s'ouvrent automatiquement :
- **Terminal Backend** : Affiche les logs du serveur FastAPI
- **Terminal Frontend** : Affiche les logs du serveur Next.js

Pour arrêter, fermez simplement les terminaux.

### Mode Desktop Windows

Pour installer et construire l'exécutable Windows :

```batch
install_build.bat
```

Ce script fait TOUT automatiquement :
1. Vérifie Python 3.11+
2. Crée l'environnement virtuel `venv/`
3. Installe toutes les dépendances Python
4. Installe NEXUS en mode développement
5. Crée le fichier `.env` depuis `.env.example`
6. Vérifie l'installation (imports, modules critiques)
7. Lance les tests
8. Build l'exécutable `NEXUS.exe` avec PyInstaller

Après le build, l'exécutable se trouve dans `dist\NEXUS.exe`.

Pour installer sans build :
```batch
install_build.bat --no-build
```

### Mode Backend Uniquement

Pour lancer uniquement le serveur API (sans interface graphique) :

```batch
start_nexus.bat
```

Puis accédez à la documentation API sur http://localhost:8080/docs.

## Configuration des Clés API

Éditez le fichier `.env` dans le dossier `nexus-workspace/` :

```env
# Fournisseurs LLM — décommentez et remplissez ceux que vous utilisez
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
ZAI_API_KEY=...

# Ollama (local — pas de clé nécessaire)
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

**Ollama** fonctionne sans clé API. Installez-le depuis https://ollama.com/ et lancez `ollama serve` avant d'utiliser NEXUS.

## Utilisation de l'App Web

1. **Premier lancement** : L'onboarding wizard vous guide en 4 étapes
   - Bienvenue — Présentation de NEXUS
   - Fournisseurs — Choix des providers LLM (Ollama coché par défaut)
   - Clés API — Saisie des clés pour les providers sélectionnés
   - Lancement — Confirmation et démarrage
2. **Chat** : Tapez un message, NEXUS répond via le provider choisi
3. **Tâches** : Décrivez une tâche complexe, l'agent l'exécute via Plan-Execute-Reflect
4. **Code** : Écrivez du code et exécutez-le en sandbox
5. **Mémoire** : Stockez et recherchez des informations dans 6 namespaces
6. **Agents** : Lancez des sous-agents avec orchestration (pipeline, parallel, supervisor, swarm)
7. **Knowledge** : Explorez le Knowledge Graph (entités, relations, chemins)
8. **Tools** : Naviguez les 46 outils MCP par catégorie
9. **Sécurité** : Consultez l'audit log et gérez les permissions
10. **Settings** : Changez de provider, ajoutez des clés, modifiez les permissions

## Mode Auto-approuve vs Confirmation

- **🔓 Auto-approuve** : L'agent fonctionne librement. Il demande confirmation uniquement pour les actions dangereuses (suppression, exécution de code, accès système, écriture de fichiers).
- **🔒 Confirmation** : L'agent demande votre accord pour toute action importante.

Changez de mode à tout moment dans l'onglet **Settings** ou via le badge en bas de la sidebar.

**Actions toujours bloquées en auto-approuve** :
- `delete_file` — Suppression de fichiers
- `execute_code` — Exécution de code
- `write_file` — Écriture de fichiers
- `install_package` — Installation de paquets
- Accès aux chemins système (C:\Windows, Program Files, etc.)

## Architecture

```
[Next.js Frontend :3000]  ←→  [FastAPI Backend :8080]  ←→  [LLM Providers]
        ↓                            ↓                          ↓
   Navigateur Utilisateur     NEXUS Core Engine          OpenAI/Anthropic/
   Chat, Tâches,              Mémoire, Agents,            Gemini/GLM/Ollama
   Settings                   Knowledge, Code
```

## Scripts Disponibles

| Script | Description |
|--------|-------------|
| `start_web.bat` | Lance l'app web complète (backend + frontend) |
| `install_build.bat` | Installation complète + build .exe Windows |
| `install_build.bat --no-build` | Installation sans build |
| `start_nexus.bat` | Lance uniquement le backend FastAPI |
| `download_wheels.bat` | Télécharge les wheels pour installation hors-ligne |
| `verify_install.py` | Vérification complète de l'installation |

## Dépannage

| Problème | Solution |
|----------|----------|
| "Backend non disponible" | Lancez `start_web.bat` ou `start_nexus.bat` en premier |
| "Clé API invalide" | Vérifiez votre fichier `.env` |
| "Ollama non connecté" | Lancez `ollama serve` dans un terminal |
| Port 8080 occupé | Changez le port dans `.env` : `NEXUS_PORT=8081` |
| Port 3000 occupé | Arrêtez les autres apps utilisant ce port |
| "node_modules not found" | Le script `start_web.bat` les installe automatiquement |
| Build PyInstaller échoué | Vérifiez que PyInstaller est installé : `pip install pyinstaller` |
| Erreur d'import ChromaDB | Normal si pas de serveur ChromaDB — les fonctionnalités mémoire sont limitées |
| "Python not found" | Installez Python 3.11+ et cochez "Add to PATH" |

## Structure du Projet

```
nexus-workspace/
├── nexus/                     → Code Python NEXUS
│   ├── api/gateway.py         → FastAPI Gateway (22+ endpoints)
│   ├── core/gateway.py        → FastAPI Gateway simple (6 endpoints)
│   ├── llm/router.py          → Routeur multi-LLM
│   ├── memory/                → Mémoire ChromaDB (5 niveaux)
│   ├── knowledge/             → Knowledge Graph
│   ├── orchestrator/          → Plan-Execute-Reflect
│   ├── agents/                → Sous-agents
│   ├── dev/                   → Code executor
│   ├── security/              → Sandbox + Audit + Permissions
│   ├── desktop/app.py         → App desktop Tkinter
│   └── core/                  → Config, Registry, A2A
├── nexus-web/                 → Frontend Next.js
│   ├── src/components/nexus/  → 12 panneaux fonctionnels
│   ├── src/lib/               → API client, Zustand store
│   ├── src/hooks/             → WebSocket, toast, mobile
│   └── mini-services/         → Service WebSocket streaming
├── tests/                     → 167 tests
├── docs/                      → Documentation phases
├── run_nexus.py               → Lanceur backend
├── install_build.bat          → Installation + build Windows
├── start_web.bat              → Lancement app web (multi-terminales)
├── start_nexus.bat            → Lancement backend uniquement
├── download_wheels.bat        → Wheels hors-ligne
└── pyproject.toml             → Dépendances Python
```
