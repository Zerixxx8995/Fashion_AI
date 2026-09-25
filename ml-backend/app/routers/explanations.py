"""
Explanations Router — ml-backend/app/routers/explanations.py

Responsibility: Map URLs and HTTP methods for RAG explanation endpoints.

Layer rules (router):
  - Declares routes with @router.get / @router.post
  - Injects DB session via FastAPI Depends(get_db)
  - Passes params directly to explanations_controller
  - NEVER contains business logic, database queries, or algorithms

Endpoints:
  GET /explanations/trend/{trend_id}                          — trend explanation
  GET /explanations/recommendation/{product_id}?user_id=...  — personalised recommendation explanation
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.controllers import explanations_controller
from app.db.database import get_db

router = APIRouter(prefix="/explanations", tags=["RAG Explanations"])


@router.get(
    "/trend/{trend_id}",
    status_code=status.HTTP_200_OK,
    summary="Get natural-language explanation for why a trend is popular",
    response_description="LLM-generated trend explanation grounded in retrieved product and review data",
)
def get_trend_explanation(
    trend_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Generate (or retrieve from cache) a natural-language explanation for why a
    trend is popular in India right now.

    Explanation is grounded in retrieved product and review data from the database.
    Results are cached in Redis for 24 hours — the LLM is never called twice for
    the same trend within 24 hours.

    The response includes a `cached` boolean so the caller knows if this came
    from the LLM or from Redis.
    """
    return explanations_controller.handle_get_trend_explanation(
        db, trend_id=trend_id
    )


@router.get(
    "/recommendation/{product_id}",
    status_code=status.HTTP_200_OK,
    summary="Get personalised explanation for why a product suits a specific user",
    response_description="LLM-generated style explanation referencing user wardrobe and body type",
)
def get_recommendation_explanation(
    product_id: str,
    user_id: str = Query(..., description="User UUID or Clerk ID — required for personalisation"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Generate (or retrieve from cache) a personalised explanation for why a product
    suits a specific user, referencing their body type and existing wardrobe items.

    Explanation is grounded in retrieved product and wardrobe data.
    Results are cached in Redis for 6 hours per user-product pair.
    """
    return explanations_controller.handle_get_recommendation_explanation(
        db, product_id=product_id, user_id=user_id
    )
