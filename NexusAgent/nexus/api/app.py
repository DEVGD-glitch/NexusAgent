"""NEXUS API — FastAPI application factory."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nexus.api.middleware import setup_middleware
from nexus.api.routers import (
    chat, memory, agents, tools, mcp, plugins, rules,
    workflows, voice, viz, approvals, config, metrics, health
)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="NEXUS Agent API",
        description="Sovereign AI Agent — Multi-LLM, 5-Layer Memory, MCP Protocol",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Middleware (logging, rate limiting, auth)
    setup_middleware(app)

    # Routers
    app.include_router(health.router, prefix="", tags=["Health"])
    app.include_router(chat.router, prefix="/chat", tags=["Chat"])
    app.include_router(memory.router, prefix="/memory", tags=["Memory"])
    app.include_router(agents.router, prefix="/agents", tags=["Agents"])
    app.include_router(tools.router, prefix="/tools", tags=["Tools"])
    app.include_router(mcp.router, prefix="/mcp", tags=["MCP"])
    app.include_router(plugins.router, prefix="/plugins", tags=["Plugins"])
    app.include_router(rules.router, prefix="/rules", tags=["Rules"])
    app.include_router(workflows.router, prefix="/workflows", tags=["Workflows"])
    app.include_router(voice.router, prefix="/voice", tags=["Voice"])
    app.include_router(viz.router, prefix="/viz", tags=["Visualization"])
    app.include_router(approvals.router, prefix="/approvals", tags=["Approvals"])
    app.include_router(config.router, prefix="/config", tags=["Configuration"])
    app.include_router(metrics.router, prefix="/metrics", tags=["Metrics"])

    return app
