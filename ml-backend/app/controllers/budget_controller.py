"""
Budget Controller — ml-backend.

Responsibility: Parse request, invoke budget_service, shape response.
"""

from __future__ import annotations

import logging
from fastapi import HTTPException

from app.models.budget_models import BudgetOptimizeRequest, BudgetOptimizeResponse
from app.services.budget_service import optimize_budget

logger = logging.getLogger(__name__)


async def optimize_outfit_budget(request: BudgetOptimizeRequest) -> BudgetOptimizeResponse:
    """
    Handle POST /budget/optimize request.
    """
    logger.info(
        "[budget_controller] optimize_outfit_budget budget=%d occasion=%s",
        request.budget_inr,
        request.occasion,
    )
    try:
        result = optimize_budget(request)
        return result
    except Exception as exc:
        logger.error("[budget_controller] optimization failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Budget optimization failed: {exc}",
        )
