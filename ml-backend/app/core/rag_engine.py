"""
RAG Engine — ml-backend/app/core/rag_engine.py

Responsibility: Pure LangChain RAG logic — prompt construction and LLM call.
No HTTP. No business logic. No database access. No caching.

Layer rules (core):
  - Only receives structured context dicts — no raw DB models.
  - Calls integrations/llm_client.py to execute the Gemini call.
  - Returns the explanation string directly — no response shaping.

Design constraints (from spec):
  - Temperature: 0.3 — factual and consistent, not creative.
  - Prompt explicitly says "Based ONLY on the data provided below" — no hallucination.
  - Output length enforcement: caller validates 80–350 chars.
"""

from __future__ import annotations

import logging
from typing import Any

from app.integrations.llm_client import get_llm_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt Templates
# ---------------------------------------------------------------------------

_TREND_PROMPT_TEMPLATE = """\
You are a fashion trend analyst for the Indian market.
Based ONLY on the data provided below, write 2-3 sentences explaining:
- Why this trend is popular right now in India
- Who it suits
- How long it is likely to last given its lifecycle stage

Use a conversational, friendly tone. No bullet points. No markdown.
Reference specific products or reviews from the data — do not invent details.

Data:
Trend: {trend_name}
Category: {category}
Lifecycle stage: {lifecycle_stage}
Origin: {origin}
Signal score: {signal_score}

Top matching products:
{formatted_products}

Sample reviews mentioning this trend:
{formatted_reviews}
"""

_RECOMMENDATION_PROMPT_TEMPLATE = """\
You are a personal stylist for an Indian fashion app.
Based ONLY on the data provided below, write 2 sentences explaining
why this product suits this specific user.
Reference their wardrobe and body type specifically.
Friendly tone. No bullet points. No markdown. Do not invent details.

Data:
Product: {product_name}
Brand: {brand}
Category: {category}
Price: \u20b9{price_inr}

User profile:
- Body type: {body_type}
- Style preferences: {style_preferences}

Most similar items already in user's wardrobe:
{formatted_wardrobe_items}
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_trend_explanation(
    *,
    trend_name: str,
    category: str,
    lifecycle_stage: str,
    origin: str,
    signal_score: float,
    products: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
) -> str:
    """
    Generate a natural-language explanation for why a trend is popular.

    Args:
        trend_name:       Display name of the trend (e.g. "Oversized Blazers").
        category:         Fashion category (e.g. "tops", "jeans").
        lifecycle_stage:  One of "emerging", "peaking", "dying".
        origin:           Where the trend was detected (e.g. "Myntra Bestsellers").
        signal_score:     Trend signal score 0–10.
        products:         List of top matching products. Each dict has keys:
                          name (str), brand (str), price_inr (int), platform (str).
        reviews:          List of top reviews. Each dict has keys:
                          reviewer_text (str), product_name (str).

    Returns:
        Explanation string (expected 80–350 chars).
    """
    formatted_products = _format_products(products)
    formatted_reviews = _format_reviews(reviews)

    prompt = _TREND_PROMPT_TEMPLATE.format(
        trend_name=trend_name,
        category=category,
        lifecycle_stage=lifecycle_stage,
        origin=origin,
        signal_score=round(signal_score, 1),
        formatted_products=formatted_products,
        formatted_reviews=formatted_reviews,
    )

    logger.info(
        "[rag_engine] generating trend explanation for '%s' (stage=%s)",
        trend_name, lifecycle_stage
    )

    client = get_llm_client()
    explanation = client.generate(prompt)

    logger.info(
        "[rag_engine] trend explanation generated len=%d", len(explanation)
    )
    return explanation


def generate_recommendation_explanation(
    *,
    product_name: str,
    brand: str,
    category: str,
    price_inr: int,
    body_type: str,
    style_preferences: list[str],
    wardrobe_items: list[dict[str, Any]],
) -> str:
    """
    Generate a personalised natural-language explanation for a style recommendation.

    Args:
        product_name:       Full product name.
        brand:              Brand string.
        category:           Fashion category.
        price_inr:          Price in Indian Rupees.
        body_type:          User's body type (e.g. "hourglass", "rectangle").
        style_preferences:  List of style preference strings (e.g. ["casual", "streetwear"]).
        wardrobe_items:     List of most similar wardrobe items. Each dict has keys:
                            name (str), category (str), color (str).

    Returns:
        Explanation string (expected 80–350 chars).
    """
    formatted_wardrobe = _format_wardrobe_items(wardrobe_items)
    prefs_str = ", ".join(style_preferences) if style_preferences else "not specified"

    prompt = _RECOMMENDATION_PROMPT_TEMPLATE.format(
        product_name=product_name,
        brand=brand,
        category=category,
        price_inr=price_inr,
        body_type=body_type,
        style_preferences=prefs_str,
        formatted_wardrobe_items=formatted_wardrobe,
    )

    logger.info(
        "[rag_engine] generating recommendation explanation for '%s'", product_name
    )

    client = get_llm_client()
    explanation = client.generate(prompt)

    logger.info(
        "[rag_engine] recommendation explanation generated len=%d", len(explanation)
    )
    return explanation


# ---------------------------------------------------------------------------
# Formatting helpers — internal only
# ---------------------------------------------------------------------------

def _format_products(products: list[dict[str, Any]]) -> str:
    """Format a list of product dicts into a readable text block for the prompt."""
    if not products:
        return "No matching products available."
    lines = []
    for i, p in enumerate(products, 1):
        name = p.get("name", "Unknown Product")
        brand = p.get("brand", "Unknown Brand")
        price = p.get("price_inr", 0)
        platform = p.get("platform", "unknown")
        lines.append(
            f"{i}. {name} by {brand} — \u20b9{price} on {platform.capitalize()}"
        )
    return "\n".join(lines)


def _format_reviews(reviews: list[dict[str, Any]]) -> str:
    """Format a list of review dicts into a readable text block for the prompt."""
    if not reviews:
        return "No reviews available."
    lines = []
    for i, r in enumerate(reviews, 1):
        text = r.get("reviewer_text", "")
        product = r.get("product_name", "")
        if text:
            snippet = text[:150] + "..." if len(text) > 150 else text
            prefix = f"[{product}] " if product else ""
            lines.append(f'{i}. {prefix}"{snippet}"')
    return "\n".join(lines) if lines else "No reviews available."


def _format_wardrobe_items(items: list[dict[str, Any]]) -> str:
    """Format a list of wardrobe item dicts into a readable text block for the prompt."""
    if not items:
        return "Wardrobe is empty."
    lines = []
    for i, item in enumerate(items, 1):
        name = item.get("name", "Unknown Item")
        category = item.get("category", "")
        color = item.get("color", "")
        details = " | ".join(filter(None, [category, color]))
        lines.append(f"{i}. {name}" + (f" ({details})" if details else ""))
    return "\n".join(lines)
