"""NEXUS API — Shared Pydantic models."""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    messages: list[dict]
    provider: Optional[str] = None
    model: Optional[str] = None
    stream: bool = False


class ChatResponse(BaseModel):
    content: str
    provider: str
    model: str
    tokens: Optional[int] = None
    latency: Optional[float] = None


class TaskRequest(BaseModel):
    task: str
    provider: Optional[str] = None
    mode: str = "plan"


class TaskResponse(BaseModel):
    status: str
    plan: Optional[str] = None
    result: str


class MemoryStoreRequest(BaseModel):
    layer: str
    content: str
    metadata: Optional[dict] = None


class MemoryRecallRequest(BaseModel):
    layer: str
    query: str
    limit: int = 5


class ToolCallRequest(BaseModel):
    tool: str
    args: dict


class ApprovalResponse(BaseModel):
    approved: bool
    reason: Optional[str] = None
