"""NEXUS API — Metrics and monitoring endpoints."""
from fastapi import APIRouter
import psutil
import os

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard():
    """Get system dashboard metrics."""
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)

    return {
        "cpu_percent": cpu,
        "memory_mb": round(mem, 1),
        "tokens_used_today": 0,
        "tool_calls_today": 0,
        "errors_last_hour": 0,
        "agents_running": [],
        "uptime_seconds": 0,
    }
