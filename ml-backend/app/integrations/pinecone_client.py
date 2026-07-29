"""
Pinecone Integration Client — ml-backend.

Responsibility: All Pinecone vector database I/O is isolated here.
No business logic lives here — just the raw Pinecone API calls.

Architecture rules:
  Layer: Integrations
  One job: External API calls to Pinecone (upsert, query, delete, fetch)
  Never does: Business logic, HTTP routing, ML algorithms

Operations:
  upsert_embedding    — store a CLIP embedding in Pinecone with metadata
  query_similar       — find k nearest neighbours for a given vector
  delete_embedding    — remove a vector by ID
  fetch_embedding     — retrieve a vector by ID

Pinecone index schema (one index: "fashion-ai"):
  Namespace "products"  — stock image embeddings from scraper pipeline
  Namespace "wardrobe"  — user wardrobe item embeddings

Metadata stored per vector (used for filtering in queries):
  product_id    (str)
  platform      (str)   e.g. "myntra"
  price_inr     (int)
  category      (str)
  url           (str)

Environment variables required:
  PINECONE_API_KEY   — Pinecone API key
  PINECONE_INDEX     — index name (default: "fashion-ai")
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy client initialisation — avoids importing pinecone at module load time
# when not running in a worker that needs it.
# ---------------------------------------------------------------------------

_pinecone_index: Any = None


def _get_index() -> Any:
    """
    Return (and lazily initialise) the Pinecone index client.

    Uses Pinecone v3+ SDK: `from pinecone import Pinecone`.

    Raises:
        RuntimeError: If PINECONE_API_KEY or PINECONE_INDEX are not set.
    """
    global _pinecone_index  # noqa: PLW0603
    if _pinecone_index is not None:
        return _pinecone_index

    api_key = os.getenv("PINECONE_API_KEY")
    index_name = os.getenv("PINECONE_INDEX", "fashion-ai")

    if not api_key:
        raise RuntimeError(
            "PINECONE_API_KEY environment variable is not set. "
            "Add it to your .env file."
        )

    from pinecone import Pinecone  # type: ignore[import]

    pc = Pinecone(api_key=api_key)
    _pinecone_index = pc.Index(index_name)
    logger.info("[pinecone_client] connected to index '%s'", index_name)
    return _pinecone_index


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upsert_embedding(
    *,
    vector_id: str,
    embedding: list[float],
    metadata: dict[str, Any],
    namespace: str = "products",
) -> None:
    """
    Upsert a single CLIP embedding into Pinecone.

    Args:
        vector_id:  Unique ID for this vector (e.g. product_id or wardrobe_item_id).
        embedding:  List of floats — CLIP embedding (512 dimensions).
        metadata:   Dict of scalar metadata stored alongside the vector.
                    Must be JSON-serialisable (str, int, float, bool only).
        namespace:  Pinecone namespace ("products" or "wardrobe").
    """
    index = _get_index()
    index.upsert(
        vectors=[{"id": vector_id, "values": embedding, "metadata": metadata}],
        namespace=namespace,
    )
    logger.debug("[pinecone_client] upserted vector_id=%s ns=%s", vector_id, namespace)


def query_similar(
    *,
    embedding: list[float],
    top_k: int = 10,
    namespace: str = "products",
    filter: Optional[dict[str, Any]] = None,
    include_metadata: bool = True,
) -> list[dict[str, Any]]:
    """
    Query Pinecone for the top-k nearest neighbours.

    Args:
        embedding:        Query CLIP embedding (512 floats).
        top_k:            Number of results to return (max 50).
        namespace:        Pinecone namespace to search.
        filter:           Optional metadata filter dict (Pinecone filter syntax).
        include_metadata: Whether to return metadata with each match.

    Returns:
        List of match dicts:
        [
            {
                "id": str,
                "score": float,       # cosine similarity 0–1
                "metadata": {
                    "product_id": str,
                    "platform": str,
                    "price_inr": int,
                    "category": str,
                    "url": str,
                }
            },
            ...
        ]
    """
    index = _get_index()
    response = index.query(
        vector=embedding,
        top_k=top_k,
        namespace=namespace,
        filter=filter,
        include_metadata=include_metadata,
        include_values=False,
    )
    matches = [
        {
            "id": m["id"],
            "score": m["score"],
            "metadata": m.get("metadata", {}),
        }
        for m in response.get("matches", [])
    ]
    logger.debug(
        "[pinecone_client] query returned %d matches ns=%s", len(matches), namespace
    )
    return matches


def delete_embedding(*, vector_id: str, namespace: str = "products") -> None:
    """
    Delete a vector from Pinecone by ID.

    Args:
        vector_id:  ID of the vector to delete.
        namespace:  Pinecone namespace.
    """
    index = _get_index()
    index.delete(ids=[vector_id], namespace=namespace)
    logger.debug("[pinecone_client] deleted vector_id=%s ns=%s", vector_id, namespace)


def fetch_embedding(
    *, vector_id: str, namespace: str = "products"
) -> Optional[dict[str, Any]]:
    """
    Fetch a single vector from Pinecone by ID.

    Returns:
        Dict with "id", "values" (embedding), and "metadata", or None if not found.
    """
    index = _get_index()
    response = index.fetch(ids=[vector_id], namespace=namespace)
    vectors = response.get("vectors", {})
    if vector_id not in vectors:
        return None
    v = vectors[vector_id]
    return {
        "id": v["id"],
        "values": v.get("values", []),
        "metadata": v.get("metadata", {}),
    }
