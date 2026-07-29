"""
Trends Controller — ml-backend.

Responsibility: Parses HTTP request query parameters, calls the trend service,
and formats the response payload.

Layer rules:
  - Receives request context and DB session.
  - Calls app/services/trend_service.py.
  - Shapes responses to plain dicts or structures.
  - Does NOT do HTTP routing.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.services import trend_service

logger = logging.getLogger(__name__)


def handle_get_trends(
    db: Session,
    *,
    category: Optional[str] = None,
    limit: int = 10,
) -> dict[str, Any]:
    """
    Handle GET /trends endpoint logic.
    Retrieves trending items from trend_service and shapes them into a response list.
    """
    logger.info(
        "[trends_controller] handle_get_trends category=%s limit=%d",
        category, limit
    )
    trends = trend_service.get_trending_items(db, category=category, limit=limit)
    
    return {
        "trends": [t.to_dict() for t in trends],
        "count": len(trends),
        "category_filter": category,
    }


def handle_trigger_recalculate(db: Session) -> dict[str, Any]:
    """
    Handle trigger recalculation logic.
    Invokes the trend calculation job across products.
    """
    logger.info("[trends_controller] handle_trigger_recalculate triggered")
    trend_service.recalculate_trends_from_products(db)
    return {
        "status": "success",
        "detail": "Trends recalculated successfully from database product profiles."
    }
