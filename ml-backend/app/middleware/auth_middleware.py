"""
Auth Middleware — ml-backend.

Responsibility: Verify Clerk JWT on every protected route. Extracts the
token from the Authorization header and validates it using PyJWT + Clerk's
JWKS endpoint.

Architecture rules:
  Layer: Middleware
  One job: Is this request authenticated? (who you are)
  Never does: Authorisation (what you're allowed to do — that's in controllers)

Design:
  - Public routes (health, docs) are explicitly excluded
  - All /api/v1/* routes require a valid Bearer token
  - On success: attaches decoded claims to request.state.user
  - On failure: returns 401 with canonical error shape

Environment variables required:
  CLERK_JWT_ISSUER   — Clerk frontend API URL (e.g. https://<slug>.clerk.accounts.dev)
  CLERK_JWKS_URL     — Clerk JWKS endpoint (auto-derived from issuer if not set)

Note on JWKS caching:
  JWKS keys are fetched once per process startup and cached. Clerk rotates
  keys infrequently; restart the worker if keys become stale.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Routes that do NOT require authentication
# ---------------------------------------------------------------------------

_PUBLIC_PATHS: frozenset[str] = frozenset(
    [
        "/api/v1/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    ]
)

# Path *prefixes* that are public (checked with startswith)
_PUBLIC_PREFIXES: tuple[str, ...] = (
    "/api/v1/trends",           # Trend discovery — read-only, no auth needed
    "/api/v1/recommendations",  # Browse recommendations — read-only
    "/api/v1/cv",               # Computer Vision scan engine — open for guest & authenticated users
    "/docs",
    "/redoc",
)


def _is_public(path: str) -> bool:
    return path in _PUBLIC_PATHS or any(path.startswith(p) for p in _PUBLIC_PREFIXES)


# ---------------------------------------------------------------------------
# JWKS cache
# ---------------------------------------------------------------------------

_JWKS_CACHE: Optional[dict] = None


def _get_jwks() -> dict:
    """
    Fetch and cache Clerk's JWKS keys.
    Called once at startup; re-fetches if cache is None.
    """
    global _JWKS_CACHE  # noqa: PLW0603
    if _JWKS_CACHE is not None:
        return _JWKS_CACHE

    jwks_url = os.getenv("CLERK_JWKS_URL")
    if not jwks_url:
        issuer = os.getenv("CLERK_JWT_ISSUER", "")
        jwks_url = f"{issuer.rstrip('/')}/.well-known/jwks.json"

    logger.info("[auth_middleware] fetching JWKS from %s", jwks_url)
    try:
        resp = httpx.get(jwks_url, timeout=10.0)
        resp.raise_for_status()
        _JWKS_CACHE = resp.json()
    except Exception as exc:
        logger.error("[auth_middleware] JWKS fetch failed: %s", exc)
        _JWKS_CACHE = {"keys": []}  # empty cache — all auth attempts will fail

    return _JWKS_CACHE


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------

_JWKS_CLIENT: Optional[Any] = None


def _get_jwks_client() -> Any:
    global _JWKS_CLIENT  # noqa: PLW0603
    if _JWKS_CLIENT is None:
        import jwt
        from jwt import PyJWKClient

        jwks_url = os.getenv("CLERK_JWKS_URL")
        if not jwks_url:
            issuer = os.getenv("CLERK_JWT_ISSUER", "")
            jwks_url = f"{issuer.rstrip('/')}/.well-known/jwks.json"
        _JWKS_CLIENT = PyJWKClient(jwks_url, cache_keys=True)
    return _JWKS_CLIENT


def _verify_token(token: str) -> Optional[dict]:
    """
    Decode and verify a Clerk JWT using a cached PyJWKClient.
    Returns the decoded claims dict on success, None on any failure.
    """
    try:
        import jwt
        jwks_client = _get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        return claims

    except Exception as exc:
        logger.warning("[auth_middleware] token verification failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Middleware class
# ---------------------------------------------------------------------------

class ClerkAuthMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that verifies Clerk JWTs on all protected routes.

    Attaches decoded claims to request.state.user on success.
    Returns 401 on missing or invalid token.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # Skip auth for public paths
        if _is_public(request.url.path):
            return await call_next(request)

        # Extract Bearer token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "detail": "Missing or malformed Authorization header. "
                              "Expected: 'Bearer <token>'",
                    "status_code": 401,
                },
            )

        token = auth_header.removeprefix("Bearer ").strip()

        # Verify token
        claims = _verify_token(token)
        if claims is None:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "detail": "Invalid or expired JWT. Please sign in again.",
                    "status_code": 401,
                },
            )

        # Attach claims to request state for downstream use
        request.state.user = claims
        return await call_next(request)
