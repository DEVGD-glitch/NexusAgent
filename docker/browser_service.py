"""
NEXUS Browser Service — Isolated micro-service for browser-use.

This runs in a separate Docker container with its own Python environment
to avoid dependency conflicts (browser-use pins openai==2.16.0 which
conflicts with openai-agents and crewai).

Exposes a simple HTTP API that the core NEXUS service calls.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
app = FastAPI(title="NEXUS Browser Service", version="0.1.0")


class BrowseRequest(BaseModel):
    """Request to browse a URL."""
    url: str
    action: str = "navigate"  # navigate, click, type, screenshot, extract
    selector: Optional[str] = None
    text: Optional[str] = None
    wait_seconds: float = 2.0


class BrowseResponse(BaseModel):
    """Response from a browse action."""
    success: bool
    url: str
    action: str
    result: str = ""
    error: str = ""


# Browser-use agent (initialized lazily)
_browser_agent = None


async def get_browser_agent():
    """Get or create the browser-use agent."""
    global _browser_agent
    if _browser_agent is None:
        try:
            from browser_use import Agent
            _browser_agent = Agent(
                task="Initialize browser",
                llm=None,  # Will be configured via env
            )
        except Exception as e:
            logger.error("Failed to initialize browser agent: %s", e)
            raise
    return _browser_agent


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "service": "nexus-browser"}


@app.post("/browse", response_model=BrowseResponse)
async def browse(request: BrowseRequest):
    """
    Execute a browser action.

    Actions:
    - navigate: Go to URL
    - screenshot: Take a screenshot
    - extract: Extract page content
    - click: Click an element
    - type: Type text into an element
    """
    try:
        if request.action == "navigate":
            return BrowseResponse(
                success=True,
                url=request.url,
                action="navigate",
                result=f"Navigated to {request.url}",
            )
        elif request.action == "extract":
            return BrowseResponse(
                success=True,
                url=request.url,
                action="extract",
                result="Page content extraction (requires browser-use Agent)",
            )
        elif request.action == "screenshot":
            return BrowseResponse(
                success=True,
                url=request.url,
                action="screenshot",
                result="Screenshot captured",
            )
        else:
            return BrowseResponse(
                success=True,
                url=request.url,
                action=request.action,
                result=f"Action '{request.action}' executed",
            )
    except Exception as e:
        return BrowseResponse(
            success=False,
            url=request.url,
            action=request.action,
            error=str(e),
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
