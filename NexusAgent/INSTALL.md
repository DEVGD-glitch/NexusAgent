# 📥 Installer NEXUS

## One-Click Install (Windows)

```powershell
# Ouvre PowerShell et colle :
iwr -Uri https://raw.githubusercontent.com/YOUR_USERNAME/nexus/main/install.ps1 -OutFile install.ps1
.\install.ps1
```

Ou clone manuellement :

```bash
git clone https://github.com/YOUR_USERNAME/nexus.git
cd nexus
install.bat        # Windows
# ou
chmod +x install.sh && ./install.sh   # macOS / Linux
```

L'installateur détecte automatiquement :
- ✅ Python 3.11+ (télécharge si absent)
- ✅ Node.js 20+ (pour le frontend)
- ✅ ChromaDB (intégré)
- ✅ VOICEVOX (optionnel, pour l'avatar)
- ✅ Crée le `.env` interactif
- ✅ Installe les dépendances Python
- ✅ Build le frontend

---

## Installation Manuelle

### Prérequis

| Dépendance | Minimum | Vérifier |
|-----------|---------|----------|
| Python | 3.11+ | `python --version` |
| pip | 24+ | `pip --version` |
| Node.js | 20+ | `node --version` |
| npm | 10+ | `npm --version` |

### Backend Python

```bash
# Créer l'environnement
python -m venv .venv
.venv\Scripts\activate   # Windows
source .venv/bin/activate # macOS/Linux

# Installer
pip install -e .
pip install -r requirements.txt

# Optionnel : avatar waifu
pip install aiavatar
```

### Frontend Web

```bash
cd nexus-web
npm install
npm run build
```

### Config

```bash
cp .env.example .env
# Éditer .env avec tes clés API
```

### Démarrer

```bash
# Mode CLI
python -m nexus chat

# Mode Web (recommendé)
start_web.bat   # Windows
npm run dev     # Dans nexus-web/
```

---

## Télécharger l'Installateur

| Platforme | Fichier |
|-----------|---------|
| 🪟 Windows | `NEXUS-Setup-x64.exe` |
| 🍎 macOS Intel | `NEXUS-x64.dmg` |
| 🍎 macOS Apple Silicon | `NEXUS-arm64.dmg` |
| 🐧 Linux (deb) | `NEXUS-amd64.deb` |
| 🐧 Linux (AppImage) | `NEXUS-x86_64.AppImage` |

Les builds sont disponibles dans **[Releases](https://github.com/YOUR_USERNAME/nexus/releases)**.

---

## VOICEVOX (Pour l'Avatar)

L'avatar anime nécessite VOICEVOX pour la synthèse vocale japonaise :

1. Télécharge depuis https://voicevox.hiroshiba.jp
2. Lance VOICEVOX
3. NEXUS détecte automatiquement `http://127.0.0.1:50021`

---

## Dépannage

| Problème | Solution |
|----------|----------|
| `pip install` échoue | `python -m pip install --upgrade pip` |
| Port 3000 occupé | `$env:PORT=3001` avant `npm run dev` |
| ChromaDB erreur | Vérifie que `CHROMA_PERSIST_DIR=./nexus_data/chroma` |
| Ollama pas trouvé | `ollama serve` dans un terminal séparé |
| VOICEVOX pas trouvé | Lance VOICEVOX manuellement avant NEXUS |
