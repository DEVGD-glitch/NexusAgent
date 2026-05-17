#!/usr/bin/env python3
"""
NEXUS Agent — Universal Launcher
Starts both backend (Python) and frontend (Next.js) with one command.

Usage:
    python start.py
"""

import os
import signal
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path


def check_port_available(port: int) -> bool:
    """Check if a port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) != 0


def wait_for_health(url: str, timeout: int = 30) -> bool:
    """Wait for a service to respond to health checks."""
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(url, method='HEAD')
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def read_stream(pipe, prefix: str):
    """Read from a pipe and print with prefix."""
    for line in iter(pipe.readline, ''):
        print(f"{prefix} {line.rstrip()}")


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

    # Check port availability
    if not check_port_available(8081):
        print("ERREUR: Le port 8081 est deja utilise.")
        print("Arretez le processus existant ou changez le port.")
        sys.exit(1)

    if not check_port_available(3000):
        print("ERREUR: Le port 3000 est deja utilise.")
        print("Arretez le processus existant ou changez le port.")
        sys.exit(1)

    # Start backend
    print("[1/2] Demarrage du backend (port 8081)...")
    backend_proc = subprocess.Popen(
        [str(venv_python), "-m", "nexus", "serve", "--port", "8081"],
        cwd=str(backend_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    # Wait for backend to be healthy
    if wait_for_health("http://localhost:8081/health", timeout=30):
        print("  Backend demarre et pret (PID: {})".format(backend_proc.pid))
    else:
        stderr = backend_proc.stderr.read() if backend_proc.stderr else ""
        print(f"ERREUR: Le backend n'a pas repondu:\n{stderr[:500]}")
        backend_proc.terminate()
        sys.exit(1)

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
        text=True,
        bufsize=1,
    )

    if wait_for_health("http://localhost:3000", timeout=30):
        print("  Frontend demarre et pret (PID: {})".format(frontend_proc.pid))
    else:
        stderr = frontend_proc.stderr.read() if frontend_proc.stderr else ""
        print(f"ERREUR: Le frontend n'a pas repondu:\n{stderr[:500]}")
        backend_proc.terminate()
        frontend_proc.terminate()
        sys.exit(1)

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

    if sys.platform != "win32":
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


if __name__ == "__main__":
    main()
