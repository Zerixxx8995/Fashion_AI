"""
Wardrobe Pydantic models — ml-backend.

Responsibility: Request and response shapes for wardrobe gap-analysis endpoint.

Architecture rules:
  Layer: Models (data shapes only)
  One job: Define Pydantic schemas for validation and serialisation
  Never does: Business logic, DB access
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, HttpUrl, field_validator


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class WardrobeItem(BaseModel):
    """
    A single item the user sends for gap analysis.
    The category field drives the gap detection logic.
    """
    id: Optional[str] = None
    name: str
    category: Optional[str] = None
    color: Optional[str] = None
    image_url: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name must be a non-empty string")
        return v.strip()


class GapAnalysisRequest(BaseModel):
    """
    POST /wardrobe/gap-analysis request body.

    wardrobe: list of items the user currently owns.
    budget_inr: optional — if provided, the response includes
                per-category budget recommendations.
    """
    wardrobe: list[WardrobeItem]
    budget_inr: Optional[int] = None

    @field_validator("wardrobe")
    @classmethod
    def wardrobe_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("wardrobe must contain at least one item")
        return v

    @field_validator("budget_inr")
    @classmethod
    def budget_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("budget_inr must be a positive integer")
        return v


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class GapCategory(BaseModel):
    """A single missing category detected in the gap analysis."""
    category: str
    priority: str           # 'high' | 'medium' | 'low'
    reason: str
    suggested_budget_inr: Optional[int] = None


class GapAnalysisResponse(BaseModel):
    """
    POST /wardrobe/gap-analysis response.

    owned_categories: normalised list of what the user has.
    missing_categories: categories detected as gaps.
    coverage_score: float 0-1 how complete the wardrobe is vs. a full capsule.
    """
    owned_categories: list[str]
    missing_categories: list[GapCategory]
    coverage_score: float
    total_items: int
    analysis_note: str
