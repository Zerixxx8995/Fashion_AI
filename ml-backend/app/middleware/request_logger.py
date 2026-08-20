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

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("request")


class RequestLoggerMiddleware:
    """
    Logs every HTTP request with method, path, status code, and duration.
    Uses pure ASGI implementation to avoid BaseHTTPMiddleware overhead.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        method = scope.get("method", "GET")
        path = scope.get("path", "")

        logger.info("→ → %s %s", method, path)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                duration_ms = int((time.perf_counter() - start) * 1000)
                status_code = message.get("status", 200)
                log_fn = logger.warning if status_code >= 400 else logger.info
                log_fn(
                    "← ← %s %s %d %dms",
                    method,
                    path,
                    status_code,
                    duration_ms,
                )
                headers = list(message.get("headers", []))
                headers.append((b"x-response-time-ms", str(duration_ms).encode()))
                message["headers"] = headers

            await send(message)

        await self.app(scope, receive, send_wrapper)
