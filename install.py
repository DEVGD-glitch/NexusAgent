#!/usr/bin/env python3
"""
NEXUS Agent — Universal Installer
Works on Windows, macOS, and Linux. No dependencies beyond Python 3.11+.

Usage:
    python install.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    print(f"  > {' '.join(cmd)}")
    result = subprocess.run(
        cmd, cwd=cwd, check=False, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        print(f"  ERREUR (code {result.returncode}):")
        if result.stderr:
            lines = result.stderr.strip().split("\n")
            for line in lines[-20:]:
                print(f"    {line}")
        if check:
            sys.exit(1)
    return result


def check_python() -> bool:
    """Check Python version >= 3.11."""
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 11):
        print(f"  ERREUR: Python 3.11+ requis, vous avez {v.major}.{v.minor}.{v.micro}")
        return False
    print(f"  Python {v.major}.{v.minor}.{v.micro} OK")
    return True


def check_node() -> bool:
    """Check if Node.js or Bun is available."""
    for cmd in ["node", "bun"]:
        if shutil.which(cmd):
            try:
                r = run([cmd, "--version"], check=False)
                print(f"  {cmd} {r.stdout.strip()} OK")
                return True
            except Exception:
                pass
    print("  ERREUR: Node.js ou Bun requis pour le frontend")
    print("  Installez Node.js 20+ depuis https://nodejs.org/")
    return False


def main():
    root = Path(__file__).resolve().parent
    backend_dir = root / "NexusAgent"

    print()
    print("=" * 50)
    print("  NEXUS Agent — Installation")
    print("=" * 50)
    print()

    # 1. Check prerequisites
    print("[1/6] Verification des prerequis...")
    if not check_python():
        sys.exit(1)
    if not check_node():
        sys.exit(1)

    # 2. Create Python venv
    print("\n[2/6] Environnement virtuel Python...")
    venv_dir = backend_dir / "venv"
    if not venv_dir.exists():
        run([sys.executable, "-m", "venv", str(venv_dir)])
        print("  venv cree")
    else:
        print("  venv existant OK")

    # Get venv python path
    if sys.platform == "win32":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    # 3. Install Python dependencies
    print("\n[3/6] Dependances Python...")
    requirements = backend_dir / "requirements.txt"
    if requirements.exists():
        run([str(venv_python), "-m", "pip", "install", "-q", "-r", str(requirements)])
    run([str(venv_python), "-m", "pip", "install", "-q", "-e", str(backend_dir)])
    print("  Python OK")

    # 4. Install frontend dependencies
    print("\n[4/6] Dependances Frontend...")
    if shutil.which("bun"):
        pkg_cmd = ["bun", "install"]
    else:
        pkg_cmd = ["npm", "install", "--no-fund", "--no-audit", "--silent"]
    run(pkg_cmd, cwd=root)
    print("  Frontend OK")

    # 5. Create .env files (before Prisma, which needs DATABASE_URL)
    print("\n[5/6] Configuration...")
    backend_env = backend_dir / ".env"
    backend_env_example = backend_dir / ".env.example"
    if not backend_env.exists() and backend_env_example.exists():
        shutil.copy(backend_env_example, backend_env)
        print("  .env backend cree (configurez vos cles API)")
    frontend_env = root / ".env"
    if not frontend_env.exists():
        frontend_env.write_text(
            "DATABASE_URL=file:./dev.db\n"
            "NEXT_PUBLIC_NEXUS_BACKEND=http://127.0.0.1:8081\n"
        )
        print("  .env frontend cree")

    # 6. Setup database (needs DATABASE_URL from .env)
    print("\n[6/6] Base de donnees...")
    if shutil.which("bun"):
        run(["bunx", "prisma", "generate"], cwd=root, check=False)
        run(["bunx", "prisma", "db", "push"], cwd=root, check=False)
    else:
        run(["npx", "prisma", "generate"], cwd=root, check=False)
        run(["npx", "prisma", "db", "push"], cwd=root, check=False)
    print("  Database OK")

    # Done!
    print()
    print("=" * 50)
    print("  Installation terminee !")
    print()
    print("  Pour demarrer NEXUS:")
    print("    python start.py")
    print()
    print("  Ou manuellement:")
    print("    Backend:  cd NexusAgent && python -m nexus serve --port 8081")
    print("    Frontend: npm run dev  (ou bun dev)")
    print()
    print("  URLs:")
    print("    Frontend: http://localhost:3000")
    print("    Backend:  http://localhost:8081/docs")
    print("=" * 50)
    print()


if __name__ == "__main__":
    main()
