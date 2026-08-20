"""
Recommendations Router — ml-backend.

Endpoint:
  POST /api/v1/recommendations  — Personalised style recommendations by body type and taste preferences
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional
from fastapi import APIRouter, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


class RecommendationRequest(BaseModel):
    user_id: Optional[str] = "anonymous"
    body_type: Optional[str] = "Hourglass"
    taste_preferences: List[str] = Field(default_factory=lambda: ["Streetwear", "Minimalist"])
    limit: int = Field(default=8, ge=1, le=50)


class RecommendedProduct(BaseModel):
    id: str
    name: str
    brand: str
    price_inr: int
    platform: str
    image_url: str
    match_score: float
    reason: str


class RecommendationResponse(BaseModel):
    body_type: str
    taste_preferences: List[str]
    recommendations: List[RecommendedProduct]
    count: int


RECOMMENDATION_CATALOG = [
    {
        "id": "rec-01",
        "name": "High-Waist Wide Leg Cargo Trousers",
        "brand": "Zara",
        "price_inr": 2990,
        "platform": "myntra",
        "image_url": "https://images.unsplash.com/photo-1517445312882-bc9910d016b7?w=600",
        "body_types": ["Hourglass", "Pear", "Athletic"],
        "aesthetics": ["Streetwear", "Y2K"],
        "reason": "Accentuates waist definition while providing relaxed leg comfort.",
    },
    {
        "id": "rec-02",
        "name": "Oversized Heavyweight Cotton Graphic Hoodie",
        "brand": "H&M",
        "price_inr": 2299,
        "platform": "ajio",
        "image_url": "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=600",
        "body_types": ["Rectangle", "Athletic", "Oval"],
        "aesthetics": ["Streetwear", "Minimalist"],
        "reason": "Relaxed drop-shoulder silhouette matching urban streetwear trends.",
    },
    {
        "id": "rec-03",
        "name": "Silk Blend Tiered Printed Maxi Anarkali",
        "brand": "Biba",
        "price_inr": 3999,
        "platform": "myntra",
        "image_url": "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=600",
        "body_types": ["Hourglass", "Pear", "Oval"],
        "aesthetics": ["Ethnic Fusion", "Vintage"],
        "reason": "Flowing flared silhouette that creates balanced proportions.",
    },
    {
        "id": "rec-04",
        "name": "Minimalist Linen Blend Blazer",
        "brand": "Mango",
        "price_inr": 4590,
        "platform": "amazon",
        "image_url": "https://images.unsplash.com/photo-1544441893-675973e31985?w=600",
        "body_types": ["Rectangle", "Hourglass", "Athletic"],
        "aesthetics": ["Minimalist", "Vintage"],
        "reason": "Structured shoulders add clean architectural lines.",
    },
    {
        "id": "rec-05",
        "name": "Cropped Corduroy Trucker Jacket",
        "brand": "Levi's",
        "price_inr": 3499,
        "platform": "flipkart",
        "image_url": "https://images.unsplash.com/photo-1525450824786-227cbef70703?w=600",
        "body_types": ["Hourglass", "Rectangle"],
        "aesthetics": ["Vintage", "Y2K"],
        "reason": "Cropped hemline highlights waistline position naturally.",
    },
    {
        "id": "rec-06",
        "name": "Chunky Platform Retro Sneakers",
        "brand": "Puma",
        "price_inr": 3299,
        "platform": "meesho",
        "image_url": "https://images.unsplash.com/photo-1552346154-21d32810aba3?w=600",
        "body_types": ["Hourglass", "Rectangle", "Athletic", "Pear", "Oval"],
        "aesthetics": ["Streetwear", "Y2K"],
        "reason": "Chunky platform sole completes retro-streetwear outfits.",
    },
]


@router.post("", response_model=RecommendationResponse)
def get_recommendations(body: RecommendationRequest) -> dict[str, Any]:
    """
    Generate personalized recommendations based on body type & aesthetic taste.
    """
    body_type = body.body_type or "Hourglass"
    tastes = [t.lower() for t in (body.taste_preferences or ["Streetwear"])]

    scored_items: List[RecommendedProduct] = []

    for item in RECOMMENDATION_CATALOG:
        match_score = 0.70
        if body_type in item["body_types"]:
            match_score += 0.15
        if any(a.lower() in tastes for a in item["aesthetics"]):
            match_score += 0.12

        match_score = min(0.98, max(0.65, match_score))

        scored_items.append(
            RecommendedProduct(
                id=item["id"],
                name=item["name"],
                brand=item["brand"],
                price_inr=item["price_inr"],
                platform=item["platform"],
                image_url=item["image_url"],
                match_score=round(match_score, 2),
                reason=item["reason"],
            )
        )

    # Sort by match score descending
    scored_items.sort(key=lambda x: x.match_score, reverse=True)
    results = scored_items[: body.limit]

    return {
        "body_type": body_type,
        "taste_preferences": body.taste_preferences or [],
        "recommendations": [r.dict() for r in results],
        "count": len(results),
    }
