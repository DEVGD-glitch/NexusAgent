"""NEXUS API — Chat endpoints with streaming support."""
from __future__ import annotations

import json
import time
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from nexus.api.models import ChatRequest, ChatResponse
from nexus.api.deps import get_auth_header
from nexus.core.config import get_settings
from nexus.llm.router import get_router as get_llm_router

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, auth: str | None = get_auth_header()):
    """Non-streaming chat endpoint."""
    settings = get_settings()
    if settings.nexus_env == "production" and not auth:
        raise HTTPException(status_code=401, detail="Authentication required")

    provider = request.provider or settings.default_provider
    model = request.model or settings.default_model

    llm_router = get_llm_router()
    start = time.time()

    try:
        result = await llm_router.chat(
            messages=request.messages,
            provider=provider,
            model=model,
        )
        latency = time.time() - start

        return ChatResponse(
            content=result.get("content", ""),
            provider=provider,
            model=model,
            tokens=result.get("usage", {}).get("total_tokens"),
            latency=round(latency, 3),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def chat_stream(request: ChatRequest, auth: str | None = get_auth_header()):
    """SSE streaming chat endpoint."""
    settings = get_settings()
    if settings.nexus_env == "production" and not auth:
        raise HTTPException(status_code=401, detail="Authentication required")

    provider = request.provider or settings.default_provider
    model = request.model or settings.default_model

    llm_router = get_llm_router()

    async def event_generator():
        try:
            async for chunk in llm_router.chat_stream(
                messages=request.messages,
                provider=provider,
                model=model,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
