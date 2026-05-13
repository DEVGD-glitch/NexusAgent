"""NEXUS CLI entry point — matches pyproject.toml [project.scripts]."""

from nexus.cli import app


def main():
    """Entry point for the nexus command."""
    app()


if __name__ == "__main__":
    main()
