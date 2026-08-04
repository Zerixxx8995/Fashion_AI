"""
Wardrobe Service — ml-backend.

Responsibility: Gap analysis algorithm — identify which clothing categories
a user's wardrobe is missing and compute a coverage score.

Architecture rules:
  Layer: Service
  One job: Gap analysis business logic and orchestration
  Never does: HTTP routing, direct DB access for the analysis itself,
               raw Pydantic model construction (that's the controller's job)

Gap Analysis Algorithm:
  1. Normalise the category of each wardrobe item to a canonical set.
  2. Compute which capsule categories are represented vs. missing.
  3. Score coverage = owned_canonical / total_capsule_categories.
  4. Prioritise missing categories by their importance tier.
  5. If a budget is provided, allocate it across missing categories
     proportionally to priority weight.

Capsule Wardrobe Definition (Indian fashion context):
  The standard Indian capsule wardrobe covers 10 canonical categories.
  Missing categories are flagged HIGH / MEDIUM / LOW by importance.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.models.wardrobe_models import (
    GapAnalysisRequest,
    GapAnalysisResponse,
    GapCategory,
    WardrobeItem,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Capsule wardrobe definition
# ---------------------------------------------------------------------------

# Canonical category → (display name, priority tier, priority weight)
# Priority weight is used for proportional budget allocation.
CAPSULE_CATEGORIES: dict[str, tuple[str, str, int]] = {
    "tops":       ("Tops / T-shirts",       "high",   30),
    "bottoms":    ("Bottoms / Jeans",        "high",   25),
    "ethnic":     ("Ethnic Wear / Kurtas",   "high",   20),
    "formals":    ("Formals",                "medium", 15),
    "outerwear":  ("Outerwear / Jackets",    "medium", 10),
    "footwear":   ("Footwear",               "high",   25),
    "accessories":("Accessories",            "low",     5),
    "sportswear": ("Sportswear / Activewear","medium", 10),
    "ethnic_acc": ("Ethnic Accessories",     "low",     5),
    "innerwear":  ("Innerwear / Basics",     "medium", 15),
}

PRIORITY_REASONS: dict[str, str] = {
    "tops":        "Tops are the most visible part of any outfit — critical for daily variety.",
    "bottoms":     "Bottoms are a wardrobe foundation — missing this limits full outfit combinations.",
    "ethnic":      "Ethnic wear is essential for Indian occasions, festivals, and weddings.",
    "formals":     "Formals are needed for professional settings and interviews.",
    "outerwear":   "Outerwear extends outfit seasons and is required in winter months.",
    "footwear":    "Footwear completes every outfit and is often the first thing noticed.",
    "accessories": "Accessories multiply outfit variations without adding bulk.",
    "sportswear":  "Activewear supports an active lifestyle and gym / sports activities.",
    "ethnic_acc":  "Ethnic accessories (dupattas, jhumkas) complete traditional looks.",
    "innerwear":   "Basics and innerwear are wardrobe essentials that affect everyday comfort.",
}

# Keyword synonyms that map to canonical categories
CATEGORY_SYNONYMS: dict[str, str] = {
    # tops
    "top": "tops", "t-shirt": "tops", "tshirt": "tops", "shirt": "tops",
    "blouse": "tops", "crop top": "tops", "tank": "tops", "cami": "tops",
    # bottoms
    "bottom": "bottoms", "jeans": "bottoms", "trouser": "bottoms",
    "pants": "bottoms", "skirt": "bottoms", "shorts": "bottoms",
    "leggings": "bottoms", "palazzos": "bottoms",
    # ethnic
    "kurta": "ethnic", "kurti": "ethnic", "salwar": "ethnic",
    "ethnic": "ethnic", "saree": "ethnic", "sari": "ethnic",
    "lehenga": "ethnic", "anarkali": "ethnic", "suit": "ethnic",
    "dupatta": "ethnic_acc",
    # formals
    "formal": "formals", "blazer": "formals", "suit jacket": "formals",
    "office wear": "formals", "formal shirt": "formals",
    # outerwear
    "jacket": "outerwear", "coat": "outerwear", "sweater": "outerwear",
    "hoodie": "outerwear", "cardigan": "outerwear", "shawl": "outerwear",
    "sweatshirt": "outerwear", "pullover": "outerwear",
    # footwear
    "shoes": "footwear", "sandals": "footwear", "heels": "footwear",
    "sneakers": "footwear", "boots": "footwear", "flats": "footwear",
    "chappals": "footwear", "loafers": "footwear", "slip-ons": "footwear",
    # accessories
    "bag": "accessories", "purse": "accessories", "belt": "accessories",
    "watch": "accessories", "sunglasses": "accessories", "scarf": "accessories",
    "necklace": "accessories", "earrings": "accessories", "bracelet": "accessories",
    # sportswear
    "sportswear": "sportswear", "activewear": "sportswear", "gym": "sportswear",
    "track pants": "sportswear", "yoga pants": "sportswear",
    "sports shoes": "footwear", "running shoes": "footwear",
    # ethnic accessories
    "jhumka": "ethnic_acc", "jhumkas": "ethnic_acc", "ethnic accessory": "ethnic_acc",
    "bindi": "ethnic_acc", "bangles": "ethnic_acc", "maang tikka": "ethnic_acc",
    # innerwear / basics
    "innerwear": "innerwear", "underwear": "innerwear", "basics": "innerwear",
    "vest": "innerwear", "bra": "innerwear", "socks": "innerwear",
}


# ---------------------------------------------------------------------------
# Core algorithm
# ---------------------------------------------------------------------------

def _normalise_category(raw: Optional[str]) -> Optional[str]:
    """
    Map a free-text category string to a canonical key.
    Returns None if unrecognised.
    """
    if not raw:
        return None
    key = raw.strip().lower()
    # Direct canonical match
    if key in CAPSULE_CATEGORIES:
        return key
    # Synonym lookup
    for synonym, canonical in CATEGORY_SYNONYMS.items():
        if synonym in key:
            return canonical
    return None


def run_gap_analysis(request: GapAnalysisRequest) -> GapAnalysisResponse:
    """
    Execute the wardrobe gap analysis.

    Args:
        request: GapAnalysisRequest with wardrobe items and optional budget.

    Returns:
        GapAnalysisResponse with missing categories, coverage score, and
        optional budget allocation per missing category.
    """
    logger.info(
        "[wardrobe_service] gap analysis: %d items, budget=%s",
        len(request.wardrobe),
        request.budget_inr,
    )

    # Step 1 — Normalise each item's category
    owned_canonical: set[str] = set()
    for item in request.wardrobe:
        canonical = _normalise_category(item.category)
        if canonical:
            owned_canonical.add(canonical)

    owned_list = sorted(owned_canonical)
    all_capsule_keys = set(CAPSULE_CATEGORIES.keys())
    missing_keys = all_capsule_keys - owned_canonical

    # Step 2 — Coverage score
    coverage = len(owned_canonical) / len(all_capsule_keys)

    # Step 3 — Build missing category list, sorted by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}

    missing_sorted = sorted(
        missing_keys,
        key=lambda k: (priority_order[CAPSULE_CATEGORIES[k][1]], k),
    )

    # Step 4 — Budget allocation (proportional to priority weight)
    # Only allocate among missing categories
    total_weight = sum(CAPSULE_CATEGORIES[k][2] for k in missing_sorted)

    missing_categories: list[GapCategory] = []
    for key in missing_sorted:
        display_name, priority, weight = CAPSULE_CATEGORIES[key]
        suggested_budget: Optional[int] = None

        if request.budget_inr and total_weight > 0:
            # Allocate proportionally; round to nearest 100 INR
            raw_budget = (weight / total_weight) * request.budget_inr
            suggested_budget = max(100, round(raw_budget / 100) * 100)

        missing_categories.append(GapCategory(
            category=display_name,
            priority=priority,
            reason=PRIORITY_REASONS[key],
            suggested_budget_inr=suggested_budget,
        ))

    # Step 5 — Analysis note
    if coverage >= 0.8:
        note = "Your wardrobe is well-rounded! Just a few gaps to fill."
    elif coverage >= 0.5:
        note = "Good foundation — focus on high-priority gaps to maximise outfit combinations."
    else:
        note = "Your wardrobe has significant gaps. Start with high-priority essentials."

    logger.info(
        "[wardrobe_service] coverage=%.2f owned=%d missing=%d",
        coverage, len(owned_canonical), len(missing_keys),
    )

    return GapAnalysisResponse(
        owned_categories=[CAPSULE_CATEGORIES[k][0] for k in owned_list],
        missing_categories=missing_categories,
        coverage_score=round(coverage, 4),
        total_items=len(request.wardrobe),
        analysis_note=note,
    )
