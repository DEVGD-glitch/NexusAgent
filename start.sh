#!/usr/bin/env bash
set -euo pipefail

NEXUS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  NEXUS v3 — Agent IA Souverain                                   ║"
echo "║  Agent Command Center + Code Workspace + Avatar VRM             ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# Activer venv
if [ -f "$NEXUS_DIR/venv/bin/activate" ]; then
    source "$NEXUS_DIR/venv/bin/activate"
fi

# Backend
echo "  [INFO] Lancement du backend (port 8081)..."
cd "$NEXUS_DIR"
python -m nexus serve --port 8081 &
BACKEND_PID=$!
echo "  [OK] Backend PID $BACKEND_PID sur :8081"

# Frontend
echo "  [INFO] Lancement du frontend (port 3000)..."
cd "$NEXUS_DIR/nexus-web"
npm run dev &
FRONTEND_PID=$!
echo "  [OK] Frontend PID $FRONTEND_PID sur :3000"

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

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo ''; echo 'NEXUS arrete.'; exit" INT TERM
wait
