"""
Similarity Service — ml-backend.

Responsibility: Business logic for visual similarity search ("find similar
but cheaper") and style recommendation.

Layer rules:
  - Calls pinecone_client for vector search
  - Calls clip_encoder (via lazy import) to convert query image/text to embedding
  - Does NOT contain HTTP knowledge (no FastAPI, no Request objects)
  - Does NOT contain Pinecone SDK calls (all isolated in pinecone_client)

Public API:
  find_similar_products(...)   — CLIP query → Pinecone search → ranked + filtered results
  rank_by_price(results)       — sort by price ascending (cheaper first)
  find_cheaper_alternatives()  — find visually similar products strictly cheaper than reference
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Optional

# Module-level import so tests can patch app.services.similarity_service.pinecone_client
from app.integrations import pinecone_client  # noqa: E402

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TOP_K = 10
MAX_TOP_K = 50


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _encode_query(
    *,
    image_url: Optional[str],
    text_query: Optional[str],
) -> list[float]:
    """
    Generate a CLIP embedding from an image URL or text query.

    Priority: image_url is used if provided; text_query is the fallback.

    Deferred import keeps CLIP model out of the FastAPI process — only
    the Celery worker loads it.

    Args:
        image_url:   HTTP/HTTPS URL of the query image, or None.
        text_query:  Natural language search query, or None.

    Returns:
        List of 512 floats (normalised CLIP embedding).

    Raises:
        ValueError: If neither image_url nor text_query is provided.
    """
    if not image_url and not text_query:
        raise ValueError("Either image_url or text_query must be provided.")

    # Deferred import — CLIP model loaded lazily via lru_cache
    from app.core.clip_encoder import encode_image, encode_text  # type: ignore[import]

    if image_url:
        embedding = encode_image(image_url)
    else:
        embedding = encode_text(text_query)  # type: ignore[arg-type]

    return embedding.tolist()


def _extract_price(metadata: dict[str, Any]) -> int:
    """
    Safely extract price_inr from Pinecone metadata.

    Returns sys.maxsize if missing so unpriced items sort last.
    """
    return int(metadata.get("price_inr", sys.maxsize))


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

def find_similar_products(
    *,
    image_url: Optional[str] = None,
    text_query: Optional[str] = None,
    limit: int = DEFAULT_TOP_K,
    max_price_inr: Optional[int] = None,
    category: Optional[str] = None,
    exclude_platform: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Find visually similar products via CLIP embedding → Pinecone query.

    Accepts either an image URL or a text query (image takes precedence).
    Optionally filters by price ceiling, category, or platform exclusion.
    Results are returned ranked by similarity score (highest first).

    Args:
        image_url:        URL of the query image (takes precedence over text).
        text_query:       Natural language product description.
        limit:            Number of results to return (1–50).
        max_price_inr:    Optional upper price limit (inclusive).
        category:         Optional category filter ("tops", "jeans", etc.)
        exclude_platform: Optional platform to exclude from results.

    Returns:
        List of product dicts ranked by similarity_score descending.
    """
    top_k = min(limit, MAX_TOP_K)

    logger.info(
        "[similarity_service] find_similar image=%s text=%s limit=%d",
        image_url, text_query, limit,
    )

    # 1. Generate query embedding
    embedding = _encode_query(image_url=image_url, text_query=text_query)

    # 2. Build Pinecone metadata filter
    pinecone_filter: dict[str, Any] = {}
    if category:
        pinecone_filter["category"] = {"$eq": category}

    # 3. Query Pinecone — over-fetch to allow for post-filter headroom
    matches = pinecone_client.query_similar(
        embedding=embedding,
        top_k=top_k * 3,
        namespace="products",
        filter=pinecone_filter if pinecone_filter else None,
    )

    # 4. Post-filter and shape results
    results: list[dict[str, Any]] = []
    for match in matches:
        meta = match.get("metadata", {})
        price = _extract_price(meta)

        # Skip if over price ceiling
        if max_price_inr is not None and price > max_price_inr:
            continue

        # Skip excluded platform
        if exclude_platform and meta.get("platform") == exclude_platform:
            continue

        results.append({
            "product_id": meta.get("product_id", match["id"]),
            "platform": meta.get("platform", "unknown"),
            "price_inr": price,
            "category": meta.get("category", ""),
            "url": meta.get("url", ""),
            "similarity_score": round(match["score"], 4),
        })

        if len(results) >= limit:
            break

    logger.info(
        "[similarity_service] returning %d results after filtering", len(results)
    )

    # 5. Rank by similarity (Pinecone already returns by score, but reaffirm)
    results.sort(key=lambda r: r["similarity_score"], reverse=True)

    # Add rank field
    for i, result in enumerate(results, start=1):
        result["rank"] = i

    return results


def rank_by_price(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Re-rank a list of similar product results by price ascending (cheapest first).

    Args:
        results: Output from find_similar_products (list of product dicts).

    Returns:
        New list sorted by price_inr ascending, with rank field updated.
    """
    sorted_results = sorted(results, key=lambda r: r.get("price_inr", 0))
    for i, result in enumerate(sorted_results, start=1):
        result["rank"] = i
    return sorted_results


def find_cheaper_alternatives(
    *,
    image_url: Optional[str] = None,
    text_query: Optional[str] = None,
    reference_price_inr: int,
    limit: int = DEFAULT_TOP_K,
    category: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Find visually similar products strictly cheaper than a reference price.

    This is the core "find similar but cheaper" feature from the MVP spec.

    Args:
        image_url:           Query image URL (takes precedence over text).
        text_query:          Natural language query.
        reference_price_inr: Price of the product being compared against.
        limit:               Number of results.
        category:            Optional category restriction.

    Returns:
        List of cheaper alternatives sorted by price ascending (cheapest first).
    """
    similar = find_similar_products(
        image_url=image_url,
        text_query=text_query,
        limit=limit * 2,    # over-fetch for price filter headroom
        max_price_inr=reference_price_inr - 1,  # strictly cheaper
        category=category,
    )
    cheaper = rank_by_price(similar)
    return cheaper[:limit]
