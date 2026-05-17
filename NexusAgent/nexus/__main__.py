"""
NEXUS — Point d'entrée principal.

Utilisation :
    python -m nexus serve    → Lance le serveur API (port 8081)
    python -m nexus chat     → Chat interactif CLI
    python -m nexus --help   → Aide
"""
from __future__ import annotations

import sys


def main():
    if len(sys.argv) > 1:
        from nexus.cli import app as cli_app
        cli_app()
    else:
        print("NEXUS — Agent IA Souverain")
        print()
        print("Utilisation :")
        print("  python install.py        → Installation complète")
        print("  python start.py          → Lance backend + frontend")
        print("  python -m nexus serve    → Lance le serveur API")
        print("  python -m nexus chat     → Chat interactif")
        print()


if __name__ == "__main__":
    main()
