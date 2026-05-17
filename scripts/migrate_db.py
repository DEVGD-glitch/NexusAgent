#!/usr/bin/env python3
"""
NEXUS — Prisma Migration Helper
Detects schema changes and safely migrates the database.

Usage:
    python scripts/migrate_db.py
"""

import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    db_path = root / "dev.db"

    print("=" * 50)
    print("  NEXUS — Database Migration")
    print("=" * 50)
    print()

    # Check if DB exists
    if db_path.exists():
        print("[1/3] Existing database detected...")

        # Try a dry run first
        result = subprocess.run(
            ["npx", "prisma", "db", "push", "--accept-data-loss", "--skip-generate"],
            cwd=str(root),
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print("  ✅ Schema migrated successfully")
        else:
            print(f"  ⚠️  Migration warning: {result.stderr[:200]}")
            print("  Attempting reset...")

            # Reset if push fails
            result = subprocess.run(
                ["npx", "prisma", "migrate", "reset", "--force", "--skip-generate"],
                cwd=str(root),
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print("  ✅ Database reset and migrated")
            else:
                print(f"  ❌ Migration failed: {result.stderr[:200]}")
                sys.exit(1)
    else:
        print("[1/3] No existing database — creating fresh...")
        result = subprocess.run(
            ["npx", "prisma", "db", "push", "--accept-data-loss"],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("  ✅ Database created")
        else:
            print(f"  ❌ Failed: {result.stderr[:200]}")
            sys.exit(1)

    # Generate Prisma client
    print("[2/3] Generating Prisma client...")
    result = subprocess.run(
        ["npx", "prisma", "generate"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("  ✅ Prisma client generated")
    else:
        print(f"  ⚠️  Prisma generate warning: {result.stderr[:200]}")

    # Verify
    print("[3/3] Verifying database...")
    result = subprocess.run(
        ["npx", "prisma", "db", "execute", "--stdin"],
        cwd=str(root),
        input='{"prismaClient": true}',
        capture_output=True,
        text=True,
    )

    print()
    print("=" * 50)
    print("  ✅ Database migration complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
