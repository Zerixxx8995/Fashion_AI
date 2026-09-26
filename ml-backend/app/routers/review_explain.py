"""
Review Explain Router — ml-backend/app/routers/review_explain.py

Endpoint:
  GET /api/v1/reviews/{review_id}/explain

Returns a structured authenticity explanation for a flagged fake review.
Explanation is Redis-cached for 48 hours per spec.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.controllers.review_explain_controller import handle_review_explain

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reviews", tags=["Review Authenticity"])


@router.get("/{review_id}/explain")
def explain_review(
    review_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    GET /api/v1/reviews/{review_id}/explain

    Returns a structured RAG-generated explanation of why a specific review
    was flagged as potentially fake.

    - 200: Explanation returned (possibly from Redis cache).
    - 400: Review exists but is NOT flagged as fake.
    - 404: Review ID not found.
    - 500: Explanation generation failed.
    """
    logger.info("[review_explain_router] GET /reviews/%s/explain", review_id)
    return handle_review_explain(db, review_id=review_id)
