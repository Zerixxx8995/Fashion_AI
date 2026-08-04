"""
Wardrobe Router — ml-backend.

Responsibility: Map HTTP method + URL to wardrobe controller.

Architecture rules:
  Layer: Router
  One job: Route definitions only — no logic, no response shaping
  Never does: Business logic, DB access

Routes:
  POST /api/v1/wardrobe/gap-analysis  — Submit wardrobe, get capsule gap analysis
"""

from __future__ import annotations

from fastapi import APIRouter

from app.models.wardrobe_models import GapAnalysisRequest, GapAnalysisResponse
from app.controllers.wardrobe_controller import gap_analysis

router = APIRouter(prefix="/wardrobe", tags=["wardrobe"])


@router.post(
    "/gap-analysis",
    response_model=GapAnalysisResponse,
    summary="Capsule wardrobe gap analysis",
    description=(
        "Submit a user's wardrobe and receive a list of missing clothing categories, "
        "a coverage score, and optional budget recommendations per missing category."
    ),
)
async def gap_analysis_route(request: GapAnalysisRequest) -> GapAnalysisResponse:
    return await gap_analysis(request)
