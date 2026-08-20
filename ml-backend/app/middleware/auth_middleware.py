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
  - Pure ASGI middleware for zero overhead.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import httpx
from starlette.types import ASGIApp, Receive, Scope, Send

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
        _JWKS_CACHE = {"keys": []}

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

class ClerkAuthMiddleware:
    """
    Starlette ASGI middleware that verifies Clerk JWTs on all protected routes.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if _is_public(path):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("latin1")

        if not auth_header.startswith("Bearer "):
            body = json.dumps({
                "error": "Unauthorized",
                "detail": "Missing or malformed Authorization header. Expected: 'Bearer <token>'",
                "status_code": 401,
            }).encode("utf-8")

            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("utf-8")),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": body,
            })
            return

        token = auth_header.removeprefix("Bearer ").strip()
        claims = _verify_token(token)

        if claims is None:
            body = json.dumps({
                "error": "Unauthorized",
                "detail": "Invalid or expired JWT. Please sign in again.",
                "status_code": 401,
            }).encode("utf-8")

            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("utf-8")),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": body,
            })
            return

        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["user"] = claims

        await self.app(scope, receive, send)
