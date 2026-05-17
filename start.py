#!/usr/bin/env python3
"""
NEXUS Agent — Universal Launcher
Starts both backend (Python) and frontend (Next.js) with one command.

Usage:
    python start.py
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    backend_dir = root / "NexusAgent"

    # Get venv python
    if sys.platform == "win32":
        venv_python = backend_dir / "venv" / "Scripts" / "python.exe"
    else:
        venv_python = backend_dir / "venv" / "bin" / "python"

    if not venv_python.exists():
        print("ERREUR: Environnement virtuel non trouve.")
        print("Lancez d'abord: python install.py")
        sys.exit(1)

    print()
    print("=" * 50)
    print("  NEXUS Agent — Demarrage")
    print("=" * 50)
    print()

    # Start backend
    print("[1/2] Demarrage du backend (port 8081)...")
    backend_proc = subprocess.Popen(
        [str(venv_python), "-m", "nexus", "serve", "--port", "8081"],
        cwd=str(backend_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for backend to start
    time.sleep(3)
    if backend_proc.poll() is not None:
        stderr = backend_proc.stderr.read().decode() if backend_proc.stderr else ""
        print(f"ERREUR: Le backend a echoue:\n{stderr[:500]}")
        sys.exit(1)
    print("  Backend demarre (PID: {})".format(backend_proc.pid))

    # Start frontend
    print("[2/2] Demarrage du frontend (port 3000)...")
    if shutil.which("bun"):
        frontend_cmd = ["bun", "dev"]
    else:
        frontend_cmd = ["npm", "run", "dev"]

    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    time.sleep(3)
    if frontend_proc.poll() is not None:
        stderr = frontend_proc.stderr.read().decode() if frontend_proc.stderr else ""
        print(f"ERREUR: Le frontend a echoue:\n{stderr[:500]}")
        backend_proc.terminate()
        sys.exit(1)
    print("  Frontend demarre (PID: {})".format(frontend_proc.pid))

    print()
    print("=" * 50)
    print("  NEXUS est pret !")
    print()
    print("  Frontend : http://localhost:3000")
    print("  Backend  : http://localhost:8081/docs")
    print()
    print("  Ctrl+C pour arreter")
    print("=" * 50)
    print()

    # Handle shutdown
    def shutdown(sig=None, frame=None):
        print("\nArret en cours...")
        backend_proc.terminate()
        frontend_proc.terminate()
        try:
            backend_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend_proc.kill()
        try:
            frontend_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            frontend_proc.kill()
        print("NEXUS arrete.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Wait for processes
    try:
        while True:
            if backend_proc.poll() is not None:
                print("ERREUR: Le backend s'est arrete.")
                frontend_proc.terminate()
                sys.exit(1)
            if frontend_proc.poll() is not None:
                print("ERREUR: Le frontend s'est arrete.")
                backend_proc.terminate()
                sys.exit(1)
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()


import shutil  # needed for shutil.which

if __name__ == "__main__":
    main()
