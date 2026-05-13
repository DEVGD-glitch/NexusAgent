#!/usr/bin/env bash
set -euo pipefail

NEXUS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "╔══════════════════════════════════════╗"
echo "║     NEXUS — One-Click Installer      ║"
echo "╚══════════════════════════════════════╝"
echo ""

# 1. Python
if command -v python3 &>/dev/null; then
    echo "Python : $(python3 --version)"
else
    echo "Python introuvable. Installez Python 3.11+ depuis python.org"
    exit 1
fi

# 2. Node.js
if command -v node &>/dev/null; then
    echo "Node.js : $(node --version)"
else
    echo "Node.js introuvable. Installez Node.js 20+ depuis nodejs.org"
    exit 1
fi

# 3. Venv
echo ""
echo "Installation des dependances Python..."
python3 -m venv "$NEXUS_DIR/venv"
source "$NEXUS_DIR/venv/bin/activate"
pip install -q -r "$NEXUS_DIR/requirements.txt"
pip install -q -e "$NEXUS_DIR"

# 4. Frontend
echo "Installation du frontend..."
cd "$NEXUS_DIR/nexus-web"
npm install --no-fund --no-audit --silent 2>/dev/null
cd "$NEXUS_DIR"

# 5. .env
if [ ! -f "$NEXUS_DIR/.env" ]; then
    cp "$NEXUS_DIR/.env.example" "$NEXUS_DIR/.env"
    echo ".env cree. Configure tes cles API."
fi

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   NEXUS pret !                       ║"
echo "║                                      ║"
echo "║   Lance : ./start_web.sh             ║"
echo "╚══════════════════════════════════════╝"
echo ""
