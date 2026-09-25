"""
Explanations Controller — ml-backend/app/controllers/explanations_controller.py

Responsibility: Parse HTTP request params, call explanation_service, shape response.

Layer rules (controller):
  - Receives parsed params from the router.
  - Calls app/services/explanation_service.py.
  - Shapes errors into HTTPExceptions for the router.
  - Does NOT contain business logic.
  - Does NOT contain HTTP routing declarations.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.services import explanation_service

logger = logging.getLogger(__name__)


def handle_get_trend_explanation(
    db: Session,
    *,
    trend_id: str,
) -> dict[str, Any]:
    """
    Handle GET /explanations/trend/{trend_id}.

    Args:
        db:       SQLAlchemy session (injected by router via Depends).
        trend_id: Path parameter — UUID of the TrendItem.

    Returns:
        Explanation dict matching the spec response shape.

    Raises:
        HTTPException 404: If the trend_id is not found.
        HTTPException 500: If explanation generation fails.
    """
    logger.info("[explanations_controller] handle_get_trend_explanation trend_id=%s", trend_id)

    try:
        result = explanation_service.get_trend_explanation(db, trend_id=trend_id)
    except KeyError as exc:
        logger.warning("[explanations_controller] trend not found: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trend with id={trend_id!r} not found",
        )
    except Exception as exc:
        logger.error("[explanations_controller] trend explanation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate explanation: {exc}",
        )

    return result


def handle_get_recommendation_explanation(
    db: Session,
    *,
    product_id: str,
    user_id: str,
) -> dict[str, Any]:
    """
    Handle GET /explanations/recommendation/{product_id}.

    Args:
        db:         SQLAlchemy session (injected by router via Depends).
        product_id: Path parameter — UUID of the Product.
        user_id:    Query parameter — UUID or clerk_id of the authenticated user.

    Returns:
        Explanation dict matching the spec response shape.

    Raises:
        HTTPException 400: If user_id query param is missing.
        HTTPException 404: If product_id or user_id is not found.
        HTTPException 500: If explanation generation fails.
    """
    logger.info(
        "[explanations_controller] handle_get_recommendation_explanation "
        "product_id=%s user_id=%s", product_id, user_id
    )

    if not user_id or not user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id query parameter is required",
        )

    try:
        result = explanation_service.get_recommendation_explanation(
            db, product_id=product_id, user_id=user_id
        )
    except KeyError as exc:
        logger.warning("[explanations_controller] resource not found: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("[explanations_controller] recommendation explanation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate explanation: {exc}",
        )

    return result
