"""
Request Logger Middleware — ml-backend.

Responsibility: Structured per-request logging — method, path, status code,
and response time. Useful for debugging and observability on Render.

Architecture rules:
  Layer: Middleware
  One job: Log every request + response (method, path, status, duration)
  Never does: Auth, business logic, error handling

Log format:
  INFO  → → METHOD /path  (request received)
  INFO  ← ← METHOD /path 200 12ms  (response sent)
  WARNING ← ← METHOD /path 4xx/5xx 5ms  (error responses)
"""

from __future__ import annotations

import logging
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger("request")


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """
    Logs every HTTP request with method, path, status code, and duration.
    Uses the "request" logger so log level can be toggled independently.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()

        logger.info("→ → %s %s", request.method, request.url.path)

        response = await call_next(request)

        duration_ms = int((time.perf_counter() - start) * 1000)
        log_fn = logger.warning if response.status_code >= 400 else logger.info
        log_fn(
            "← ← %s %s %d %dms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        # Attach timing header for debugging
        response.headers["X-Response-Time-Ms"] = str(duration_ms)
        return response
