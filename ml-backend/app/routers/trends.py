"""
Trends Router — ml-backend.

Responsibility: Map URLs and HTTP methods for trends discovery endpoints.

Layer rules:
  - Defines routes with @router.method
  - Injects DB session via FastAPI Depends(get_db)
  - Passes params and body to trends_controller
  - NEVER contains business logic, database queries, or algorithms
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.controllers import trends_controller
from app.db.database import get_db

router = APIRouter(prefix="/trends", tags=["Trends Discovery"])


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Get current trending items with lifecycle stage",
    response_description="List of trending items categorized by category & score",
)
def get_trends(
    category: Optional[str] = Query(None, description="Optional category filter (e.g. 'tops', 'jeans')"),
    limit: int = Query(10, ge=1, le=50, description="Max number of trend items to return"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Get the trending items feed.
    Returns trending items containing trend signal scores and lifecycle stages
    (emerging | peaking | dying).
    """
    return trends_controller.handle_get_trends(db, category=category, limit=limit)


@router.post(
    "/recalculate",
    status_code=status.HTTP_200_OK,
    summary="Trigger trend signal recalculation based on database products",
)
def trigger_recalculate_trends(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Forces a recalculation of the signal score and lifecycle stage classification
    for all distinct fashion categories currently present in the database.
    """
    return trends_controller.handle_trigger_recalculate(db)
