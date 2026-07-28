"""
Health Router — ml-backend.

Responsibility: Expose a /health endpoint for uptime checks and deployment probes.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health check")
def health_check() -> dict[str, str]:
    """Returns 200 OK when the service is running."""
    return {"status": "ok", "service": "ml-backend"}
