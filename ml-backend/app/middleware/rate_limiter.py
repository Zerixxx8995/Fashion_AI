"""
Rate Limiter Middleware — ml-backend.

Responsibility: Prevent abuse by enforcing per-IP request rate limits.
Satisfies NF8: rate limiting on all public-facing API routes.

Strategy:
  - In-memory sliding window using a simple token bucket per IP address.
  - No Redis needed for single-instance deployment (Render free tier).
  - Configurable via environment variables — see constants below.
  - Returns 429 Too Many Requests with canonical error shape and
    Retry-After header so clients know when to retry.

Architecture rules:
  Layer: Middleware
  One job: Is this client within its request quota?
  Never does: Auth, business logic, response shaping beyond error format

Environment variables (all optional — defaults shown):
  RATE_LIMIT_MAX_REQUESTS   — max requests per window (default: 60)
  RATE_LIMIT_WINDOW_SECONDS — sliding window size in seconds (default: 60)
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

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

# Maps IP address → deque of request timestamps within the current window
_request_log: dict[str, Deque[float]] = defaultdict(deque)


def _get_client_ip(request: Request) -> str:
    """
    Extract client IP, respecting X-Forwarded-For set by Render's proxy.
    Falls back to the direct connection address.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_rate_limited(ip: str) -> tuple[bool, int]:
    """
    Check whether `ip` has exceeded its rate limit.

    Returns:
        (is_limited: bool, retry_after_seconds: int)
    """
    now = time.monotonic()
    window_start = now - _WINDOW_SECONDS
    timestamps = _request_log[ip]

    # Evict timestamps outside the sliding window
    while timestamps and timestamps[0] < window_start:
        timestamps.popleft()

    if len(timestamps) >= _MAX_REQUESTS:
        # How long until the oldest request falls out of the window
        retry_after = int(timestamps[0] - window_start) + 1
        return True, retry_after

    timestamps.append(now)
    return False, 0


# ---------------------------------------------------------------------------
# Middleware class
# ---------------------------------------------------------------------------

class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Per-IP sliding window rate limiter.

    Exempt paths bypass the limiter entirely (health checks, docs).
    All other paths are subject to the configured request quota.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        logger.info(
            "[rate_limiter] configured: %d req / %ds window",
            _MAX_REQUESTS, _WINDOW_SECONDS,
        )

    async def dispatch(self, request: Request, call_next):
        # Exempt paths bypass rate limiting
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        ip = _get_client_ip(request)
        limited, retry_after = _is_rate_limited(ip)

        if limited:
            logger.warning(
                "[rate_limiter] 429 Too Many Requests ip=%s path=%s",
                ip, request.url.path,
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(retry_after)},
                content={
                    "error": "Too Many Requests",
                    "detail": (
                        f"Rate limit exceeded: {_MAX_REQUESTS} requests "
                        f"per {_WINDOW_SECONDS}s. "
                        f"Retry after {retry_after}s."
                    ),
                    "status_code": 429,
                },
            )

        return await call_next(request)
