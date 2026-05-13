"""
NEXUS MCP Web Tools.
"""

import json
from typing import Optional


async def web_search(query: str, num_results: int = 5) -> str:
    """Search the web for information."""
    try:
        from exa_py import Exa

        exa = Exa()
        results = exa.search(query, num_results=num_results)

        return json.dumps({
            "query": query,
            "results": [
                {
                    "title": r.get("title"),
                    "url": r.get("url"),
                    "snippet": r.get("snippet", "")[:200],
                }
                for r in results
            ],
            "count": len(results),
        })
    except ImportError:
        return json.dumps({"error": "exa-py not installed. Install with: pip install exa-py"})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def web_scrape(url: str, max_length: int = 10000) -> str:
    """Scrape a webpage's content."""
    try:
        import requests

        response = requests.get(url, timeout=10)
        content = response.text[:max_length]

        return json.dumps({
            "url": url,
            "content": content,
            "length": len(content),
            "status_code": response.status_code,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


async def web_screenshot(url: str) -> str:
    """Take a screenshot of a webpage."""
    try:
        return json.dumps({
            "status": "not_implemented",
            "message": "Use browser automation for screenshots",
            "url": url,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})