# 📦 Guide d'Installation Complet — NEXUSAgent

> Installation détaillée pour Windows, macOS, Linux et Docker.

---

## 📋 Prérequis

| Composant | Version minimale | Recommandée |
|-----------|-----------------|-------------|
| Python | 3.11+ | 3.12 |
| Node.js | 18+ | 22 (LTS) |
| Bun ou npm | Bun 1.0+ ou npm 9+ | Bun 1.1+ |
| Git | 2.30+ | Dernière version |
| Docker | 24+ (optionnel) | Dernière version |
| Docker Compose | 2.20+ (optionnel) | Dernière version |

---

## 🪟 Installation sur Windows

### Méthode 1 : Script automatique (recommandé)

```powershell
# Cloner le dépôt
git clone https://github.com/YOUR_USERNAME/NexusAgent.git
cd NexusAgent

# Exécuter le script d'installation
install.bat
```

Le script `install.bat` effectue automatiquement :
- Vérification de Python 3.11+
- Création d'un environnement virtuel `.venv`
- Installation des dépendances Python
- Vérification des packages critiques
- Installation des dépendances Node.js pour le frontend
- Création du fichier `.env` depuis `.env.example`

### Méthode 2 : Installation manuelle

```powershell
# 1. Cloner
git clone https://github.com/YOUR_USERNAME/NexusAgent.git
cd NexusAgent

# 2. Créer l'environnement virtuel
python -m venv .venv
.venv\Scripts\activate

# 3. Installer les dépendances Python
pip install --upgrade pip
pip install -e ".[dev]"

# 4. Installer les extensions optionnelles (au choix)
pip install -e ".[browser]"    # Playwright + browser-use
pip install -e ".[desktop]"    # Application bureau customtkinter
pip install -e ".[avatar]"     # Avatar VRM + VOICEVOX
pip install -e ".[multiagent]" # CrewAI + Google ADK + OpenAI Agents

# 5. Installer le frontend
cd nexus-web
npm install
cd ..

# 6. Configurer
copy .env.example .env
notepad .env
```

### Installation PowerShell avancée

```powershell
# Utiliser le script PowerShell avancé
.\INSTALL.ps1

# Ou avec paramètres
.\INSTALL.ps1 -PythonPath "C:\Python312" -SkipFrontend
```

---

## 🍎 Installation sur macOS

### Méthode 1 : Script automatique

```bash
# Cloner
git clone https://github.com/YOUR_USERNAME/NexusAgent.git
cd NexusAgent

# Rendre le script exécutable
chmod +x install.sh

# Exécuter
./install.sh
```

### Méthode 2 : Installation manuelle avec Homebrew

```bash
# 1. Installer les prérequis (si pas déjà installés)
brew install python@3.12
brew install node@22
brew install bun

# 2. Cloner
git clone https://github.com/YOUR_USERNAME/NexusAgent.git
cd NexusAgent

# 3. Environnement virtuel
python3.12 -m venv .venv
source .venv/bin/activate

# 4. Dépendances Python
pip install --upgrade pip
pip install -e ".[dev]"

# 5. Frontend
cd nexus-web
bun install
cd ..

# 6. Configuration
cp .env.example .env
nano .env
```

### Note pour macOS Apple Silicon (M1/M2/M3/M4)

ChromaDB est compatible ARM64 natif depuis la version 0.4.0+. Aucune configuration spéciale n'est requise. Si vous rencontrez des problèmes avec des dépendances C :

```bash
# Installer les outils de compilation
xcode-select --install

# Si problème avec ChromaDB
pip install chromadb --no-binary :all:
```

---

## 🐧 Installation sur Linux

### Ubuntu / Debian

```bash
# 1. Prérequis système
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip nodejs npm git

# 2. Cloner
git clone https://github.com/YOUR_USERNAME/NexusAgent.git
cd NexusAgent

# 3. Environnement virtuel
python3.12 -m venv .venv
source .venv/bin/activate

# 4. Dépendances Python
pip install --upgrade pip
pip install -e ".[dev]"

# 5. Frontend
cd nexus-web
npm install
cd ..

# 6. Configuration
cp .env.example .env
nano .env
```

### Fedora / RHEL

```bash
# Prérequis
sudo dnf install -y python3.12 python3.12-pip nodejs npm git

# Suite identique à Ubuntu...
```

### Arch Linux

```bash
# Prérequis
sudo pacman -S python python-pip nodejs npm git

# Suite identique...
```

### Installation avec script automatique

```bash
chmod +x install.sh
./install.sh
```

---

## 🐳 Installation avec Docker

Docker est la méthode recommandée pour un déploiement en production.

### Stack complète avec Docker Compose

```bash
# 1. Cloner
git clone https://github.com/YOUR_USERNAME/NexusAgent.git
cd NexusAgent

# 2. Configurer
cp .env.example .env
# Éditer .env avec vos clés API

# 3. Lancer la stack
docker-compose up -d

# 4. Vérifier les services
docker-compose ps
```

### Services Docker

| Service | Port | Description |
|---------|------|-------------|
| `nexus-core` | 8080 | API backend FastAPI |
| `chromadb` | 8000 | Base de données vectorielle |
| `browser-service` | 8001 | Service de navigateur isolé |

### Construction manuelle des images

```bash
# Image backend
docker build -t nexus-agent:latest -f docker/Dockerfile.core .

# Image browser service
docker build -t nexus-browser:latest -f docker/Dockerfile.browser .

# Lancer
docker run -d \
  --name nexus \
  -p 8080:8080 \
  -e GOOGLE_API_KEY=your-key \
  -v nexus-data:/app/nexus_data \
  nexus-agent:latest
```

### Docker Compose — Configuration avancée

```yaml
# docker-compose.override.yml pour personnaliser
version: "3.9"
services:
  nexus-core:
    environment:
      - NEXUS_ENV=production
      - NEXUS_SECRET_KEY=your-secure-random-key
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./nexus_data:/app/nexus_data
```

---

## 🎮 Démarrage après installation

### Mode CLI (Terminal)

```bash
# Activer l'environnement virtuel (si pas déjà fait)
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Chat interactif
python -m nexus chat

# Lancer le serveur API
python -m nexus serve

# Vérification
python verify_install.py
```

### Mode Web (Navigateur)

```bash
# Windows
start_web.bat

# Linux/macOS
./start_web.sh

# Ou manuellement :
# Terminal 1 — Backend
python -m nexus serve

# Terminal 2 — Frontend
cd nexus-web
npm run dev
# Ouvrir http://localhost:3000
```

### Mode Bureau (Electron)

```bash
cd nexus-desktop
npm install
npm start
```

---

## 🔧 Résolution des problèmes

### Python non trouvé

```bash
# Vérifier la version
python --version    # Doit être 3.11+

# Sur Ubuntu, python3 peut être requis
python3 --version
python3 -m venv .venv
```

### Erreur pip avec ChromaDB

```bash
# Sur某些 systèmes, ChromaDB peut nécessiter des dépendances C
sudo apt install -y build-essential python3-dev  # Ubuntu/Debian

# Installation isolée
pip install chromadb --no-cache-dir
```

### Erreur Node.js / npm

```bash
# Mettre à jour npm
npm install -g npm@latest

# Utiliser Bun à la place
curl -fsSL https://bun.sh/install | bash
cd nexus-web && bun install
```

### Port 8080 déjà utilisé

```bash
# Changer le port dans .env
NEXUS_PORT=8081

# Ou tuer le processus existant
lsof -i :8080      # Linux/macOS
netstat -ano | findstr :8080  # Windows
```

### Problème de permissions (Linux/macOS)

```bash
chmod +x install.sh start_web.sh start.sh
```

### Docker — Erreur de build

```bash
# Rebuild sans cache
docker-compose build --no-cache

# Vérifier les logs
docker-compose logs nexus-core
```

---

## 📦 Extensions optionnelles

| Extension | Installation | Description |
|-----------|-------------|-------------|
| `browser` | `pip install -e ".[browser]"` | Playwright, browser-use, screenshots |
| `desktop` | `pip install -e ".[desktop]"` | Application bureau customtkinter |
| `avatar` | `pip install -e ".[avatar]"` | Avatar VRM, VOICEVOX, lip-sync |
| `multiagent` | `pip install -e ".[multiagent]"` | CrewAI, Google ADK, OpenAI Agents |
| `dev` | `pip install -e ".[dev]"` | pytest, ruff, mypy, httpx |

Toutes les extensions :

```bash
pip install -e ".[dev,browser,desktop,avatar,multiagent]"
```

---

## ✅ Vérification de l'installation

```bash
# Script de vérification automatique
python verify_install.py

# Vérification manuelle
python -c "import nexus; print(f'NEXUS v{nexus.__version__}')"
python -c "from nexus.llm.router import LLMRouter; print('LLM Router OK')"
python -c "from nexus.memory.chroma_service import NexusMemoryService; print('Memory OK')"
python -c "from nexus.mcp_server import nexus_mcp; print('MCP Server OK')"
```

---

## 🔄 Mise à jour

```bash
# Récupérer les dernières modifications
git pull origin main

# Mettre à jour les dépendances Python
pip install -e ".[dev]"

# Mettre à jour le frontend
cd nexus-web && npm install && cd ..

# Mettre à jour le bureau
cd nexus-desktop && npm install && cd ..
```
