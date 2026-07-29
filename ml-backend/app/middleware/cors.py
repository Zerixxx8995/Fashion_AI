"""
CORS Configuration — ml-backend.

Responsibility: Configure Cross-Origin Resource Sharing headers so the
React Native mobile app and web admin can make cross-origin requests.

Architecture rules:
  Layer: Middleware
  One job: Set CORS headers on every response
  Never does: Auth, business logic

Strategy:
  - Development: allow all origins (*)
  - Production: restrict to origins in ALLOWED_ORIGINS env var (comma-separated)
  - Always expose X-Response-Time-Ms and Content-Type headers
  - Preflight (OPTIONS) requests handled automatically by FastAPI CORSMiddleware

Environment variables:
  ALLOWED_ORIGINS  — comma-separated list of allowed origins.
                     If not set or empty → all origins allowed (development).
                     Example: "https://fashion.app,https://admin.fashion.app"
"""

from __future__ import annotations

import logging
import os
from typing import Sequence

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


def _get_allowed_origins() -> list[str]:
    """
    Read ALLOWED_ORIGINS env var. Falls back to ["*"] if not set.
    """
    raw = os.getenv("ALLOWED_ORIGINS", "").strip()
    if not raw:
        logger.warning(
            "[cors] ALLOWED_ORIGINS not set — allowing all origins (*). "
            "Set this env var in production."
        )
        return ["*"]
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    logger.info("[cors] allowed origins: %s", origins)
    return origins


def register_cors(app: FastAPI) -> None:
    """
    Attach CORSMiddleware to the FastAPI app.
    Call this in create_app() before registering other middleware.
    """
    origins = _get_allowed_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Response-Time-Ms", "Content-Type"],
    )
    logger.info("[cors] middleware registered")
