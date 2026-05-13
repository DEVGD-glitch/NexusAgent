#!/usr/bin/env python3
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

try:
    from dotenv import load_dotenv
    env_path = WORKSPACE_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

if __name__ == "__main__":
    from nexus.cli import app
    app()
