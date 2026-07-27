"""
Confidence Scorer — Pure ML/CV layer.

Responsibility: Compute a structured confidence score that quantifies how
closely a user-uploaded real product photo matches a stock image from a
platform listing.

Rules (enforced by architecture):
  - No HTTP knowledge. No business logic. No database calls.
  - All public functions accept pre-computed L2-normalised numpy embeddings
    (produced by clip_encoder.py) and return plain Python floats or dataclasses.
  - This module is stateless — every function is a pure transformation.

Score breakdown:
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  stock_match_score    → cosine similarity between uploaded image        │
  │                         embedding and stock image embedding             │
  │                         Range: [0.0, 1.0]                               │
  │                                                                          │
  │  authenticity_score   → weighted aggregate of multiple stock image      │
  │                         embeddings (handles multi-angle listings)       │
  │                         Range: [0.0, 1.0]                               │
  │                                                                          │
  │  overall_confidence   → final blended score with configurable weights   │
  │                         Range: [0.0, 1.0]                               │
  └─────────────────────────────────────────────────────────────────────────┘

Thresholds (used for label generation only — callers decide what to do):
  ≥ 0.85  → High confidence (product matches listing)
  0.60–0.84 → Moderate confidence (minor differences)
  < 0.60  → Low confidence (likely mismatch or fake listing)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMBEDDING_DIM = 512

# Confidence thresholds for label assignment
THRESHOLD_HIGH: float = 0.85
THRESHOLD_MODERATE: float = 0.60

# Default weight split for overall_confidence blending
# stock_match is weighted higher because it's the primary signal
DEFAULT_STOCK_MATCH_WEIGHT: float = 0.7
DEFAULT_AUTHENTICITY_WEIGHT: float = 0.3


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ConfidenceResult:
    """
    Structured output of the confidence scoring pipeline.

    All scores are in range [0.0, 1.0] where 1.0 = perfect match.
    """
    stock_match_score: float
    """Cosine similarity between the uploaded image and the primary stock image."""

    authenticity_score: float
    """Weighted aggregate score across all available stock image embeddings."""

    overall_confidence: float
    """Final blended score combining stock_match and authenticity signals."""

    label: str
    """Human-readable verdict: 'high' | 'moderate' | 'low'."""

    num_stock_images_used: int
    """Number of stock image embeddings that contributed to authenticity_score."""

    def as_dict(self) -> dict:
        """Return a plain dict representation for serialisation."""
        return {
            "stock_match_score": self.stock_match_score,
            "authenticity_score": self.authenticity_score,
            "overall_confidence": self.overall_confidence,
            "label": self.label,
            "num_stock_images_used": self.num_stock_images_used,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cosine_similarity_from_embeddings(
    vec_a: np.ndarray,
    vec_b: np.ndarray,
) -> float:
    """
    Compute cosine similarity between two L2-normalised embedding vectors.

    Because clip_encoder.py always returns L2-normalised vectors, this reduces
    to a dot product — O(d) with no division needed.

    Args:
        vec_a: L2-normalised float32 array of shape (512,).
        vec_b: L2-normalised float32 array of shape (512,).

    Returns:
        Cosine similarity as a Python float, clamped to [0.0, 1.0].
        The lower clamp at 0.0 is intentional: negative similarity between
        fashion images is meaningless noise, not a signal, so we treat it as 0.

    Raises:
        ValueError: If shapes do not match or are not 1-D with 512 elements.
    """
    _validate_embedding(vec_a, "vec_a")
    _validate_embedding(vec_b, "vec_b")

    if vec_a.shape != vec_b.shape:
        raise ValueError(
            f"Shape mismatch: vec_a={vec_a.shape}, vec_b={vec_b.shape}"
        )

    raw = float(np.dot(vec_a, vec_b))
    # Clamp: upper bound handles floating-point rounding past 1.0;
    # lower bound at 0.0 because negative cosine similarity has no fashion meaning.
    return float(np.clip(raw, 0.0, 1.0))


def _validate_embedding(embedding: np.ndarray, name: str = "embedding") -> None:
    """
    Raise ValueError if the embedding is not a valid (512,) float32 array.

    Args:
        embedding: Array to validate.
        name: Parameter name for error messages.

    Raises:
        ValueError: If shape is wrong.
        TypeError: If input is not a numpy array.
    """
    if not isinstance(embedding, np.ndarray):
        raise TypeError(
            f"{name} must be a numpy.ndarray, got {type(embedding).__name__}"
        )
    if embedding.ndim != 1 or embedding.shape[0] != EMBEDDING_DIM:
        raise ValueError(
            f"{name}: expected shape ({EMBEDDING_DIM},), got {embedding.shape}"
        )


def _assign_label(score: float) -> str:
    """
    Map a numeric confidence score to a human-readable label.

    Args:
        score: A float in [0.0, 1.0].

    Returns:
        'high' if score >= THRESHOLD_HIGH,
        'moderate' if score >= THRESHOLD_MODERATE,
        'low' otherwise.
    """
    if score >= THRESHOLD_HIGH:
        return "high"
    if score >= THRESHOLD_MODERATE:
        return "moderate"
    return "low"


# ---------------------------------------------------------------------------
# Public API — pure functions
# ---------------------------------------------------------------------------

def compute_stock_match_score(
    uploaded_embedding: np.ndarray,
    stock_embedding: np.ndarray,
) -> float:
    """
    Compute cosine similarity between an uploaded product image and one
    stock image embedding.

    This is the primary signal: how closely does the real product the user
    received match the hero/primary stock image from the listing?

    Args:
        uploaded_embedding: L2-normalised CLIP embedding of the user's photo,
                            shape (512,), produced by clip_encoder.encode_image.
        stock_embedding:    L2-normalised CLIP embedding of the listing's
                            primary stock image, shape (512,).

    Returns:
        Cosine similarity as a Python float in [0.0, 1.0].
        1.0 → perfect visual match.
        0.0 → completely unrelated images.

    Raises:
        ValueError: If either embedding is the wrong shape.
        TypeError: If either argument is not a numpy array.

    Example:
        >>> score = compute_stock_match_score(uploaded_emb, stock_emb)
        >>> 0.0 <= score <= 1.0
        True
    """
    score = _cosine_similarity_from_embeddings(uploaded_embedding, stock_embedding)
    logger.debug("stock_match_score=%.4f", score)
    return score


def compute_authenticity_score(
    uploaded_embedding: np.ndarray,
    stock_embeddings: list[np.ndarray],
    weights: Optional[list[float]] = None,
) -> float:
    """
    Compute a weighted aggregate similarity score between the uploaded photo
    and ALL available stock image embeddings for the listing.

    Many listings have multiple stock images (front, back, detail shots). A
    product is more likely authentic if it matches well across multiple angles,
    not just the hero shot.

    Aggregation strategy: weighted average of cosine similarities.
    Default weights: uniform (all stock images treated equally).
    Custom weights: pass a list of floats in the same order as stock_embeddings
    (e.g., weight the hero shot higher: [0.5, 0.3, 0.2]).

    Args:
        uploaded_embedding: L2-normalised CLIP embedding of the user's photo,
                            shape (512,).
        stock_embeddings:   List of L2-normalised CLIP embeddings for all
                            stock images of the listing. At least one required.
        weights:            Optional list of floats, same length as stock_embeddings.
                            Values need not sum to 1.0 — they are normalised
                            internally. Pass None for uniform weights.

    Returns:
        Weighted average cosine similarity as a Python float in [0.0, 1.0].

    Raises:
        ValueError: If stock_embeddings is empty.
        ValueError: If weights length does not match stock_embeddings length.
        ValueError: If any weight is negative.

    Example:
        >>> score = compute_authenticity_score(uploaded_emb, [stock_a, stock_b])
        >>> 0.0 <= score <= 1.0
        True
    """
    if not stock_embeddings:
        raise ValueError("stock_embeddings must not be empty.")

    n = len(stock_embeddings)

    # Validate and normalise weights
    if weights is None:
        normalised_weights = [1.0 / n] * n
    else:
        if len(weights) != n:
            raise ValueError(
                f"weights length ({len(weights)}) must match "
                f"stock_embeddings length ({n})."
            )
        if any(w < 0 for w in weights):
            raise ValueError("All weights must be non-negative.")
        total = sum(weights)
        if total == 0.0:
            raise ValueError("Weights must not all be zero.")
        normalised_weights = [w / total for w in weights]

    # Compute per-stock-image similarities and aggregate
    weighted_sum = 0.0
    for stock_emb, w in zip(stock_embeddings, normalised_weights):
        sim = _cosine_similarity_from_embeddings(uploaded_embedding, stock_emb)
        weighted_sum += sim * w

    score = float(np.clip(weighted_sum, 0.0, 1.0))
    logger.debug(
        "authenticity_score=%.4f from %d stock image(s)", score, n
    )
    return score


def compute_confidence_score(
    uploaded_embedding: np.ndarray,
    stock_embeddings: list[np.ndarray],
    stock_match_weight: float = DEFAULT_STOCK_MATCH_WEIGHT,
    authenticity_weight: float = DEFAULT_AUTHENTICITY_WEIGHT,
    authenticity_weights: Optional[list[float]] = None,
) -> ConfidenceResult:
    """
    Compute the full structured confidence score for a single CV scan request.

    This is the top-level function that orchestrates the entire scoring
    pipeline. It calls compute_stock_match_score (primary stock image only)
    and compute_authenticity_score (all stock images), then blends them
    into an overall_confidence score.

    Args:
        uploaded_embedding:     L2-normalised CLIP embedding of the user's
                                uploaded photo, shape (512,).
        stock_embeddings:       List of L2-normalised CLIP embeddings for
                                the listing's stock images. The FIRST element
                                is treated as the primary (hero) image for
                                stock_match_score. All elements are used for
                                authenticity_score.
        stock_match_weight:     Weight for stock_match_score in the final
                                blend (default 0.7). Must be >= 0.
        authenticity_weight:    Weight for authenticity_score in the final
                                blend (default 0.3). Must be >= 0.
                                stock_match_weight + authenticity_weight
                                need not equal 1.0 — normalised internally.
        authenticity_weights:   Per-stock-image weights passed through to
                                compute_authenticity_score (see that function).
                                Pass None for uniform weights.

    Returns:
        ConfidenceResult dataclass with:
          - stock_match_score
          - authenticity_score
          - overall_confidence
          - label ('high' | 'moderate' | 'low')
          - num_stock_images_used

    Raises:
        ValueError: If stock_embeddings is empty or weights are invalid.

    Example:
        >>> result = compute_confidence_score(user_emb, [stock_emb])
        >>> 0.0 <= result.overall_confidence <= 1.0
        True
        >>> result.label in ('high', 'moderate', 'low')
        True
    """
    if not stock_embeddings:
        raise ValueError("stock_embeddings must not be empty.")
    if stock_match_weight < 0:
        raise ValueError("stock_match_weight must be non-negative.")
    if authenticity_weight < 0:
        raise ValueError("authenticity_weight must be non-negative.")

    total_weight = stock_match_weight + authenticity_weight
    if total_weight == 0.0:
        raise ValueError(
            "stock_match_weight and authenticity_weight must not both be zero."
        )

    # Primary signal: hero stock image vs uploaded photo
    stock_match = compute_stock_match_score(
        uploaded_embedding, stock_embeddings[0]
    )

    # Secondary signal: aggregate across all available stock images
    authenticity = compute_authenticity_score(
        uploaded_embedding, stock_embeddings, weights=authenticity_weights
    )

    # Weighted blend → overall confidence
    overall = (
        stock_match * (stock_match_weight / total_weight)
        + authenticity * (authenticity_weight / total_weight)
    )
    overall = float(np.clip(overall, 0.0, 1.0))
    label = _assign_label(overall)

    result = ConfidenceResult(
        stock_match_score=stock_match,
        authenticity_score=authenticity,
        overall_confidence=overall,
        label=label,
        num_stock_images_used=len(stock_embeddings),
    )

    logger.info(
        "ConfidenceResult: stock_match=%.4f authenticity=%.4f "
        "overall=%.4f label=%s",
        result.stock_match_score,
        result.authenticity_score,
        result.overall_confidence,
        result.label,
    )
    return result


def score_batch(
    uploaded_embedding: np.ndarray,
    stock_embedding_sets: list[list[np.ndarray]],
) -> list[ConfidenceResult]:
    """
    Compute confidence scores for multiple products in a single call.

    Useful when the CV pipeline needs to compare one user photo against
    several candidate products simultaneously (e.g., similarity search results).

    Args:
        uploaded_embedding:    L2-normalised CLIP embedding of the user's
                               photo, shape (512,).
        stock_embedding_sets:  List of stock embedding lists — one per product.
                               Each inner list must have at least one embedding.

    Returns:
        List of ConfidenceResult objects in the same order as
        stock_embedding_sets.

    Raises:
        ValueError: If stock_embedding_sets is empty.
    """
    if not stock_embedding_sets:
        raise ValueError("stock_embedding_sets must not be empty.")

    results = []
    for i, stock_embeddings in enumerate(stock_embedding_sets):
        try:
            result = compute_confidence_score(uploaded_embedding, stock_embeddings)
        except (ValueError, TypeError) as exc:
            logger.error(
                "score_batch: error scoring product at index %d: %s", i, exc
            )
            raise
        results.append(result)

    logger.info(
        "score_batch: scored %d products for a single uploaded image",
        len(results),
    )
    return results
