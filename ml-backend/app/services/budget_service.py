"""
Budget Service — ml-backend.

Responsibility: Implement the budget optimization logic to allocate a given
outfit budget across clothes categories for specific occasions.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.models.budget_models import (
    BudgetOptimizeRequest,
    BudgetOptimizeResponse,
    BudgetAllocationItem,
)

logger = logging.getLogger(__name__)

# Occasion templates: category -> (weight, description)
OCCASION_TEMPLATES: dict[str, dict[str, tuple[float, str]]] = {
    "wedding": {
        "Sherwani / Kurta / Saree (Hero)": (0.50, "The main ethnic outfit. Allocate the largest portion here for premium fabric and detailing."),
        "Bottomwear (Pyjama / Churidar / Skirt)": (0.20, "Complementary bottomwear. Focus on fit and comfort."),
        "Footwear (Mojaris / Juttis / Sandals)": (0.15, "Traditional Indian footwear to complete the ethnic look."),
        "Accessories (Safa / Dupatta / Jewelry / Watch)": (0.15, "Finishing touches that elevate the festive outfit."),
    },
    "festive": {
        "Kurta / Lehenga / Saree (Hero)": (0.50, "The main ethnic outfit. Allocate the largest portion here for premium fabric and detailing."),
        "Bottomwear (Pyjama / Churidar / Skirt)": (0.20, "Complementary bottomwear. Focus on fit and comfort."),
        "Footwear (Mojaris / Juttis / Sandals)": (0.15, "Traditional Indian footwear to complete the ethnic look."),
        "Accessories (Safa / Dupatta / Jewelry / Watch)": (0.15, "Finishing touches that elevate the festive outfit."),
    },
    "formal": {
        "Suit Blazer / Jacket (Hero)": (0.45, "The anchor of a formal outfit. Prioritize structure, fabric weight, and tailoring quality."),
        "Formal Shirt": (0.15, "A crisp cotton shirt in classic colors (white, light blue)."),
        "Trousers": (0.15, "Well-fitted trousers matching or contrasting with the blazer."),
        "Footwear (Oxfords / Loafers)": (0.15, "Clean leather formal shoes. Crucial for a professional impression."),
        "Accessories (Belt / Tie / Watch)": (0.10, "Subtle details. Keep them classic and minimal."),
    },
    "office": {
        "Suit Blazer / Jacket (Hero)": (0.45, "The anchor of a formal outfit. Prioritize structure, fabric weight, and tailoring quality."),
        "Formal Shirt": (0.15, "A crisp cotton shirt in classic colors (white, light blue)."),
        "Trousers": (0.15, "Well-fitted trousers matching or contrasting with the blazer."),
        "Footwear (Oxfords / Loafers)": (0.15, "Clean leather formal shoes. Crucial for a professional impression."),
        "Accessories (Belt / Tie / Watch)": (0.10, "Subtle details. Keep them classic and minimal."),
    },
    "casual": {
        "Jeans / Chinos / Pants (Hero)": (0.35, "Daily wear anchor. Spend on high-quality denim that lasts."),
        "Tops / Shirts / T-shirts": (0.30, "Comfortable and expressive tops. Easy to mix and match."),
        "Footwear / Sneakers": (0.25, "Versatile sneakers or casual shoes for all-day comfort."),
        "Accessories (Sunglasses / Belt)": (0.10, "Simple additions like sunglasses or a minimal watch."),
    },
    "party": {
        "Statement Dress / Top (Hero)": (0.40, "The main focus piece. Choose a standout color, pattern, or cut."),
        "Bottoms / Pants / Skirt": (0.20, "Sleek bottoms to balance the statement top."),
        "Outerwear / Jacket": (0.20, "A stylish bomber, denim, or leather jacket to layer the look."),
        "Footwear (Heels / Boots)": (0.15, "Elevated footwear like boots or heels to stand out."),
        "Accessories": (0.05, "Minimal jewelry or bag to keep focus on the main outfit."),
    },
    "sports": {
        "Athletic Footwear / Running Shoes (Hero)": (0.40, "Most critical activewear component. Spend here for cushioning and injury prevention."),
        "Activewear Top / Tee": (0.25, "Moisture-wicking, breathable athletic fabric."),
        "Track Pants / Shorts": (0.25, "Flexible bottoms optimized for movement."),
        "Accessories (Smart Band / Socks / Cap)": (0.10, "Useful additions like running socks or wrist bands."),
    },
    "activewear": {
        "Athletic Footwear / Running Shoes (Hero)": (0.40, "Most critical activewear component. Spend here for cushioning and injury prevention."),
        "Activewear Top / Tee": (0.25, "Moisture-wicking, breathable athletic fabric."),
        "Track Pants / Shorts": (0.25, "Flexible bottoms optimized for movement."),
        "Accessories (Smart Band / Socks / Cap)": (0.10, "Useful additions like running socks or wrist bands."),
    },
}


def optimize_budget(request: BudgetOptimizeRequest) -> BudgetOptimizeResponse:
    """
    Perform budget allocation across clothing categories based on the occasion.
    """
    logger.info(
        "[budget_service] optimizing budget %d for occasion %s",
        request.budget_inr,
        request.occasion,
    )

    occasion_key = request.occasion.strip().lower()
    template = OCCASION_TEMPLATES.get(occasion_key, OCCASION_TEMPLATES["casual"])

    # If the user passed custom categories, filter or build dynamic weights
    if request.custom_categories:
        # Standardize custom category names
        custom_set = {c.strip() for c in request.custom_categories if c.strip()}
        if custom_set:
            # Try to inherit weights from template if there's any match, otherwise assign equal weight
            filtered_template = {}
            total_inherited_weight = 0.0

            for cat, info in template.items():
                # Check if this template category matches any custom category substring
                matched = False
                for custom_cat in custom_set:
                    if custom_cat.lower() in cat.lower() or cat.lower() in custom_cat.lower():
                        filtered_template[custom_cat] = (info[0], info[1])
                        total_inherited_weight += info[0]
                        matched = True
                        break

            # Fill in remaining custom categories that didn't match the template
            unmatched = custom_set - set(filtered_template.keys())
            if unmatched:
                remaining_weight = max(0.1, 1.0 - total_inherited_weight)
                default_weight = remaining_weight / len(unmatched)
                for cat in unmatched:
                    filtered_template[cat] = (default_weight, "Custom category requested by user.")

            template = filtered_template

    # Re-normalize template weights to sum to exactly 1.0
    weight_sum = sum(info[0] for info in template.values())
    normalized_template = {}
    for cat, info in template.items():
        w = info[0] / weight_sum if weight_sum > 0 else (1.0 / len(template))
        normalized_template[cat] = (w, info[1])

    # Initial allocation computation (raw float)
    allocations_raw = {}
    for cat, (weight, desc) in normalized_template.items():
        allocations_raw[cat] = weight * request.budget_inr

    # Round all values to nearest 50 INR to avoid ugly values
    allocations_rounded = {}
    for cat, val in allocations_raw.items():
        allocations_rounded[cat] = max(50, round(val / 50) * 50)

    # Adjust rounding errors so the total sum matches request.budget_inr exactly
    current_sum = sum(allocations_rounded.values())
    diff = request.budget_inr - current_sum

    if diff != 0:
        # Find the category with the highest weight to apply the adjustment
        hero_category = max(normalized_template.keys(), key=lambda k: normalized_template[k][0])
        # Apply the diff directly to the hero piece to guarantee exact sum match
        allocations_rounded[hero_category] = max(50, allocations_rounded[hero_category] + diff)

    # Re-verify and construct items
    final_sum = sum(allocations_rounded.values())
    unused = request.budget_inr - final_sum

    items: list[BudgetAllocationItem] = []
    for cat, amt in allocations_rounded.items():
        weight = normalized_template[cat][0]
        desc = normalized_template[cat][1]
        items.append(BudgetAllocationItem(
            category=cat,
            allocated_amount_inr=amt,
            percentage=round((amt / request.budget_inr) * 100, 2),
            description=desc
        ))

    # Generate tips based on budget brackets
    tips = []
    budget = request.budget_inr
    if budget < 2000:
        tips.append("With a tight budget, consider local street markets (e.g., Sarojini Nagar, Colaba Causeway, Commercial Street) or factory outlets.")
        tips.append("Prioritize the hero piece first; you can reuse bottoms and accessories you already own.")
        tips.append("Look for basic materials like polyester-cotton blends which are cheaper and durable.")
    elif budget < 10000:
        tips.append("Shop during seasonal sales on online platforms (Myntra, Ajio, Tata Cliq) to get mid-tier brand discounts.")
        tips.append("Invest more in your footwear and bottoms, as these are worn repeatedly across different outfits.")
        tips.append("Consider fast-fashion staples that offer good style value for money.")
    else:
        tips.append("For high budgets, invest in premium fabrics like pure cotton, linen, silk, or genuine leather.")
        tips.append("Look at custom tailoring for ethnic outfits or formal blazers to ensure a premium fit.")
        tips.append("Consider boutique designers or premium Indian brands for unique, high-quality items.")

    # Sort items by allocation size (descending)
    items.sort(key=lambda x: x.allocated_amount_inr, reverse=True)

    return BudgetOptimizeResponse(
        total_budget_inr=request.budget_inr,
        occasion=request.occasion,
        allocations=items,
        allocated_sum_inr=final_sum,
        unused_budget_inr=unused,
        tips=tips,
    )
