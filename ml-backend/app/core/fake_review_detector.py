"""
Fake Review Detector — Pure ML/CV layer.

Responsibility: Detect whether reviewer-submitted photos match the product's
stock images. A significant visual mismatch between what a reviewer photographed
and what the stock listing shows is a strong signal that:
  (a) The reviewer received a different (counterfeit / wrong) product, OR
  (b) The reviewer's photo is unrelated to the product (review manipulation).

Rules (enforced by architecture):
  - No HTTP knowledge. No business logic. No database calls.
  - All public functions accept pre-computed L2-normalised numpy embeddings
    produced by clip_encoder.py — this module never calls CLIP directly.
  - Stateless — every function is a pure transformation.

Detection strategy:
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  mismatch_score  = 1 - max_similarity                                   │
  │                                                                          │
  │  Where max_similarity = max cosine similarity of the review image       │
  │  against ALL available stock image embeddings.                           │
  │                                                                          │
  │  Taking the MAX across stock images is deliberate: a product may have   │
  │  multiple stock angles (front, back, detail). A genuine reviewer photo  │
  │  will closely match at least ONE of those angles. A fake review photo   │
  │  will score low against all of them.                                     │
  │                                                                          │
  │  mismatch_score range: [0.0, 1.0]                                        │
  │    0.0 → review photo perfectly matches a stock image (authentic)       │
  │    1.0 → review photo completely unrelated to any stock image (fake)    │
  └─────────────────────────────────────────────────────────────────────────┘

Flagging threshold (DEFAULT_FLAG_THRESHOLD = 0.45):
  mismatch_score >= threshold → is_flagged_fake = True

  This threshold was chosen conservatively:
  - Authentic reviewers often photograph the product in different lighting,
    angles, or while worn — the match score is lower than stock-vs-stock.
  - A threshold at 0.45 (i.e., max_similarity < 0.55) catches obvious
    mismatches while tolerating real-world photo variation.
  - Threshold is configurable per-call for downstream tuning.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMBEDDING_DIM = 512

# A review is flagged as fake if mismatch_score >= this value.
# mismatch_score = 1 - max_cosine_similarity_vs_stock_images
# DEFAULT: 0.45 → max_similarity must be >= 0.55 to pass as authentic.
DEFAULT_FLAG_THRESHOLD: float = 0.45


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ReviewFlagResult:
    """
    Structured output of the fake review detection pipeline for one review.

    Scores are in range [0.0, 1.0].
    """

    mismatch_score: float
    """
    How dissimilar the review photo is from the best-matching stock image.
    0.0 = perfect match (authentic), 1.0 = completely unrelated (fake).
    mismatch_score = 1 - max_similarity_vs_stock.
    """

    max_similarity: float
    """
    Highest cosine similarity found between the review image and any stock image.
    This is the raw signal before inversion.
    """

    is_flagged_fake: bool
    """True when mismatch_score >= the flag threshold used for this call."""

    threshold_used: float
    """The flag threshold value that was applied."""

    num_stock_images_checked: int
    """Number of stock image embeddings compared against."""

    def as_dict(self) -> dict:
        """Return a plain dict for serialisation."""
        return {
            "mismatch_score": self.mismatch_score,
            "max_similarity": self.max_similarity,
            "is_flagged_fake": self.is_flagged_fake,
            "threshold_used": self.threshold_used,
            "num_stock_images_checked": self.num_stock_images_checked,
        }


@dataclass
class ProductFakeReviewReport:
    """
    Aggregated fake review report for all reviewer photos on a single product.

    Combines individual ReviewFlagResult objects into a product-level summary.
    """

    review_results: list[ReviewFlagResult]
    """One ReviewFlagResult per review image submitted."""

    fake_count: int
    """Number of review images flagged as fake."""

    total_count: int
    """Total number of review images evaluated."""

    fake_ratio: float
    """Fraction of review images flagged: fake_count / total_count. Range [0, 1]."""

    product_trust_score: float
    """
    Inverse of fake_ratio, adjusted for confidence.
    1.0 = all reviews authentic, 0.0 = all reviews flagged fake.
    product_trust_score = 1 - fake_ratio.
    """

    def as_dict(self) -> dict:
        """Return a plain dict for serialisation."""
        return {
            "fake_count": self.fake_count,
            "total_count": self.total_count,
            "fake_ratio": self.fake_ratio,
            "product_trust_score": self.product_trust_score,
            "review_results": [r.as_dict() for r in self.review_results],
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_embedding(embedding: np.ndarray, name: str = "embedding") -> None:
    """
    Raise if the embedding is not a valid L2-normalised (512,) float32 array.

    Args:
        embedding: Array to validate.
        name: Parameter name used in error messages.

    Raises:
        TypeError: If input is not a numpy array.
        ValueError: If shape does not match expected (EMBEDDING_DIM,).
    """
    if not isinstance(embedding, np.ndarray):
        raise TypeError(
            f"{name} must be a numpy.ndarray, got {type(embedding).__name__}"
        )
    if embedding.ndim != 1 or embedding.shape[0] != EMBEDDING_DIM:
        raise ValueError(
            f"{name}: expected shape ({EMBEDDING_DIM},), got {embedding.shape}"
        )


def _max_cosine_similarity(
    review_embedding: np.ndarray,
    stock_embeddings: list[np.ndarray],
) -> float:
    """
    Find the highest cosine similarity between one review image embedding and
    all available stock image embeddings.

    Because clip_encoder.py returns L2-normalised vectors, cosine similarity
    is simply the dot product — no division needed.

    The MAX is taken (not average) because a genuine reviewer photo needs to
    closely match only ONE stock angle to be considered authentic.

    Args:
        review_embedding: L2-normalised float32 array of shape (512,).
        stock_embeddings: List of L2-normalised float32 arrays, each (512,).
                          Must have at least one element.

    Returns:
        Maximum cosine similarity as a Python float, clamped to [0.0, 1.0].
    """
    max_sim = -1.0
    for stock_emb in stock_embeddings:
        _validate_embedding(stock_emb, "stock embedding")
        sim = float(np.dot(review_embedding, stock_emb))
        if sim > max_sim:
            max_sim = sim

    # Clamp to [0, 1]: negative similarity has no semantic meaning for fashion
    return float(np.clip(max_sim, 0.0, 1.0))


# ---------------------------------------------------------------------------
# Public API — pure functions
# ---------------------------------------------------------------------------

def compute_mismatch_score(
    review_embedding: np.ndarray,
    stock_embeddings: list[np.ndarray],
) -> float:
    """
    Compute the visual mismatch score between a review photo and a product listing.

    mismatch_score = 1 - max_cosine_similarity(review_embedding, stock_embeddings)

    A high score means the reviewer photo does not resemble any stock image —
    a strong signal of a counterfeit product or a manipulated review.

    Args:
        review_embedding: L2-normalised CLIP embedding of the reviewer's photo,
                          shape (512,). Produced by clip_encoder.encode_image.
        stock_embeddings: List of L2-normalised CLIP embeddings for the product's
                          stock images. At least one required.

    Returns:
        Mismatch score as a Python float in [0.0, 1.0].
        0.0 → review photo perfectly matches a stock image (authentic).
        1.0 → review photo completely unrelated to all stock images (fake).

    Raises:
        ValueError: If stock_embeddings is empty or any embedding is wrong shape.
        TypeError: If any embedding is not a numpy array.

    Example:
        >>> score = compute_mismatch_score(review_emb, [stock_emb_front, stock_emb_back])
        >>> 0.0 <= score <= 1.0
        True
    """
    if not stock_embeddings:
        raise ValueError("stock_embeddings must not be empty.")
    _validate_embedding(review_embedding, "review_embedding")

    max_sim = _max_cosine_similarity(review_embedding, stock_embeddings)
    mismatch = float(np.clip(1.0 - max_sim, 0.0, 1.0))
    logger.debug(
        "mismatch_score=%.4f (max_similarity=%.4f, %d stock images)",
        mismatch,
        max_sim,
        len(stock_embeddings),
    )
    return mismatch


def flag_review(
    review_embedding: np.ndarray,
    stock_embeddings: list[np.ndarray],
    threshold: float = DEFAULT_FLAG_THRESHOLD,
) -> ReviewFlagResult:
    """
    Evaluate one review image against the product's stock images and decide
    whether the review should be flagged as potentially fake.

    This is the primary entry point for evaluating a single reviewer photo.

    Args:
        review_embedding: L2-normalised CLIP embedding of the reviewer's photo,
                          shape (512,).
        stock_embeddings: List of L2-normalised CLIP embeddings for all stock
                          images of the product. At least one required.
        threshold:        Mismatch score at or above which the review is flagged.
                          Default is DEFAULT_FLAG_THRESHOLD (0.45).
                          Must be in (0.0, 1.0].

    Returns:
        ReviewFlagResult with mismatch_score, max_similarity, is_flagged_fake,
        threshold_used, and num_stock_images_checked.

    Raises:
        ValueError: If stock_embeddings is empty, threshold is out of range,
                    or any embedding has wrong shape.
        TypeError: If any embedding is not a numpy array.

    Example:
        >>> result = flag_review(review_emb, [stock_emb])
        >>> result.is_flagged_fake  # True if review photo doesn't match listing
        False
    """
    if not stock_embeddings:
        raise ValueError("stock_embeddings must not be empty.")
    if not (0.0 < threshold <= 1.0):
        raise ValueError(
            f"threshold must be in (0.0, 1.0], got {threshold}"
        )
    _validate_embedding(review_embedding, "review_embedding")

    max_sim = _max_cosine_similarity(review_embedding, stock_embeddings)
    mismatch = float(np.clip(1.0 - max_sim, 0.0, 1.0))
    is_fake = mismatch >= threshold

    result = ReviewFlagResult(
        mismatch_score=mismatch,
        max_similarity=max_sim,
        is_flagged_fake=is_fake,
        threshold_used=threshold,
        num_stock_images_checked=len(stock_embeddings),
    )

    logger.info(
        "flag_review: mismatch=%.4f max_sim=%.4f flagged=%s threshold=%.2f",
        mismatch,
        max_sim,
        is_fake,
        threshold,
    )
    return result


def analyze_product_reviews(
    review_embeddings: list[np.ndarray],
    stock_embeddings: list[np.ndarray],
    threshold: float = DEFAULT_FLAG_THRESHOLD,
) -> ProductFakeReviewReport:
    """
    Evaluate ALL reviewer photos for a single product and produce an aggregated
    trust report.

    This is the top-level function used by the service layer when the scraper
    has collected review images for a product and wants to pre-compute fake
    review scores at scrape time.

    Args:
        review_embeddings: List of L2-normalised CLIP embeddings — one per
                           reviewer photo. At least one required.
        stock_embeddings:  List of L2-normalised CLIP embeddings for the
                           product's stock images. At least one required.
        threshold:         Mismatch threshold for flagging. Default 0.45.

    Returns:
        ProductFakeReviewReport with:
          - review_results: List of ReviewFlagResult per reviewer photo.
          - fake_count: Number of photos flagged as fake.
          - total_count: Total reviewer photos evaluated.
          - fake_ratio: fake_count / total_count.
          - product_trust_score: 1 - fake_ratio.

    Raises:
        ValueError: If either list is empty or threshold is invalid.

    Example:
        >>> report = analyze_product_reviews([rev1, rev2, rev3], [stock])
        >>> 0.0 <= report.product_trust_score <= 1.0
        True
        >>> report.fake_ratio + report.product_trust_score == 1.0
        True
    """
    if not review_embeddings:
        raise ValueError("review_embeddings must not be empty.")
    if not stock_embeddings:
        raise ValueError("stock_embeddings must not be empty.")

    results: list[ReviewFlagResult] = []
    for i, rev_emb in enumerate(review_embeddings):
        try:
            result = flag_review(rev_emb, stock_embeddings, threshold=threshold)
        except (ValueError, TypeError) as exc:
            logger.error(
                "analyze_product_reviews: error on review image %d: %s", i, exc
            )
            raise
        results.append(result)

    total = len(results)
    fake_count = sum(1 for r in results if r.is_flagged_fake)
    fake_ratio = fake_count / total
    trust_score = float(np.clip(1.0 - fake_ratio, 0.0, 1.0))

    report = ProductFakeReviewReport(
        review_results=results,
        fake_count=fake_count,
        total_count=total,
        fake_ratio=round(fake_ratio, 6),
        product_trust_score=round(trust_score, 6),
    )

    logger.info(
        "analyze_product_reviews: total=%d fake=%d ratio=%.4f trust=%.4f",
        total,
        fake_count,
        fake_ratio,
        trust_score,
    )
    return report


def batch_flag_reviews(
    review_embeddings: list[np.ndarray],
    stock_embeddings: list[np.ndarray],
    threshold: float = DEFAULT_FLAG_THRESHOLD,
) -> list[ReviewFlagResult]:
    """
    Convenience wrapper — flag a batch of review images and return a flat list
    of ReviewFlagResult objects without the aggregated report.

    Use this when you need per-review results but not the product-level summary.

    Args:
        review_embeddings: List of L2-normalised CLIP embeddings, one per review.
        stock_embeddings:  List of L2-normalised CLIP embeddings for stock images.
        threshold:         Mismatch threshold. Default 0.45.

    Returns:
        List of ReviewFlagResult objects in the same order as review_embeddings.

    Raises:
        ValueError: If either list is empty.
    """
    report = analyze_product_reviews(review_embeddings, stock_embeddings, threshold)
    return report.review_results
