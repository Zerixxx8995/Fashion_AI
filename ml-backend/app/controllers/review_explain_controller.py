"""
Review Explain Controller — ml-backend/app/controllers/review_explain_controller.py

Responsibility: Parse HTTP request params, validate review exists and is
flagged fake, call review_explain_service, shape errors into HTTPExceptions.

Layer rules (controller):
  - Receives parsed params from the router.
  - Calls app/services/review_explain_service.py.
  - Shapes errors into HTTPExceptions.
  - Does NOT contain business logic.
  - Does NOT contain HTTP routing declarations.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.services import review_explain_service

logger = logging.getLogger(__name__)


def handle_review_explain(
    db: Session,
    *,
    review_id: str,
) -> dict:
    """
    Handle GET /reviews/{review_id}/explain.

    Args:
        db:        SQLAlchemy session (injected by router via Depends).
        review_id: UUID string path parameter.

    Returns:
        Response dict matching the spec API shape.

    Raises:
        HTTPException 404: If the review does not exist.
        HTTPException 400: If the review is not flagged as fake.
        HTTPException 500: If the RAG engine or LLM call fails.
    """
    logger.info(
        "[review_explain_controller] handle_review_explain review_id=%s", review_id
    )

    try:
        result = review_explain_service.get_review_explanation(
            db,
            review_id=review_id,
        )
    except KeyError as exc:
        logger.warning("[review_explain_controller] review not found: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review with id={review_id!r} not found",
        )
    except ValueError as exc:
        logger.warning("[review_explain_controller] review not flagged: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(
            "[review_explain_controller] explanation generation failed: %s", exc
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Explanation generation failed: {exc}",
        )

    return result
