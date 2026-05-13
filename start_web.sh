#!/bin/bash
set -euo pipefail

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  NEXUS v3 — Agent IA Souverain                                   ║"
echo "║  Agent Command Center + Code Workspace + Avatar VRM             ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

NEXUS_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Vérifier venv ──
if [ ! -f "$NEXUS_DIR/venv/bin/python" ]; then
    echo " [*] Installation des dependances Python..."
    cd "$NEXUS_DIR"
    python3 -m venv venv
    source venv/bin/activate
    pip install -q -r requirements.txt
    pip install -q -e .
else
    source venv/bin/activate
fi

# ── Vérifier Node.js ──
if ! command -v node &> /dev/null; then
    echo " [ECHEC] Node.js n'est pas installe."
    echo " Installez Node.js 18+ depuis https://nodejs.org/"
    exit 1
fi

# ── Config .env ──
if [ ! -f "$NEXUS_DIR/.env" ]; then
    cp "$NEXUS_DIR/.env.example" "$NEXUS_DIR/.env"
    echo " [!] Fichier .env cree. Editez-le pour ajouter vos cles API."
fi

# ── Backend ──
echo " [INFO] Lancement du backend (port 8081)..."
cd "$NEXUS_DIR"
python -m nexus serve --port 8081 &
BACKEND_PID=$!
sleep 4

# ── Frontend ──
echo " [INFO] Lancement du frontend (port 3000)..."
cd "$NEXUS_DIR/nexus-web"
npm install --no-fund --no-audit --silent 2>/dev/null
npm run dev &
FRONTEND_PID=$!
sleep 5

# ── Browser ──
if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:3000
elif command -v open &> /dev/null; then
    open http://localhost:3000
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  NEXUS v3 est en cours d'execution !                             ║"
echo "║                                                                  ║"
echo "║  Frontend : http://localhost:3000                                  ║"
echo "║  Backend  : http://localhost:8081/docs                             ║"
echo "║                                                                  ║"
echo "║  Ctrl+C pour arreter.                                             ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

cleanup() {
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    echo ""
    echo " NEXUS v3 arrete."
    exit 0
}
trap cleanup SIGINT SIGTERM
wait
