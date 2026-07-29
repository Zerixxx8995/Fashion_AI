"""
CV Pydantic Models — ml-backend.

Responsibility: Request and response schemas for all CV/ML endpoints,
with built-in validation using custom validators and Pydantic rules.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from app.validators.cv_validator import (
    validate_detection_threshold,
    validate_image_url,
    validate_urls_list,
    validate_uuid_string,
)


class CVScoreRequest(BaseModel):
    """
    Schema for scoring request if sent as JSON.
    Note: Real-time scan API uses multipart/form-data for image upload,
    but we define this model for validation completeness.
    """
    product_id: str = Field(..., description="Target product ID (UUID)")
    user_id: str = Field(..., description="User ID requesting the scan (UUID)")

    @field_validator("product_id")
    @classmethod
    def check_product_id(cls, v: str) -> str:
        return validate_uuid_string(v, "product_id")

    @field_validator("user_id")
    @classmethod
    def check_user_id(cls, v: str) -> str:
        return validate_uuid_string(v, "user_id")


class SimilarProductsRequest(BaseModel):
    """
    Request model for visually similar products lookup.
    Requires at least one of image_url or text_query.
    """
    image_url: Optional[str] = Field(None, description="HTTP/HTTPS URL of query image")
    text_query: Optional[str] = Field(None, description="Natural language search query")
    limit: int = Field(10, ge=1, le=50, description="Max number of results to return")
    max_price_inr: Optional[int] = Field(
        None, ge=1, description="Optional upper price limit (inclusive, in INR)"
    )
    category: Optional[str] = Field(
        None, description="Optional category filter (e.g. 'tops', 'jeans')"
    )
    exclude_platform: Optional[str] = Field(
        None, description="Optional platform to exclude from results"
    )

    @field_validator("image_url")
    @classmethod
    def check_image_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_image_url(v, "image_url")
        return v

    @field_validator("text_query")
    @classmethod
    def check_text_query(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("text_query must not be empty or whitespace.")
            return trimmed
        return v

    @model_validator(mode="after")
    def verify_query_provided(self) -> SimilarProductsRequest:
        if not self.image_url and not self.text_query:
            raise ValueError("At least one of 'image_url' or 'text_query' must be provided.")
        return self


class FakeReviewCheckRequest(BaseModel):
    """
    Request model for matching review photos against stock photos.
    """
    review_image_urls: List[str] = Field(..., description="List of reviewer photo URLs")
    stock_image_urls: List[str] = Field(..., description="List of product stock image URLs")
    threshold: float = Field(0.45, description="Mismatch score threshold for flagging")

    @field_validator("review_image_urls")
    @classmethod
    def check_review_urls(cls, v: List[str]) -> List[str]:
        return validate_urls_list(v, "review_image_urls")

    @field_validator("stock_image_urls")
    @classmethod
    def check_stock_urls(cls, v: List[str]) -> List[str]:
        return validate_urls_list(v, "stock_image_urls")

    @field_validator("threshold")
    @classmethod
    def check_threshold(cls, v: float) -> float:
        return validate_detection_threshold(v)
