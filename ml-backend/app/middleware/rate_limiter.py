"""
Rate Limiter Middleware — ml-backend.

Responsibility: Prevent abuse by enforcing per-IP request rate limits.
Satisfies NF8: rate limiting on all public-facing API routes.

Strategy:
  - In-memory sliding window using a simple token bucket per IP address.
  - Configurable via environment variables.
  - Pure ASGI middleware for zero overhead.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict, deque
from typing import Deque

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_MAX_REQUESTS: int = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "60"))
_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

# Routes exempt from rate limiting (internal health checks, docs)
_EXEMPT_PATHS: frozenset[str] = frozenset(
    ["/api/v1/health", "/docs", "/redoc", "/openapi.json"]
)

# ---------------------------------------------------------------------------
# In-memory sliding window store
# ---------------------------------------------------------------------------

_request_log: dict[str, Deque[float]] = defaultdict(deque)


def _get_client_ip_from_scope(scope: Scope) -> str:
    headers = dict(scope.get("headers", []))
    forwarded_for = headers.get(b"x-forwarded-for")
    if forwarded_for:
        return forwarded_for.decode("latin1").split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else "unknown"


def _is_rate_limited(ip: str) -> tuple[bool, int]:
    now = time.monotonic()
    window_start = now - _WINDOW_SECONDS
    timestamps = _request_log[ip]

    while timestamps and timestamps[0] < window_start:
        timestamps.popleft()

    if len(timestamps) >= _MAX_REQUESTS:
        retry_after = int(timestamps[0] - window_start) + 1
        return True, retry_after

    timestamps.append(now)
    return False, 0


# ---------------------------------------------------------------------------
# Middleware class
# ---------------------------------------------------------------------------

class RateLimiterMiddleware:
    """
    Per-IP sliding window rate limiter implemented as pure ASGI middleware.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        logger.info(
            "[rate_limiter] configured: %d req / %ds window",
            _MAX_REQUESTS,
            _WINDOW_SECONDS,
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in _EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        ip = _get_client_ip_from_scope(scope)
        limited, retry_after = _is_rate_limited(ip)

        if limited:
            logger.warning(
                "[rate_limiter] 429 Too Many Requests ip=%s path=%s",
                ip,
                path,
            )
            body = json.dumps({
                "error": "Too Many Requests",
                "detail": f"Rate limit exceeded: {_MAX_REQUESTS} requests per {_WINDOW_SECONDS}s. Retry after {retry_after}s.",
                "status_code": 429,
            }).encode("utf-8")

            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", str(retry_after).encode("utf-8")),
                    (b"content-length", str(len(body)).encode("utf-8")),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": body,
            })
            return

        await self.app(scope, receive, send)
