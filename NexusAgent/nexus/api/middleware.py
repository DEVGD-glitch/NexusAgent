"""NEXUS API — Middleware setup."""
from __future__ import annotations

import logging
import time
import uuid
from fastapi import FastAPI, Request, Response

logger = logging.getLogger("nexus.api")


def setup_middleware(app: FastAPI) -> None:
    """Setup all middleware."""

    @app.middleware("http")
    async def logging_middleware(request: Request, call_next) -> Response:
        """Log every request with timing and request ID."""
        start = time.time()
        request_id = str(uuid.uuid4())[:8]

        response = await call_next(request)

        duration = time.time() - start
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} "
            f"{response.status_code} {duration:.3f}s"
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        return response

    @app.middleware("http")
    async def security_headers(request: Request, call_next) -> Response:
        """Add security headers to every response."""
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
