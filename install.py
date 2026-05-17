#!/usr/bin/env python3
"""
NEXUS Agent — One-Click Installer
Supports: Windows, macOS, Linux
Python 3.11+ | Node 20+ | Bun (optional)

Usage:
    python install.py
"""

import os
import shutil
import subprocess
import sys
import secrets
from pathlib import Path


class Installer:
    def __init__(self):
        self.root = Path(__file__).resolve().parent
        self.backend = self.root / "NexusAgent"
        self.errors = []
        self.warnings = []
        self.has_bun = shutil.which("bun") is not None
        self.has_docker = shutil.which("docker") is not None

    def run(self):
        self.banner()
        self.check_system()
        self.setup_backend()
        self.setup_frontend()
        self.setup_database()
        self.generate_env()
        self.verify()
        self.done()

    def banner(self):
        print()
        print("=" * 60)
        print("  NEXUS Agent — One-Click Installer")
        print("  Agent IA Souverain — Zero Cloud, Zero Compromis")
        print("=" * 60)
        print()

    def step(self, msg: str):
        print(f"  → {msg}")

    def fail(self, msg: str):
        self.errors.append(msg)
        print(f"  ❌ {msg}")

    def warn(self, msg: str):
        self.warnings.append(msg)
        print(f"  ⚠️  {msg}")

    def ok(self, msg: str):
        print(f"  ✅ {msg}")

    def check_system(self):
        """Check Python, Node, system requirements."""
        self.step("Verification du systeme...")

        # Python 3.11+
        py_ver = sys.version_info
        if py_ver < (3, 11):
            self.fail(f"Python 3.11+ requis, trouve {py_ver.major}.{py_ver.minor}")
        else:
            self.ok(f"Python {py_ver.major}.{py_ver.minor}.{py_ver.micro}")

        # Node.js
        try:
            node_ver = subprocess.check_output(["node", "--version"], text=True).strip()
            major = int(node_ver.lstrip("v").split(".")[0])
            if major >= 20:
                self.ok(f"Node.js {node_ver}")
            else:
                self.warn(f"Node 20+ recommande, trouve {node_ver}")
        except Exception:
            self.fail("Node.js non trouve. Installez depuis nodejs.org")

        # Bun
        if self.has_bun:
            bun_ver = subprocess.check_output(["bun", "--version"], text=True).strip()
            self.ok(f"Bun {bun_ver}")
        else:
            self.warn("Bun non trouve (optionnel, npm sera utilise)")

        # Docker
        if self.has_docker:
            self.ok("Docker disponible")
        else:
            self.warn("Docker non trouve (optionnel, pour le deploiement)")

        if self.errors:
            print("\nInstallation annulee. Corrigez les erreurs ci-dessus.")
            sys.exit(1)

    def setup_backend(self):
        """Create venv and install Python dependencies."""
        self.step("Configuration du backend Python...")

        venv_dir = self.backend / "venv"
        if sys.platform == "win32":
            venv_python = venv_dir / "Scripts" / "python.exe"
            pip_path = venv_dir / "Scripts" / "pip.exe"
        else:
            venv_python = venv_dir / "bin" / "python"
            pip_path = venv_dir / "bin" / "pip"

        if not venv_python.exists():
            self.step("Creation de l'environnement virtuel...")
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
            self.ok("Environnement virtuel cree")
        else:
            self.ok("Environnement virtuel existant")

        self.step("Installation des dependances Python...")
        result = subprocess.run(
            [str(pip_path), "install", "-r", str(self.backend / "requirements.txt")],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            self.ok("Dependances Python installees")
        else:
            self.fail(f"Echec installation Python:\n{result.stderr[-500:]}")

    def setup_frontend(self):
        """Install Node.js dependencies."""
        self.step("Installation des dependances frontend...")
        cmd = ["bun", "install"] if self.has_bun else ["npm", "install"]
        result = subprocess.run(cmd, cwd=str(self.root), capture_output=True, text=True)
        if result.returncode == 0:
            self.ok("Dependances frontend installees")
        else:
            self.fail(f"Echec installation frontend:\n{result.stderr[-500:]}")

    def setup_database(self):
        """Setup Prisma database."""
        self.step("Configuration de la base de donnees...")

        # Generate Prisma client
        result = subprocess.run(
            ["npx", "prisma", "generate"],
            cwd=str(self.root),
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            self.ok("Client Prisma genere")
        else:
            self.warn(f"Prisma generate: {result.stderr[-200:]}")

        # Push schema to database
        result = subprocess.run(
            ["npx", "prisma", "db", "push", "--accept-data-loss"],
            cwd=str(self.root),
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            self.ok("Base de donnees initialisee")
        else:
            self.warn(f"Prisma db push: {result.stderr[-200:]}")

    def generate_env(self):
        """Generate .env files with secure defaults."""
        self.step("Generation des fichiers de configuration...")

        secret_key = secrets.token_hex(32)

        # Backend .env
        backend_env = self.backend / ".env"
        if not backend_env.exists():
            backend_env.write_text(f"""# ═══════════════════════════════════════════════════════════════
# NEXUS Backend Configuration
# ═══════════════════════════════════════════════════════════════

# Environment
NEXUS_ENV=development
NEXUS_PORT=8081
NEXUS_SECRET_KEY={secret_key}

# LLM Providers (decommentez et ajoutez vos cles)
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# GOOGLE_API_KEY=AIza...
# GROQ_API_KEY=gsk_...
# OPENROUTER_API_KEY=sk-or-...
# NVIDIA_API_KEY=nvapi-...
# CEREBRAS_API_KEY=csk-...
# TOGETHER_API_KEY=...
# DEEPINFRA_API_KEY=...
# ZHIPUAI_API_KEY=...

# ChromaDB
CHROMA_HOST=localhost
CHROMA_PORT=8000

# CORS
ALLOWED_ORIGINS=http://localhost:3000

# Security
NEXUS_API_KEY=  # Leave empty for dev mode

# Observability
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=
""")
            self.ok("Backend .env genere")
        else:
            self.ok("Backend .env existant (non ecrase)")

        # Frontend .env.local
        frontend_env = self.root / ".env.local"
        if not frontend_env.exists():
            frontend_env.write_text("""# ═══════════════════════════════════════════════════════════════
# NEXUS Frontend Configuration
# ═══════════════════════════════════════════════════════════════

NEXT_PUBLIC_NEXUS_BACKEND=http://localhost:8081
DATABASE_URL="file:./dev.db"
""")
            self.ok("Frontend .env.local genere")
        else:
            self.ok("Frontend .env.local existant (non ecrase)")

    def verify(self):
        """Run verification checks."""
        self.step("Verification finale...")

        # Check backend can import
        if sys.platform == "win32":
            venv_python = self.backend / "venv" / "Scripts" / "python.exe"
        else:
            venv_python = self.backend / "venv" / "bin" / "python"

        result = subprocess.run(
            [str(venv_python), "-c", "import nexus; print('OK')"],
            cwd=str(self.backend),
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            self.ok("Module nexus importable")
        else:
            self.warn(f"Import nexus: {result.stderr.strip()}")

    def done(self):
        """Print completion message."""
        print()
        print("=" * 60)
        if self.errors:
            print("  ❌ Installation terminee avec des erreurs")
            print("=" * 60)
            for e in self.errors:
                print(f"     - {e}")
            sys.exit(1)
        else:
            print("  ✅ NEXUS Agent installe avec succes !")
            print("=" * 60)
            print()
            print("  Demarrer avec :  python start.py")
            print()
            print("  Frontend : http://localhost:3000")
            print("  Backend  : http://localhost:8081/docs")
            print("  API Docs : http://localhost:8081/docs")
            print()
            if self.warnings:
                print(f"  ⚠️  Avertissements ({len(self.warnings)}):")
                for w in self.warnings:
                    print(f"     - {w}")
                print()


if __name__ == "__main__":
    Installer().run()
