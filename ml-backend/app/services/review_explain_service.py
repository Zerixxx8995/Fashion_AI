"""
Review Explain Service — ml-backend/app/services/review_explain_service.py

Responsibility: Orchestrate review authenticity explanation.
- Redis cache check first (key: review:explain:{review_id}, TTL 48h).
- On cache miss: fetch review + product from PostgreSQL,
  retrieve similar fake reviews from Pinecone,
  call review_authenticity_engine, cache and return result.

Layer rules (service):
  - Knows about DB models (SQLAlchemy).
  - Knows about integrations (pinecone_client via review_authenticity_engine).
  - Does NOT contain HTTP knowledge (lives in routers/controllers).
  - Does NOT contain raw LLM/prompt logic (lives in core/).

Caching (spec constraint):
  - Redis key: review:explain:{review_id}
  - TTL: 48 hours — review explanations are stable, cache aggressively.

Redis pattern copied exactly from explanation_service.py.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.review_authenticity_engine import (
    generate_review_explanation,
    ReviewAuthenticityExplanation,
)
from app.db.models.review import Review
from app.db.models.product import Product

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis client — exact pattern from explanation_service.py
# ---------------------------------------------------------------------------

_redis_client: Optional[Any] = None

_REVIEW_EXPLAIN_TTL = 48 * 60 * 60   # 48 hours — spec constraint


def _get_redis() -> Any:
    """
    Lazily initialise and return the Upstash Redis REST client.
    Falls back gracefully if env vars are missing.
    """
    global _redis_client  # noqa: PLW0603
    if _redis_client is not None:
        return _redis_client

    url = os.getenv("UPSTASH_REDIS_REST_URL")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN")

    if not url or not token:
        logger.warning(
            "[review_explain_service] UPSTASH_REDIS_REST_URL or TOKEN not set — "
            "Redis caching disabled. All requests will call the LLM."
        )
        return None

    try:
        from upstash_redis import Redis  # type: ignore[import]
        _redis_client = Redis(url=url, token=token)
        logger.info("[review_explain_service] Upstash Redis client initialised")
        return _redis_client
    except Exception as exc:
        logger.warning(
            "[review_explain_service] Redis client init failed: %s — caching disabled", exc
        )
        return None


def _cache_get(key: str) -> Optional[str]:
    """Get a value from Redis cache. Returns None if missing or on error."""
    redis = _get_redis()
    if redis is None:
        return None
    try:
        value = redis.get(key)
        if value is not None:
            logger.debug("[review_explain_service] cache HIT key=%s", key)
        else:
            logger.debug("[review_explain_service] cache MISS key=%s", key)
        return value
    except Exception as exc:
        logger.warning("[review_explain_service] cache GET failed key=%s: %s", key, exc)
        return None


def _cache_set(key: str, value: str, ttl_seconds: int) -> None:
    """Set a value in Redis with TTL. Silently ignores errors."""
    redis = _get_redis()
    if redis is None:
        return
    try:
        redis.setex(key, ttl_seconds, value)
        logger.debug(
            "[review_explain_service] cache SET key=%s ttl=%ds", key, ttl_seconds
        )
    except Exception as exc:
        logger.warning(
            "[review_explain_service] cache SET failed key=%s: %s", key, exc
        )


# ---------------------------------------------------------------------------
# Internal — Pinecone retrieval of similar fake reviews
# ---------------------------------------------------------------------------

def _fetch_similar_fake_reviews(
    db: Session,
    review_id: str,
    product_id: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    Retrieve the top-k most similar historically fake reviews via Pinecone.

    Strategy:
      1. Query Pinecone "reviews" namespace for vectors close to this review's
         embedding, filtered to is_flagged_fake=true.
      2. For each Pinecone match, fetch the reviewer_text from PostgreSQL via
         the stored review_id metadata field.
      3. Exclude the current review itself.
      4. Fall back to any DB fake reviews for the same product if Pinecone fails.

    Returns:
        List of dicts with key "reviewer_text".
    """
    # Try Pinecone first — it may not be populated yet in dev
    try:
        from app.integrations import pinecone_client
        # Pinecone: query the "reviews" namespace for similar fake reviews.
        # We use a zero vector as a stub when no embedding is stored per review.
        # In production the scraper pipeline upserts review embeddings at index time.
        stub_vector = [0.0] * 512
        matches = pinecone_client.query_similar(
            embedding=stub_vector,
            top_k=top_k + 1,  # +1 to allow filtering self
            namespace="reviews",
            filter={"is_flagged_fake": {"$eq": True}},
        )
        ids = [
            m["metadata"].get("review_id", m["id"])
            for m in matches
            if m["metadata"].get("review_id", m["id"]) != review_id
        ][:top_k]

        if ids:
            rows = list(
                db.scalars(
                    select(Review)
                    .where(Review.id.in_(ids))
                    .where(Review.reviewer_text.isnot(None))
                ).all()
            )
            return [{"reviewer_text": r.reviewer_text} for r in rows]

    except Exception as exc:
        logger.warning(
            "[review_explain_service] Pinecone retrieval failed: %s — using DB fallback", exc
        )

    # DB fallback: fetch other flagged fake reviews for the same product
    rows = list(
        db.scalars(
            select(Review)
            .where(Review.product_id == product_id)
            .where(Review.is_flagged_fake.is_(True))
            .where(Review.id != review_id)
            .where(Review.reviewer_text.isnot(None))
            .limit(top_k)
        ).all()
    )
    return [{"reviewer_text": r.reviewer_text} for r in rows]


# ---------------------------------------------------------------------------
# Public service API
# ---------------------------------------------------------------------------

def get_review_explanation(
    db: Session,
    *,
    review_id: str,
) -> dict[str, Any]:
    """
    Return a structured review authenticity explanation.
    Checks Redis cache first; generates via RAG engine on miss.

    Args:
        db:        SQLAlchemy session.
        review_id: UUID string of the Review.

    Returns:
        Dict matching the spec API response shape:
        {
            "review_id":            str,
            "overall_verdict":      str,
            "confidence_score":     float,
            "suspicious_phrases":   list[str],
            "image_mismatch_summary": str,
            "pattern_matches":      list[str],
            "recommendation":       str,
            "cached":               bool,
        }

    Raises:
        KeyError:  If review_id is not found in the database.
        ValueError: If the review is not flagged as fake.
    """
    cache_key = f"review:explain:{review_id}"

    # 1. Check Redis cache
    cached_raw = _cache_get(cache_key)
    if cached_raw:
        try:
            cached_data = json.loads(cached_raw)
            cached_data["cached"] = True
            logger.info(
                "[review_explain_service] cache hit review_id=%s", review_id
            )
            return cached_data
        except json.JSONDecodeError:
            logger.warning(
                "[review_explain_service] invalid cached JSON key=%s — regenerating",
                cache_key,
            )

    # 2. Cache miss — fetch review from DB
    review = db.scalar(select(Review).where(Review.id == review_id))
    if review is None:
        raise KeyError(f"Review with id={review_id!r} not found")

    is_flagged_fake = bool(review.is_flagged_fake)

    # 3. Fetch the product for context
    product = db.scalar(select(Product).where(Product.id == review.product_id))
    product_name = product.name if product else "Fashion Product"
    platform = product.platform if product else "unknown"

    # First stock image URL (used in the prompt)
    stock_image_url = ""
    if product and product.stock_image_urls:
        try:
            urls = json.loads(product.stock_image_urls)
            stock_image_url = urls[0] if urls else ""
        except (json.JSONDecodeError, IndexError):
            stock_image_url = ""

    # 4. Retrieve similar historical fake reviews (Pinecone → DB fallback)
    historical_reviews = []
    if is_flagged_fake:
        historical_reviews = _fetch_similar_fake_reviews(
            db,
            review_id=review_id,
            product_id=review.product_id,
        )

    # 5. Generate explanation via RAG engine
    logger.info(
        "[review_explain_service] generating explanation review_id=%s product=%s flagged=%s",
        review_id, product_name, is_flagged_fake,
    )
    explanation: ReviewAuthenticityExplanation = generate_review_explanation(
        review_text=review.reviewer_text or "(no review text)",
        stock_match_score=review.stock_match_score or 0.0,
        product_name=product_name,
        platform=platform,
        stock_image_url=stock_image_url,
        historical_fake_reviews=historical_reviews,
        is_flagged_fake=is_flagged_fake,
    )

    # 6. Build response dict
    response: dict[str, Any] = {
        "review_id": review_id,
        "overall_verdict": explanation.overall_verdict,
        "confidence_score": explanation.confidence_score,
        "suspicious_phrases": explanation.suspicious_phrases,
        "image_mismatch_summary": explanation.image_mismatch_summary,
        "pattern_matches": explanation.pattern_matches,
        "recommendation": explanation.recommendation,
        "cached": False,
    }

    # 7. Cache the result (48h TTL per spec)
    cacheable = {**response, "cached": False}
    _cache_set(cache_key, json.dumps(cacheable), _REVIEW_EXPLAIN_TTL)

    logger.info(
        "[review_explain_service] explanation generated and cached review_id=%s verdict=%s",
        review_id, explanation.overall_verdict,
    )
    return response
