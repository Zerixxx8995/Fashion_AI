"""
Explanation Service — ml-backend/app/services/explanation_service.py

Responsibility: Retrieval orchestration for both trend and recommendation
explanation flows. Checks Redis cache first, retrieves context from
PostgreSQL + Pinecone on cache miss, delegates generation to rag_engine,
caches result, returns explanation dict.

Layer rules (service):
  - Knows about DB models (SQLAlchemy).
  - Knows about integrations (pinecone_client, llm_client via rag_engine).
  - Does NOT contain HTTP knowledge (lives in routers/controllers).
  - Does NOT contain raw LLM/prompt logic (lives in core/rag_engine).

Caching (from spec):
  - Trend explanations:      Redis key explanation:trend:{trend_id}  — TTL 24h
  - Recommendation explanations: Redis key explanation:rec:{user_id}:{product_id} — TTL 6h
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core import rag_engine
from app.db.models.trend_item import TrendItem
from app.db.models.product import Product
from app.db.models.review import Review
from app.db.models.user import User
from app.db.models.wardrobe_item import WardrobeItem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis client — uses Upstash REST API (same pattern as the rest of the app)
# ---------------------------------------------------------------------------

_redis_client: Optional[Any] = None


def _get_redis() -> Any:
    """
    Lazily initialise and return the Upstash Redis REST client.
    Falls back gracefully if env vars are missing (e.g. local dev without Redis).
    """
    global _redis_client  # noqa: PLW0603
    if _redis_client is not None:
        return _redis_client

    url = os.getenv("UPSTASH_REDIS_REST_URL")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN")

    if not url or not token:
        logger.warning(
            "[explanation_service] UPSTASH_REDIS_REST_URL or TOKEN not set — "
            "Redis caching disabled. All requests will call the LLM."
        )
        return None

    try:
        from upstash_redis import Redis  # type: ignore[import]
        _redis_client = Redis(url=url, token=token)
        logger.info("[explanation_service] Upstash Redis client initialised")
        return _redis_client
    except Exception as exc:
        logger.warning("[explanation_service] Redis client init failed: %s — caching disabled", exc)
        return None


def _cache_get(key: str) -> Optional[str]:
    """Get a value from Redis cache. Returns None if missing or on error."""
    redis = _get_redis()
    if redis is None:
        return None
    try:
        value = redis.get(key)
        if value is not None:
            logger.debug("[explanation_service] cache HIT key=%s", key)
        else:
            logger.debug("[explanation_service] cache MISS key=%s", key)
        return value
    except Exception as exc:
        logger.warning("[explanation_service] cache GET failed key=%s: %s", key, exc)
        return None


def _cache_set(key: str, value: str, ttl_seconds: int) -> None:
    """Set a value in Redis with TTL. Silently ignores errors."""
    redis = _get_redis()
    if redis is None:
        return
    try:
        redis.setex(key, ttl_seconds, value)
        logger.debug("[explanation_service] cache SET key=%s ttl=%ds", key, ttl_seconds)
    except Exception as exc:
        logger.warning("[explanation_service] cache SET failed key=%s: %s", key, exc)


# ---------------------------------------------------------------------------
# TTL constants
# ---------------------------------------------------------------------------

_TREND_TTL_SECONDS = 24 * 60 * 60      # 24 hours
_REC_TTL_SECONDS = 6 * 60 * 60         # 6 hours

# ---------------------------------------------------------------------------
# Public service API
# ---------------------------------------------------------------------------


def get_trend_explanation(
    db: Session,
    *,
    trend_id: str,
) -> dict[str, Any]:
    """
    Return a trend explanation. Checks Redis first; generates via RAG if cache miss.

    Args:
        db:       SQLAlchemy session.
        trend_id: UUID string of the TrendItem.

    Returns:
        Dict matching the spec response shape:
        {
            "trend_id": str,
            "trend_name": str,
            "explanation": str,
            "cached": bool,
            "generated_at": str (ISO-8601),
        }

    Raises:
        KeyError: If trend_id is not found in the database.
    """
    cache_key = f"explanation:trend:{trend_id}"

    # 1. Check Redis cache
    cached_raw = _cache_get(cache_key)
    if cached_raw:
        try:
            cached_data = json.loads(cached_raw)
            cached_data["cached"] = True
            return cached_data
        except json.JSONDecodeError:
            logger.warning(
                "[explanation_service] invalid cached JSON for key=%s — regenerating", cache_key
            )

    # 2. Cache miss — fetch trend from DB
    trend = db.scalar(select(TrendItem).where(TrendItem.id == trend_id))
    if trend is None:
        raise KeyError(f"TrendItem with id={trend_id!r} not found")

    # 3. Retrieve top matching products from DB (those in the same category)
    products_stmt = (
        select(Product)
        .where(Product.category == trend.category)
        .limit(5)
    )
    db_products = list(db.scalars(products_stmt).all())
    products_context = [
        {
            "name": p.name,
            "brand": p.brand or "Unknown Brand",
            "price_inr": p.price_inr or 0,
            "platform": p.platform,
        }
        for p in db_products
    ]

    # 4. Retrieve top reviews for those products from DB
    reviews_context: list[dict[str, Any]] = []
    for p in db_products[:3]:  # top 3 products, up to 3 reviews each
        reviews_stmt = (
            select(Review)
            .where(Review.product_id == p.id)
            .where(Review.reviewer_text.isnot(None))
            .limit(3)
        )
        db_reviews = list(db.scalars(reviews_stmt).all())
        for r in db_reviews:
            if r.reviewer_text:
                reviews_context.append({
                    "reviewer_text": r.reviewer_text,
                    "product_name": p.name,
                })
        if len(reviews_context) >= 9:
            break

    # 5. Generate explanation via RAG engine
    explanation = rag_engine.generate_trend_explanation(
        trend_name=trend.name,
        category=trend.category,
        lifecycle_stage=trend.lifecycle_stage,
        origin=trend.origin,
        signal_score=trend.signal_score,
        products=products_context,
        reviews=reviews_context,
    )

    # 6. Build response
    generated_at = datetime.now(timezone.utc).isoformat()
    response = {
        "trend_id": str(trend.id),
        "trend_name": trend.name,
        "explanation": explanation,
        "cached": False,
        "generated_at": generated_at,
    }

    # 7. Cache the storeable part (without the "cached" flag — set to False for storage)
    cacheable = {**response, "cached": False}
    _cache_set(cache_key, json.dumps(cacheable), _TREND_TTL_SECONDS)

    logger.info(
        "[explanation_service] trend explanation generated and cached trend_id=%s", trend_id
    )
    return response


def get_recommendation_explanation(
    db: Session,
    *,
    product_id: str,
    user_id: str,
) -> dict[str, Any]:
    """
    Return a personalised recommendation explanation. Checks Redis first.

    Args:
        db:         SQLAlchemy session.
        product_id: UUID string of the Product.
        user_id:    UUID string of the User (clerk_id or internal user.id).

    Returns:
        Dict matching the spec response shape:
        {
            "product_id": str,
            "product_name": str,
            "explanation": str,
            "cached": bool,
            "generated_at": str (ISO-8601),
        }

    Raises:
        KeyError: If product_id or user_id is not found.
    """
    cache_key = f"explanation:rec:{user_id}:{product_id}"

    # 1. Check Redis cache
    cached_raw = _cache_get(cache_key)
    if cached_raw:
        try:
            cached_data = json.loads(cached_raw)
            cached_data["cached"] = True
            return cached_data
        except json.JSONDecodeError:
            logger.warning(
                "[explanation_service] invalid cached JSON for key=%s — regenerating", cache_key
            )

    # 2. Cache miss — fetch product from DB
    product = db.scalar(select(Product).where(Product.id == product_id))
    if product is None:
        raise KeyError(f"Product with id={product_id!r} not found")

    # 3. Fetch user profile from DB
    # user_id can be either the internal UUID or the clerk_id
    user = db.scalar(
        select(User).where(
            (User.id == user_id) | (User.clerk_id == user_id)
        )
    )
    if user is None:
        raise KeyError(f"User with id={user_id!r} not found")

    # 4. Fetch wardrobe items most similar to this product's category
    wardrobe_stmt = (
        select(WardrobeItem)
        .where(WardrobeItem.user_id == user.id)
        .where(WardrobeItem.category == product.category)
        .limit(5)
    )
    wardrobe_items_db = list(db.scalars(wardrobe_stmt).all())

    # Fallback: if no exact category match, get any wardrobe items
    if not wardrobe_items_db:
        wardrobe_stmt = (
            select(WardrobeItem)
            .where(WardrobeItem.user_id == user.id)
            .limit(5)
        )
        wardrobe_items_db = list(db.scalars(wardrobe_stmt).all())

    wardrobe_context = [
        {
            "name": w.name,
            "category": w.category or "clothing",
            "color": w.color or "unknown",
        }
        for w in wardrobe_items_db
    ]

    # 5. Parse style preferences (stored as JSON string in DB)
    style_preferences: list[str] = []
    if user.style_preferences:
        try:
            style_preferences = json.loads(user.style_preferences)
        except (json.JSONDecodeError, TypeError):
            style_preferences = [user.style_preferences]

    # 6. Generate explanation via RAG engine
    explanation = rag_engine.generate_recommendation_explanation(
        product_name=product.name,
        brand=product.brand or "Unknown Brand",
        category=product.category or "clothing",
        price_inr=product.price_inr or 0,
        body_type=user.body_type or "standard",
        style_preferences=style_preferences,
        wardrobe_items=wardrobe_context,
    )

    # 7. Build response
    generated_at = datetime.now(timezone.utc).isoformat()
    response = {
        "product_id": str(product.id),
        "product_name": product.name,
        "explanation": explanation,
        "cached": False,
        "generated_at": generated_at,
    }

    # 8. Cache the result
    cacheable = {**response, "cached": False}
    _cache_set(cache_key, json.dumps(cacheable), _REC_TTL_SECONDS)

    logger.info(
        "[explanation_service] recommendation explanation generated and cached "
        "product_id=%s user_id=%s", product_id, user_id
    )
    return response
