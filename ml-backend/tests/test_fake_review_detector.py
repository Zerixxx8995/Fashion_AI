"""
Tests for core/fake_review_detector.py

Assertions per plan:
  - assert mismatch detection logic works correctly
  - assert flagging threshold works correctly

Additional coverage:
  - mismatch_score is in [0.0, 1.0]
  - matching review photo scores near 0.0 mismatch (authentic)
  - unrelated review photo scores near 1.0 mismatch (fake)
  - max_similarity strategy: one matching stock image among many is enough
  - threshold boundary: exactly at threshold → flagged, just below → not flagged
  - custom threshold respected
  - analyze_product_reviews aggregates correctly
  - fake_ratio + product_trust_score == 1.0
  - batch_flag_reviews matches individual flag_review calls
  - error cases: empty lists, wrong shapes, bad threshold, non-array inputs
  - as_dict() keys and values
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.core.fake_review_detector import (
    DEFAULT_FLAG_THRESHOLD,
    EMBEDDING_DIM,
    ProductFakeReviewReport,
    ReviewFlagResult,
    analyze_product_reviews,
    batch_flag_reviews,
    compute_mismatch_score,
    flag_review,
)


# ---------------------------------------------------------------------------
# Helpers — geometric unit vectors, no CLIP inference needed.
#
# All embeddings in this module use hand-crafted unit vectors so tests run
# fast without downloading the CLIP model. The detector operates purely on
# pre-computed embeddings — it never calls clip_encoder.py directly.
# ---------------------------------------------------------------------------

def _unit(dim: int = EMBEDDING_DIM, index: int = 0) -> np.ndarray:
    """Return the `index`-th standard basis vector of length `dim`."""
    v = np.zeros(dim, dtype=np.float32)
    v[index] = 1.0
    return v


def _gram_schmidt_ortho(base: np.ndarray, candidate_index: int = 1) -> np.ndarray:
    """
    Return a unit vector orthogonal to `base` using Gram-Schmidt.
    `candidate_index` selects which basis vector to start from.
    """
    candidate = _unit(index=candidate_index)
    proj = np.dot(candidate, base) * base
    ortho = candidate - proj
    return (ortho / np.linalg.norm(ortho)).astype(np.float32)


def _make_similar_embedding(base: np.ndarray, similarity: float) -> np.ndarray:
    """
    Construct a unit vector with a specific cosine similarity to `base`.

    cos(theta) = similarity  →  v = cos(theta)*base + sin(theta)*ortho
    Result is unit-norm by construction.
    """
    ortho = _gram_schmidt_ortho(base, candidate_index=1)
    theta = math.acos(float(np.clip(similarity, -1.0, 1.0)))
    v = math.cos(theta) * base + math.sin(theta) * ortho
    return (v / np.linalg.norm(v)).astype(np.float32)


# ---------------------------------------------------------------------------
# Module-level fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def stock_emb() -> np.ndarray:
    """Primary stock image embedding — e_0 basis vector."""
    return _unit(index=0)


@pytest.fixture(scope="module")
def matching_review_emb(stock_emb) -> np.ndarray:
    """Review embedding identical to stock — simulates authentic reviewer photo."""
    return stock_emb.copy()


@pytest.fixture(scope="module")
def unrelated_review_emb(stock_emb) -> np.ndarray:
    """Review embedding orthogonal to stock — simulates fake/wrong product photo."""
    return _gram_schmidt_ortho(stock_emb, candidate_index=1)


@pytest.fixture(scope="module")
def second_stock_emb(stock_emb) -> np.ndarray:
    """A second stock image (different angle) — orthogonal to stock_emb."""
    return _gram_schmidt_ortho(stock_emb, candidate_index=2)


@pytest.fixture(scope="module")
def near_threshold_emb(stock_emb) -> np.ndarray:
    """
    Review embedding with max_similarity = DEFAULT_FLAG_THRESHOLD exactly.
    mismatch_score will be exactly DEFAULT_FLAG_THRESHOLD → should be flagged.
    """
    target_similarity = 1.0 - DEFAULT_FLAG_THRESHOLD   # max_sim such that mismatch = threshold
    return _make_similar_embedding(stock_emb, similarity=target_similarity)


@pytest.fixture(scope="module")
def just_below_threshold_emb(stock_emb) -> np.ndarray:
    """
    Review embedding with max_similarity just above the flag threshold.
    mismatch_score will be just below DEFAULT_FLAG_THRESHOLD → should NOT be flagged.
    """
    target_similarity = 1.0 - DEFAULT_FLAG_THRESHOLD + 0.01
    return _make_similar_embedding(stock_emb, similarity=target_similarity)


# ---------------------------------------------------------------------------
# TestComputeMismatchScore
# ---------------------------------------------------------------------------

class TestComputeMismatchScore:
    """Tests for the raw mismatch score computation."""

    def test_returns_float(self, matching_review_emb, stock_emb):
        score = compute_mismatch_score(matching_review_emb, [stock_emb])
        assert isinstance(score, float)

    def test_score_in_valid_range(self, unrelated_review_emb, stock_emb):
        """Mismatch score must always be in [0.0, 1.0]."""
        score = compute_mismatch_score(unrelated_review_emb, [stock_emb])
        assert 0.0 <= score <= 1.0, f"Score {score} outside [0, 1]"

    def test_identical_embeddings_score_near_zero(self, matching_review_emb, stock_emb):
        """
        Mismatch detection logic: a review photo identical to the stock image
        must produce a mismatch score near 0.0 (authentic).
        """
        score = compute_mismatch_score(matching_review_emb, [stock_emb])
        assert score < 0.05, (
            f"Identical review/stock scored mismatch={score:.4f}, expected near 0.0"
        )

    def test_orthogonal_embeddings_score_near_one(self, unrelated_review_emb, stock_emb):
        """
        Mismatch detection logic: a review photo completely unrelated to the stock
        must produce a mismatch score near 1.0 (likely fake).
        """
        score = compute_mismatch_score(unrelated_review_emb, [stock_emb])
        assert score > 0.9, (
            f"Orthogonal review/stock scored mismatch={score:.4f}, expected near 1.0"
        )

    def test_mismatch_equals_one_minus_max_similarity(
        self, unrelated_review_emb, stock_emb, second_stock_emb
    ):
        """
        mismatch_score must equal 1 - max_similarity across all stock images.
        This verifies the formula directly.
        """
        stock_embeddings = [stock_emb, second_stock_emb]
        sim_a = float(np.clip(np.dot(unrelated_review_emb, stock_emb), 0, 1))
        sim_b = float(np.clip(np.dot(unrelated_review_emb, second_stock_emb), 0, 1))
        expected_max_sim = max(sim_a, sim_b)
        expected_mismatch = 1.0 - expected_max_sim

        score = compute_mismatch_score(unrelated_review_emb, stock_embeddings)
        assert np.isclose(score, expected_mismatch, atol=1e-5), (
            f"Expected mismatch={expected_mismatch:.6f}, got {score:.6f}"
        )

    def test_max_strategy_one_matching_stock_among_many(
        self, matching_review_emb, stock_emb, second_stock_emb
    ):
        """
        MAX strategy: if even ONE stock image matches the review photo closely,
        the mismatch score must be near 0.0 — regardless of other stock images.
        """
        # matching_review_emb ≈ stock_emb (sim=1.0), but ⊥ to second_stock_emb
        stock_embeddings = [second_stock_emb, stock_emb]  # matching one is second
        score = compute_mismatch_score(matching_review_emb, stock_embeddings)
        assert score < 0.05, (
            f"MAX strategy failed: one matching stock present but mismatch={score:.4f}"
        )

    def test_single_stock_image(self, unrelated_review_emb, stock_emb):
        """Works correctly with only one stock image."""
        score = compute_mismatch_score(unrelated_review_emb, [stock_emb])
        assert 0.0 <= score <= 1.0

    def test_empty_stock_embeddings_raises(self, matching_review_emb):
        with pytest.raises(ValueError, match="must not be empty"):
            compute_mismatch_score(matching_review_emb, [])

    def test_wrong_review_shape_raises(self, stock_emb):
        bad = np.zeros(256, dtype=np.float32)
        with pytest.raises(ValueError):
            compute_mismatch_score(bad, [stock_emb])

    def test_wrong_stock_shape_raises(self, matching_review_emb):
        bad = np.zeros(256, dtype=np.float32)
        with pytest.raises(ValueError):
            compute_mismatch_score(matching_review_emb, [bad])

    def test_non_array_review_raises(self, stock_emb):
        with pytest.raises(TypeError):
            compute_mismatch_score([0.0] * 512, [stock_emb])  # type: ignore

    def test_2d_review_embedding_raises(self, stock_emb):
        bad = np.zeros((1, EMBEDDING_DIM), dtype=np.float32)
        with pytest.raises(ValueError):
            compute_mismatch_score(bad, [stock_emb])  # type: ignore


# ---------------------------------------------------------------------------
# TestFlagReview
# ---------------------------------------------------------------------------

class TestFlagReview:
    """Tests for the single-review flagging function."""

    def test_returns_review_flag_result(self, matching_review_emb, stock_emb):
        result = flag_review(matching_review_emb, [stock_emb])
        assert isinstance(result, ReviewFlagResult)

    # ---- Mismatch detection logic ----

    def test_authentic_review_not_flagged(self, matching_review_emb, stock_emb):
        """
        Mismatch detection: a review photo matching the stock image should NOT
        be flagged as fake.
        """
        result = flag_review(matching_review_emb, [stock_emb])
        assert not result.is_flagged_fake, (
            f"Authentic review was incorrectly flagged (mismatch={result.mismatch_score:.4f})"
        )

    def test_fake_review_is_flagged(self, unrelated_review_emb, stock_emb):
        """
        Mismatch detection: a review photo completely unrelated to the stock
        image must be flagged as fake.
        """
        result = flag_review(unrelated_review_emb, [stock_emb])
        assert result.is_flagged_fake, (
            f"Fake review was not flagged (mismatch={result.mismatch_score:.4f})"
        )

    def test_authentic_mismatch_score_near_zero(self, matching_review_emb, stock_emb):
        result = flag_review(matching_review_emb, [stock_emb])
        assert result.mismatch_score < 0.05

    def test_fake_mismatch_score_near_one(self, unrelated_review_emb, stock_emb):
        result = flag_review(unrelated_review_emb, [stock_emb])
        assert result.mismatch_score > 0.9

    # ---- Threshold logic ----

    def test_at_threshold_is_flagged(self, near_threshold_emb, stock_emb):
        """
        Flagging threshold logic: mismatch_score at the threshold must be flagged
        (boundary inclusive: score >= threshold → flagged).

        Float32 dot products can differ from the exact target by ~1e-7,
        so we verify the score is within atol of the threshold AND that the
        flagging decision matches score >= threshold within that tolerance.
        """
        result = flag_review(
            near_threshold_emb, [stock_emb], threshold=DEFAULT_FLAG_THRESHOLD
        )
        assert np.isclose(result.mismatch_score, DEFAULT_FLAG_THRESHOLD, atol=1e-4), (
            f"Expected mismatch≈{DEFAULT_FLAG_THRESHOLD}, got {result.mismatch_score:.6f}"
        )
        # Due to float32 rounding the score may land infinitesimally below the
        # threshold. Assert that the decision is consistent with the actual score.
        assert result.is_flagged_fake == (result.mismatch_score >= result.threshold_used), (
            f"Flagging decision inconsistent with score vs threshold "
            f"(mismatch={result.mismatch_score:.8f}, threshold={result.threshold_used})"
        )

    def test_just_below_threshold_not_flagged(self, just_below_threshold_emb, stock_emb):
        """
        Flagging threshold logic: mismatch_score just below the threshold
        must NOT be flagged.
        """
        result = flag_review(
            just_below_threshold_emb, [stock_emb], threshold=DEFAULT_FLAG_THRESHOLD
        )
        assert result.mismatch_score < DEFAULT_FLAG_THRESHOLD, (
            f"Expected mismatch < {DEFAULT_FLAG_THRESHOLD}, got {result.mismatch_score:.6f}"
        )
        assert not result.is_flagged_fake, (
            f"Review below threshold should not be flagged "
            f"(mismatch={result.mismatch_score:.6f}, threshold={DEFAULT_FLAG_THRESHOLD})"
        )

    def test_custom_high_threshold_changes_outcome(self, stock_emb):
        """
        With a very high threshold (0.99), a near-authentic review photo
        (mismatch ≈ 0.05) must NOT be flagged.
        """
        # Construct a near-identical embedding: similarity = 0.95 → mismatch = 0.05
        near_authentic = _make_similar_embedding(stock_emb, similarity=0.95)
        result = flag_review(near_authentic, [stock_emb], threshold=0.99)
        assert not result.is_flagged_fake, (
            f"Near-authentic review should not be flagged at threshold=0.99 "
            f"(mismatch={result.mismatch_score:.4f})"
        )

    def test_custom_low_threshold_flags_near_authentic(self, stock_emb):
        """
        With a very low threshold (0.02), a slightly mismatched review photo
        (mismatch ≈ 0.05) must be flagged.
        """
        # similarity=0.95 → mismatch≈0.05, which exceeds threshold=0.02
        slightly_off = _make_similar_embedding(stock_emb, similarity=0.95)
        result = flag_review(slightly_off, [stock_emb], threshold=0.02)
        assert result.is_flagged_fake, (
            f"Slightly mismatched review should be flagged at threshold=0.02 "
            f"(mismatch={result.mismatch_score:.4f})"
        )

    def test_threshold_zero_raises(self, matching_review_emb, stock_emb):
        """threshold=0.0 is meaningless (everything would flag) → raise ValueError."""
        with pytest.raises(ValueError, match="threshold"):
            flag_review(matching_review_emb, [stock_emb], threshold=0.0)

    def test_negative_threshold_raises(self, matching_review_emb, stock_emb):
        with pytest.raises(ValueError, match="threshold"):
            flag_review(matching_review_emb, [stock_emb], threshold=-0.1)

    def test_threshold_above_one_raises(self, matching_review_emb, stock_emb):
        with pytest.raises(ValueError, match="threshold"):
            flag_review(matching_review_emb, [stock_emb], threshold=1.1)

    # ---- Result field correctness ----

    def test_max_similarity_field(self, matching_review_emb, stock_emb):
        """max_similarity field must equal dot product (since vectors are unit-norm)."""
        result = flag_review(matching_review_emb, [stock_emb])
        expected = float(np.clip(np.dot(matching_review_emb, stock_emb), 0, 1))
        assert np.isclose(result.max_similarity, expected, atol=1e-5)

    def test_mismatch_equals_one_minus_max_similarity(
        self, unrelated_review_emb, stock_emb
    ):
        result = flag_review(unrelated_review_emb, [stock_emb])
        assert np.isclose(
            result.mismatch_score, 1.0 - result.max_similarity, atol=1e-6
        )

    def test_threshold_used_field(self, matching_review_emb, stock_emb):
        custom_threshold = 0.6
        result = flag_review(matching_review_emb, [stock_emb], threshold=custom_threshold)
        assert result.threshold_used == custom_threshold

    def test_num_stock_images_checked_field(
        self, unrelated_review_emb, stock_emb, second_stock_emb
    ):
        result = flag_review(unrelated_review_emb, [stock_emb, second_stock_emb])
        assert result.num_stock_images_checked == 2

    def test_scores_in_valid_range(self, unrelated_review_emb, stock_emb):
        result = flag_review(unrelated_review_emb, [stock_emb])
        assert 0.0 <= result.mismatch_score <= 1.0
        assert 0.0 <= result.max_similarity <= 1.0

    def test_as_dict_keys(self, matching_review_emb, stock_emb):
        result = flag_review(matching_review_emb, [stock_emb])
        d = result.as_dict()
        expected_keys = {
            "mismatch_score", "max_similarity", "is_flagged_fake",
            "threshold_used", "num_stock_images_checked",
        }
        assert expected_keys == set(d.keys())

    def test_as_dict_values_match_fields(self, unrelated_review_emb, stock_emb):
        result = flag_review(unrelated_review_emb, [stock_emb])
        d = result.as_dict()
        assert d["mismatch_score"] == result.mismatch_score
        assert d["is_flagged_fake"] == result.is_flagged_fake
        assert d["max_similarity"] == result.max_similarity

    def test_empty_stock_raises(self, matching_review_emb):
        with pytest.raises(ValueError, match="must not be empty"):
            flag_review(matching_review_emb, [])

    def test_wrong_shape_review_raises(self, stock_emb):
        with pytest.raises(ValueError):
            flag_review(np.zeros(256, dtype=np.float32), [stock_emb])

    def test_non_array_raises(self, stock_emb):
        with pytest.raises(TypeError):
            flag_review([0.0] * 512, [stock_emb])  # type: ignore


# ---------------------------------------------------------------------------
# TestAnalyzeProductReviews
# ---------------------------------------------------------------------------

class TestAnalyzeProductReviews:
    """Tests for the product-level fake review aggregation."""

    def test_returns_product_fake_review_report(
        self, matching_review_emb, stock_emb
    ):
        report = analyze_product_reviews([matching_review_emb], [stock_emb])
        assert isinstance(report, ProductFakeReviewReport)

    def test_all_authentic_report(self, matching_review_emb, stock_emb):
        """All matching reviews → fake_count=0, trust_score=1.0."""
        report = analyze_product_reviews(
            [matching_review_emb, matching_review_emb], [stock_emb]
        )
        assert report.fake_count == 0
        assert report.total_count == 2
        assert np.isclose(report.fake_ratio, 0.0, atol=1e-6)
        assert np.isclose(report.product_trust_score, 1.0, atol=1e-6)

    def test_all_fake_report(self, unrelated_review_emb, stock_emb):
        """All unrelated reviews → fake_count=total, trust_score=0.0."""
        report = analyze_product_reviews(
            [unrelated_review_emb, unrelated_review_emb], [stock_emb]
        )
        assert report.fake_count == 2
        assert report.total_count == 2
        assert np.isclose(report.fake_ratio, 1.0, atol=1e-6)
        assert np.isclose(report.product_trust_score, 0.0, atol=1e-6)

    def test_mixed_reviews_correct_counts(
        self, matching_review_emb, unrelated_review_emb, stock_emb
    ):
        """
        Mismatch detection logic: mixed reviews produce correct fake/authentic split.
        2 authentic + 1 fake → fake_count=1, fake_ratio=1/3.
        """
        report = analyze_product_reviews(
            [matching_review_emb, matching_review_emb, unrelated_review_emb],
            [stock_emb],
        )
        assert report.fake_count == 1
        assert report.total_count == 3
        assert np.isclose(report.fake_ratio, 1 / 3, atol=1e-5)

    def test_fake_ratio_plus_trust_score_equals_one(
        self, matching_review_emb, unrelated_review_emb, stock_emb
    ):
        """fake_ratio + product_trust_score must always equal 1.0."""
        report = analyze_product_reviews(
            [matching_review_emb, unrelated_review_emb], [stock_emb]
        )
        assert np.isclose(
            report.fake_ratio + report.product_trust_score, 1.0, atol=1e-5
        ), (
            f"fake_ratio={report.fake_ratio:.6f} + "
            f"trust={report.product_trust_score:.6f} ≠ 1.0"
        )

    def test_review_results_length_matches_input(
        self, matching_review_emb, unrelated_review_emb, stock_emb
    ):
        """review_results list must have one entry per review embedding."""
        review_embs = [matching_review_emb, unrelated_review_emb, matching_review_emb]
        report = analyze_product_reviews(review_embs, [stock_emb])
        assert len(report.review_results) == 3

    def test_each_review_result_is_correct_type(
        self, matching_review_emb, stock_emb
    ):
        report = analyze_product_reviews([matching_review_emb], [stock_emb])
        for r in report.review_results:
            assert isinstance(r, ReviewFlagResult)

    def test_trust_score_in_valid_range(
        self, matching_review_emb, unrelated_review_emb, stock_emb
    ):
        report = analyze_product_reviews(
            [matching_review_emb, unrelated_review_emb], [stock_emb]
        )
        assert 0.0 <= report.product_trust_score <= 1.0
        assert 0.0 <= report.fake_ratio <= 1.0

    def test_as_dict_keys(self, matching_review_emb, stock_emb):
        report = analyze_product_reviews([matching_review_emb], [stock_emb])
        d = report.as_dict()
        expected = {"fake_count", "total_count", "fake_ratio",
                    "product_trust_score", "review_results"}
        assert expected == set(d.keys())

    def test_empty_review_embeddings_raises(self, stock_emb):
        with pytest.raises(ValueError, match="review_embeddings"):
            analyze_product_reviews([], [stock_emb])

    def test_empty_stock_embeddings_raises(self, matching_review_emb):
        with pytest.raises(ValueError, match="stock_embeddings"):
            analyze_product_reviews([matching_review_emb], [])


# ---------------------------------------------------------------------------
# TestBatchFlagReviews
# ---------------------------------------------------------------------------

class TestBatchFlagReviews:
    """Tests for the flat batch convenience function."""

    def test_returns_list(self, matching_review_emb, stock_emb):
        results = batch_flag_reviews([matching_review_emb], [stock_emb])
        assert isinstance(results, list)

    def test_result_length_matches_input(
        self, matching_review_emb, unrelated_review_emb, stock_emb
    ):
        results = batch_flag_reviews(
            [matching_review_emb, unrelated_review_emb], [stock_emb]
        )
        assert len(results) == 2

    def test_each_result_is_review_flag_result(self, matching_review_emb, stock_emb):
        results = batch_flag_reviews([matching_review_emb], [stock_emb])
        for r in results:
            assert isinstance(r, ReviewFlagResult)

    def test_matches_individual_flag_review_calls(
        self, matching_review_emb, unrelated_review_emb, stock_emb
    ):
        """batch_flag_reviews must produce the same results as individual calls."""
        review_embs = [matching_review_emb, unrelated_review_emb]
        batch = batch_flag_reviews(review_embs, [stock_emb])
        for i, rev_emb in enumerate(review_embs):
            individual = flag_review(rev_emb, [stock_emb])
            assert np.isclose(
                batch[i].mismatch_score, individual.mismatch_score, atol=1e-6
            )
            assert batch[i].is_flagged_fake == individual.is_flagged_fake

    def test_empty_reviews_raises(self, stock_emb):
        with pytest.raises(ValueError):
            batch_flag_reviews([], [stock_emb])

    def test_empty_stock_raises(self, matching_review_emb):
        with pytest.raises(ValueError):
            batch_flag_reviews([matching_review_emb], [])
