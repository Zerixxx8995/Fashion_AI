"""
Budget Pydantic models — ml-backend.

Responsibility: Request and response schemas for the outfit budget optimizer.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, field_validator


class BudgetOptimizeRequest(BaseModel):
    """
    POST /budget/optimize request body.
    """
    budget_inr: int
    occasion: str  # e.g., "wedding", "formal", "casual", "party", "sports"
    custom_categories: Optional[list[str]] = None

    @field_validator("budget_inr")
    @classmethod
    def budget_positive(cls, v: int) -> int:
        if v < 500:
            raise ValueError("budget_inr must be at least 500 INR")
        return v

    @field_validator("occasion")
    @classmethod
    def validate_occasion(cls, v: str) -> str:
        supported = {"wedding", "festive", "formal", "office", "casual", "party", "sports", "activewear"}
        val = v.strip().lower()
        if val not in supported:
            raise ValueError(
                f"Unsupported occasion '{v}'. Supported occasions are: {', '.join(sorted(supported))}"
            )
        return val


class BudgetAllocationItem(BaseModel):
    """
    Allocation details for a single category.
    """
    category: str
    allocated_amount_inr: int
    percentage: float
    description: str


class BudgetOptimizeResponse(BaseModel):
    """
    POST /budget/optimize response body.
    """
    total_budget_inr: int
    occasion: str
    allocations: list[BudgetAllocationItem]
    allocated_sum_inr: int
    unused_budget_inr: int
    tips: list[str]
