"""NEXUS API — Configuration endpoints."""
from fastapi import APIRouter
from nexus.core.config import get_settings

router = APIRouter()


@router.get("/providers")
async def get_providers():
    """Get available LLM providers."""
    settings = get_settings()
    providers = {}
    for pid in settings.available_providers:
        providers[pid] = {
            "available": True,
            "default_model": settings.get_default_model(pid) if hasattr(settings, 'get_default_model') else settings.llm_default_model,
        }
    return providers


@router.get("/api-keys")
async def get_api_keys_status():
    """Get API key configuration status (masked)."""
    settings = get_settings()
    keys = {}
    for provider in ["openai", "anthropic", "google", "groq", "openrouter"]:
        key = getattr(settings, f"{provider}_api_key", None)
        if key:
            keys[provider] = {
                "name": provider.title(),
                "env_var": f"{provider.upper()}_API_KEY",
                "configured": True,
                "masked": key[:4] + "..." + key[-4:] if len(key) > 8 else "****",
            }
        else:
            keys[provider] = {
                "name": provider.title(),
                "env_var": f"{provider.upper()}_API_KEY",
                "configured": False,
                "masked": "",
            }
    return keys


@router.post("/api-keys")
async def set_api_key(request: dict):
    """Set an API key (saves to .env)."""
    import os
    from pathlib import Path

    provider = request.get("provider")
    api_key = request.get("api_key", "")
    if not provider:
        return {"error": "Provider required"}

    env_file = Path(__file__).parent.parent.parent / ".env"
    env_var = f"{provider.upper()}_API_KEY"

    lines = []
    updated = False
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith(f"{env_var}="):
                lines.append(f"{env_var}={api_key}")
                updated = True
            else:
                lines.append(line)
    if not updated:
        lines.append(f"{env_var}={api_key}")

    env_file.write_text("\n".join(lines) + "\n")
    os.environ[env_var] = api_key

    return {
        "provider": provider,
        "configured": bool(api_key),
        "masked": api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "****",
    }
