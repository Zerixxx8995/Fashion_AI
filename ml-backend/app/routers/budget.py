"""
Budget Router — ml-backend.

Responsibility: Map HTTP method + URL to budget controller.

Routes:
  POST /api/v1/budget/optimize  — Optimize outfit budget splits
"""

from __future__ import annotations

from fastapi import APIRouter

from app.models.budget_models import BudgetOptimizeRequest, BudgetOptimizeResponse
from app.controllers.budget_controller import optimize_outfit_budget

router = APIRouter(prefix="/budget", tags=["budget"])


@router.post(
    "/optimize",
    response_model=BudgetOptimizeResponse,
    summary="Optimize outfit budget",
    description=(
        "Submit a total shopping budget and target occasion to receive an optimized "
        "proportional allocation across clothing categories, along with tailored styling and shopping tips."
    ),
)
async def optimize_budget_route(request: BudgetOptimizeRequest) -> BudgetOptimizeResponse:
    return await optimize_outfit_budget(request)
