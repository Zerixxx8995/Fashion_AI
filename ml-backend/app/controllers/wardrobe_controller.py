"""
Wardrobe Controller — ml-backend.

Responsibility: Parse request, call wardrobe_service, shape response.

Architecture rules:
  Layer: Controller
  One job: HTTP request parsing → service call → response shaping
  Never does: Business logic, DB queries, gap analysis algorithm
"""

from __future__ import annotations

import logging

from fastapi import HTTPException

from app.models.wardrobe_models import GapAnalysisRequest, GapAnalysisResponse
from app.services.wardrobe_service import run_gap_analysis

logger = logging.getLogger(__name__)


async def gap_analysis(request: GapAnalysisRequest) -> GapAnalysisResponse:
    """
    Handle POST /wardrobe/gap-analysis.

    Delegates entirely to wardrobe_service.run_gap_analysis().
    Raises HTTP 422 if validation fails (Pydantic handles this automatically).
    Raises HTTP 500 if an unexpected service error occurs.
    """
    logger.info(
        "[wardrobe_controller] gap_analysis items=%d budget=%s",
        len(request.wardrobe),
        request.budget_inr,
    )

    try:
        result = run_gap_analysis(request)
    except Exception as exc:
        logger.error("[wardrobe_controller] gap_analysis failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Gap analysis failed: {exc}",
        )

    return result
