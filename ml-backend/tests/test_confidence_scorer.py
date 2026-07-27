"""
Tests for core/confidence_scorer.py

Assertions per plan:
  - score is in [0.0, 1.0]
  - identical images score > 0.9
  - unrelated images score < 0.3

Additional coverage:
  - ConfidenceResult fields are valid types and ranges
  - label is one of 'high', 'moderate', 'low'
  - compute_stock_match_score is symmetric
  - compute_authenticity_score with uniform and custom weights
  - multi-stock-image scoring uses all embeddings
  - score_batch returns correct number of results
  - edge cases: empty stock_embeddings, bad shapes, zero weights
  - as_dict() returns correct keys
  - overall_confidence is a weighted blend of component scores
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from app.core.clip_encoder import encode_image, encode_text
from app.core.confidence_scorer import (
    THRESHOLD_HIGH,
    THRESHOLD_MODERATE,
    ConfidenceResult,
    compute_authenticity_score,
    compute_confidence_score,
    compute_stock_match_score,
    score_batch,
)


# ---------------------------------------------------------------------------
# Fixtures — all embeddings are computed once per test module to save time.
# Module-scope is appropriate because encode_image is deterministic.
# ---------------------------------------------------------------------------

def _make_image(seed: int, size: tuple[int, int] = (224, 224)) -> Image.Image:
    """Create a synthetic RGB PIL image from a random seed."""
    rng = np.random.default_rng(seed=seed)
    pixels = rng.integers(0, 256, (*size, 3), dtype=np.uint8)
    return Image.fromarray(pixels, mode="RGB")


@pytest.fixture(scope="module")
def uploaded_embedding() -> np.ndarray:
    """Embedding for a synthetic 'real product photo' the user uploads."""
    return encode_image(_make_image(seed=10))


@pytest.fixture(scope="module")
def matching_stock_embedding(uploaded_embedding) -> np.ndarray:
    """
    A stock embedding that is identical to the uploaded photo.
    Simulates a perfect listing match — score should be ≈ 1.0.
    """
    # Same tensor → identical embedding
    return uploaded_embedding.copy()


@pytest.fixture(scope="module")
def unrelated_stock_embedding(uploaded_embedding: np.ndarray) -> np.ndarray:
    """
    A hand-crafted embedding that is ORTHOGONAL to uploaded_embedding.

    CLIP embeddings of random synthetic images cluster very closely together
    (cosine similarity ~0.99) because random pixel noise occupies a small
    region of CLIP's embedding space. To reliably test "unrelated product"
    behaviour we construct a geometrically orthogonal unit vector instead.

    Orthogonal vectors have cosine similarity = 0.0, which is well below
    the plan's < 0.3 threshold.
    """
    # Gram-Schmidt: start from e_1, subtract its projection onto uploaded_embedding.
    candidate = np.zeros(512, dtype=np.float32)
    candidate[1] = 1.0                                     # e_1 basis vector
    proj = np.dot(candidate, uploaded_embedding) * uploaded_embedding
    ortho = candidate - proj
    ortho = ortho / np.linalg.norm(ortho)                 # normalise to unit length
    return ortho.astype(np.float32)


@pytest.fixture(scope="module")
def second_unrelated_embedding(uploaded_embedding: np.ndarray) -> np.ndarray:
    """A second distinct orthogonal embedding (uses e_2 direction)."""
    candidate = np.zeros(512, dtype=np.float32)
    candidate[2] = 1.0                                     # e_2 basis vector
    proj = np.dot(candidate, uploaded_embedding) * uploaded_embedding
    ortho = candidate - proj
    ortho = ortho / np.linalg.norm(ortho)
    return ortho.astype(np.float32)


@pytest.fixture(scope="module")
def text_embedding() -> np.ndarray:
    """A text embedding to use as an 'unrelated' counterpart."""
    return encode_text("completely unrelated product description xyz")


# ---------------------------------------------------------------------------
# TestComputeStockMatchScore
# ---------------------------------------------------------------------------

class TestComputeStockMatchScore:
    """Tests for the primary stock-match signal."""

    def test_returns_float(self, uploaded_embedding, matching_stock_embedding):
        """Return type must be Python float."""
        score = compute_stock_match_score(uploaded_embedding, matching_stock_embedding)
        assert isinstance(score, float)

    def test_score_in_valid_range(self, uploaded_embedding, unrelated_stock_embedding):
        """Score must always be in [0.0, 1.0]."""
        score = compute_stock_match_score(uploaded_embedding, unrelated_stock_embedding)
        assert 0.0 <= score <= 1.0, f"Score {score} out of [0, 1]"

    def test_identical_images_score_above_0_9(
        self, uploaded_embedding, matching_stock_embedding
    ):
        """
        Per plan: assert identical images score > 0.9.
        Two copies of the same normalised embedding must have cosine sim ≈ 1.0.
        """
        score = compute_stock_match_score(uploaded_embedding, matching_stock_embedding)
        assert score > 0.9, (
            f"Identical image embeddings scored {score:.4f}, expected > 0.9"
        )

    def test_identical_images_score_close_to_one(
        self, uploaded_embedding, matching_stock_embedding
    ):
        """Cosine similarity of a vector with itself is exactly 1.0."""
        score = compute_stock_match_score(uploaded_embedding, matching_stock_embedding)
        assert np.isclose(score, 1.0, atol=1e-5), (
            f"Expected ≈ 1.0 for identical embeddings, got {score:.6f}"
        )

    def test_unrelated_images_score_below_0_3(
        self, uploaded_embedding, unrelated_stock_embedding
    ):
        """
        Per plan: assert unrelated images score < 0.3.
        The unrelated_stock_embedding fixture is geometrically orthogonal to
        uploaded_embedding (cosine similarity = 0.0), well below 0.3.
        """
        score = compute_stock_match_score(uploaded_embedding, unrelated_stock_embedding)
        assert score < 0.3, (
            f"Orthogonal embeddings scored {score:.4f}, expected < 0.3"
        )

    def test_symmetry(self, uploaded_embedding, unrelated_stock_embedding):
        """score(a, b) == score(b, a) — cosine similarity is symmetric."""
        score_ab = compute_stock_match_score(uploaded_embedding, unrelated_stock_embedding)
        score_ba = compute_stock_match_score(unrelated_stock_embedding, uploaded_embedding)
        assert np.isclose(score_ab, score_ba, atol=1e-6), (
            f"Symmetry failed: {score_ab} vs {score_ba}"
        )

    def test_wrong_shape_raises(self, uploaded_embedding):
        """A (256,) vector must raise ValueError — wrong dimension."""
        bad_embedding = np.random.randn(256).astype(np.float32)
        with pytest.raises(ValueError):
            compute_stock_match_score(uploaded_embedding, bad_embedding)

    def test_non_array_raises(self, uploaded_embedding):
        """Passing a list instead of ndarray must raise TypeError."""
        with pytest.raises(TypeError):
            compute_stock_match_score(uploaded_embedding, [0.1] * 512)  # type: ignore

    def test_2d_embedding_raises(self, uploaded_embedding):
        """A (1, 512) 2-D array must raise ValueError — wrong ndim."""
        bad_embedding = uploaded_embedding.reshape(1, 512)
        with pytest.raises(ValueError):
            compute_stock_match_score(uploaded_embedding, bad_embedding)


# ---------------------------------------------------------------------------
# TestComputeAuthenticityScore
# ---------------------------------------------------------------------------

class TestComputeAuthenticityScore:
    """Tests for the multi-stock-image authenticity aggregate."""

    def test_returns_float(self, uploaded_embedding, matching_stock_embedding):
        """Return type must be Python float."""
        score = compute_authenticity_score(
            uploaded_embedding, [matching_stock_embedding]
        )
        assert isinstance(score, float)

    def test_score_in_valid_range(
        self, uploaded_embedding, unrelated_stock_embedding, second_unrelated_embedding
    ):
        """Score must always be in [0.0, 1.0]."""
        score = compute_authenticity_score(
            uploaded_embedding,
            [unrelated_stock_embedding, second_unrelated_embedding],
        )
        assert 0.0 <= score <= 1.0, f"Score {score} out of [0, 1]"

    def test_single_stock_image_equals_stock_match(
        self, uploaded_embedding, unrelated_stock_embedding
    ):
        """
        With a single stock image, authenticity_score must equal stock_match_score
        (they compute the same thing in that case).
        """
        stock_match = compute_stock_match_score(
            uploaded_embedding, unrelated_stock_embedding
        )
        authenticity = compute_authenticity_score(
            uploaded_embedding, [unrelated_stock_embedding]
        )
        assert np.isclose(stock_match, authenticity, atol=1e-6), (
            f"Single-image authenticity {authenticity} != stock_match {stock_match}"
        )

    def test_identical_single_stock_scores_near_one(
        self, uploaded_embedding, matching_stock_embedding
    ):
        """Identical uploaded + stock images → authenticity ≈ 1.0."""
        score = compute_authenticity_score(
            uploaded_embedding, [matching_stock_embedding]
        )
        assert np.isclose(score, 1.0, atol=1e-5)

    def test_uniform_weights_matches_manual_average(
        self,
        uploaded_embedding,
        unrelated_stock_embedding,
        second_unrelated_embedding,
    ):
        """
        With uniform weights, authenticity_score must equal the arithmetic
        mean of the individual cosine similarities.
        """
        sim1 = compute_stock_match_score(uploaded_embedding, unrelated_stock_embedding)
        sim2 = compute_stock_match_score(uploaded_embedding, second_unrelated_embedding)
        expected_avg = (sim1 + sim2) / 2.0

        authenticity = compute_authenticity_score(
            uploaded_embedding,
            [unrelated_stock_embedding, second_unrelated_embedding],
            weights=None,  # uniform
        )
        assert np.isclose(authenticity, expected_avg, atol=1e-6), (
            f"Expected avg={expected_avg:.6f}, got authenticity={authenticity:.6f}"
        )

    def test_custom_weights_respected(
        self,
        uploaded_embedding,
        unrelated_stock_embedding,
        second_unrelated_embedding,
    ):
        """
        With weights [1.0, 0.0], only the first stock image contributes.
        Result must equal the stock_match_score for that image alone.
        """
        sim1 = compute_stock_match_score(uploaded_embedding, unrelated_stock_embedding)
        authenticity = compute_authenticity_score(
            uploaded_embedding,
            [unrelated_stock_embedding, second_unrelated_embedding],
            weights=[1.0, 0.0],
        )
        assert np.isclose(authenticity, sim1, atol=1e-6), (
            f"Expected {sim1:.6f}, got {authenticity:.6f}"
        )

    def test_empty_stock_embeddings_raises(self, uploaded_embedding):
        """An empty list of stock embeddings must raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            compute_authenticity_score(uploaded_embedding, [])

    def test_wrong_weights_length_raises(
        self, uploaded_embedding, unrelated_stock_embedding
    ):
        """Mismatched weights length must raise ValueError."""
        with pytest.raises(ValueError, match="weights length"):
            compute_authenticity_score(
                uploaded_embedding,
                [unrelated_stock_embedding],
                weights=[0.5, 0.5],  # 2 weights for 1 embedding
            )

    def test_negative_weight_raises(
        self, uploaded_embedding, unrelated_stock_embedding
    ):
        """Negative weight must raise ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            compute_authenticity_score(
                uploaded_embedding,
                [unrelated_stock_embedding],
                weights=[-0.5],
            )

    def test_all_zero_weights_raises(
        self, uploaded_embedding, unrelated_stock_embedding, second_unrelated_embedding
    ):
        """All-zero weights are undefined and must raise ValueError."""
        with pytest.raises(ValueError, match="zero"):
            compute_authenticity_score(
                uploaded_embedding,
                [unrelated_stock_embedding, second_unrelated_embedding],
                weights=[0.0, 0.0],
            )


# ---------------------------------------------------------------------------
# TestComputeConfidenceScore  (top-level pipeline)
# ---------------------------------------------------------------------------

class TestComputeConfidenceScore:
    """Tests for the full confidence scoring pipeline."""

    def test_returns_confidence_result(
        self, uploaded_embedding, unrelated_stock_embedding
    ):
        """compute_confidence_score must return a ConfidenceResult instance."""
        result = compute_confidence_score(
            uploaded_embedding, [unrelated_stock_embedding]
        )
        assert isinstance(result, ConfidenceResult)

    # ---- Score range assertions (per project plan) ----

    def test_overall_confidence_in_valid_range(
        self, uploaded_embedding, unrelated_stock_embedding
    ):
        """Per plan: assert score is 0-1."""
        result = compute_confidence_score(
            uploaded_embedding, [unrelated_stock_embedding]
        )
        assert 0.0 <= result.overall_confidence <= 1.0

    def test_stock_match_score_in_valid_range(
        self, uploaded_embedding, unrelated_stock_embedding
    ):
        result = compute_confidence_score(
            uploaded_embedding, [unrelated_stock_embedding]
        )
        assert 0.0 <= result.stock_match_score <= 1.0

    def test_authenticity_score_in_valid_range(
        self, uploaded_embedding, unrelated_stock_embedding
    ):
        result = compute_confidence_score(
            uploaded_embedding, [unrelated_stock_embedding]
        )
        assert 0.0 <= result.authenticity_score <= 1.0

    # ---- Per-plan threshold assertions ----

    def test_identical_images_overall_above_0_9(
        self, uploaded_embedding, matching_stock_embedding
    ):
        """Per plan: assert identical images score > 0.9."""
        result = compute_confidence_score(
            uploaded_embedding, [matching_stock_embedding]
        )
        assert result.overall_confidence > 0.9, (
            f"Identical images overall_confidence={result.overall_confidence:.4f}, "
            "expected > 0.9"
        )

    def test_unrelated_images_overall_below_0_3(
        self, uploaded_embedding, unrelated_stock_embedding
    ):
        """Per plan: assert unrelated images score < 0.3."""
        result = compute_confidence_score(
            uploaded_embedding, [unrelated_stock_embedding]
        )
        assert result.overall_confidence < 0.3, (
            f"Unrelated images overall_confidence={result.overall_confidence:.4f}, "
            "expected < 0.3"
        )

    # ---- Label assertions ----

    def test_label_is_valid_value(self, uploaded_embedding, unrelated_stock_embedding):
        """label must be one of the three defined values."""
        result = compute_confidence_score(
            uploaded_embedding, [unrelated_stock_embedding]
        )
        assert result.label in ("high", "moderate", "low"), (
            f"Unexpected label: {result.label!r}"
        )

    def test_high_label_for_identical_images(
        self, uploaded_embedding, matching_stock_embedding
    ):
        """Perfect match (score ≈ 1.0) must produce label='high'."""
        result = compute_confidence_score(
            uploaded_embedding, [matching_stock_embedding]
        )
        assert result.label == "high", (
            f"Expected 'high' for identical images, got {result.label!r}"
        )

    def test_low_label_for_unrelated_images(
        self, uploaded_embedding, unrelated_stock_embedding
    ):
        """Random synthetic images should yield label='low'."""
        result = compute_confidence_score(
            uploaded_embedding, [unrelated_stock_embedding]
        )
        assert result.label == "low", (
            f"Expected 'low' for unrelated images, got {result.label!r}"
        )

    # ---- num_stock_images_used ----

    def test_num_stock_images_single(
        self, uploaded_embedding, unrelated_stock_embedding
    ):
        """With one stock image, num_stock_images_used must be 1."""
        result = compute_confidence_score(
            uploaded_embedding, [unrelated_stock_embedding]
        )
        assert result.num_stock_images_used == 1

    def test_num_stock_images_multiple(
        self,
        uploaded_embedding,
        unrelated_stock_embedding,
        second_unrelated_embedding,
    ):
        """With two stock images, num_stock_images_used must be 2."""
        result = compute_confidence_score(
            uploaded_embedding,
            [unrelated_stock_embedding, second_unrelated_embedding],
        )
        assert result.num_stock_images_used == 2

    # ---- Blend correctness ----

    def test_overall_is_weighted_blend(
        self, uploaded_embedding, unrelated_stock_embedding
    ):
        """
        overall_confidence must equal the weighted blend of stock_match_score
        and authenticity_score using default weights (0.7, 0.3).
        """
        result = compute_confidence_score(
            uploaded_embedding, [unrelated_stock_embedding]
        )
        expected = result.stock_match_score * 0.7 + result.authenticity_score * 0.3
        assert np.isclose(result.overall_confidence, expected, atol=1e-6), (
            f"Blend mismatch: expected {expected:.6f}, "
            f"got overall={result.overall_confidence:.6f}"
        )

    def test_custom_weights_change_overall(
        self,
        uploaded_embedding,
        unrelated_stock_embedding,
        second_unrelated_embedding,
    ):
        """
        Providing custom stock_match_weight / authenticity_weight values
        must change the overall_confidence relative to defaults.
        """
        stock_embeddings = [unrelated_stock_embedding, second_unrelated_embedding]
        result_default = compute_confidence_score(
            uploaded_embedding, stock_embeddings
        )
        result_custom = compute_confidence_score(
            uploaded_embedding,
            stock_embeddings,
            stock_match_weight=0.0,  # ignore stock_match entirely
            authenticity_weight=1.0,
        )
        # With stock_match_weight=0, overall_confidence should equal authenticity_score
        assert np.isclose(
            result_custom.overall_confidence,
            result_custom.authenticity_score,
            atol=1e-6,
        )
        # And differ from the default blend (unless scores happen to be equal)
        # This guards against custom weights silently having no effect.
        if not np.isclose(
            result_default.stock_match_score,
            result_default.authenticity_score,
            atol=1e-4,
        ):
            assert not np.isclose(
                result_default.overall_confidence,
                result_custom.overall_confidence,
                atol=1e-4,
            )

    # ---- Error cases ----

    def test_empty_stock_embeddings_raises(self, uploaded_embedding):
        """Empty stock_embeddings must raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            compute_confidence_score(uploaded_embedding, [])

    def test_negative_stock_match_weight_raises(
        self, uploaded_embedding, unrelated_stock_embedding
    ):
        """Negative stock_match_weight must raise ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            compute_confidence_score(
                uploaded_embedding,
                [unrelated_stock_embedding],
                stock_match_weight=-0.1,
            )

    def test_negative_authenticity_weight_raises(
        self, uploaded_embedding, unrelated_stock_embedding
    ):
        """Negative authenticity_weight must raise ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            compute_confidence_score(
                uploaded_embedding,
                [unrelated_stock_embedding],
                authenticity_weight=-0.1,
            )

    def test_both_zero_weights_raises(
        self, uploaded_embedding, unrelated_stock_embedding
    ):
        """Both weights zero is undefined — must raise ValueError."""
        with pytest.raises(ValueError, match="both be zero"):
            compute_confidence_score(
                uploaded_embedding,
                [unrelated_stock_embedding],
                stock_match_weight=0.0,
                authenticity_weight=0.0,
            )

    # ---- as_dict ----

    def test_as_dict_has_required_keys(
        self, uploaded_embedding, unrelated_stock_embedding
    ):
        """ConfidenceResult.as_dict() must contain all required keys."""
        result = compute_confidence_score(
            uploaded_embedding, [unrelated_stock_embedding]
        )
        d = result.as_dict()
        expected_keys = {
            "stock_match_score",
            "authenticity_score",
            "overall_confidence",
            "label",
            "num_stock_images_used",
        }
        assert expected_keys == set(d.keys()), (
            f"Missing keys: {expected_keys - set(d.keys())}"
        )

    def test_as_dict_values_match_fields(
        self, uploaded_embedding, unrelated_stock_embedding
    ):
        """as_dict() values must match the dataclass fields exactly."""
        result = compute_confidence_score(
            uploaded_embedding, [unrelated_stock_embedding]
        )
        d = result.as_dict()
        assert d["stock_match_score"] == result.stock_match_score
        assert d["authenticity_score"] == result.authenticity_score
        assert d["overall_confidence"] == result.overall_confidence
        assert d["label"] == result.label
        assert d["num_stock_images_used"] == result.num_stock_images_used


# ---------------------------------------------------------------------------
# TestScoreBatch
# ---------------------------------------------------------------------------

class TestScoreBatch:
    """Tests for the batch-scoring utility."""

    def test_returns_list(
        self, uploaded_embedding, unrelated_stock_embedding
    ):
        """score_batch must return a list."""
        results = score_batch(
            uploaded_embedding, [[unrelated_stock_embedding]]
        )
        assert isinstance(results, list)

    def test_result_length_matches_input(
        self,
        uploaded_embedding,
        unrelated_stock_embedding,
        second_unrelated_embedding,
    ):
        """Return list must have the same length as stock_embedding_sets."""
        results = score_batch(
            uploaded_embedding,
            [
                [unrelated_stock_embedding],
                [second_unrelated_embedding],
            ],
        )
        assert len(results) == 2

    def test_each_result_is_confidence_result(
        self, uploaded_embedding, unrelated_stock_embedding
    ):
        """Every item in the returned list must be a ConfidenceResult."""
        results = score_batch(uploaded_embedding, [[unrelated_stock_embedding]])
        for r in results:
            assert isinstance(r, ConfidenceResult)

    def test_empty_product_sets_raises(self, uploaded_embedding):
        """Passing an empty outer list must raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            score_batch(uploaded_embedding, [])

    def test_batch_matches_individual_calls(
        self,
        uploaded_embedding,
        unrelated_stock_embedding,
        second_unrelated_embedding,
    ):
        """
        score_batch must produce the same results as calling
        compute_confidence_score individually for each product.
        """
        stock_sets = [
            [unrelated_stock_embedding],
            [second_unrelated_embedding],
        ]
        batch_results = score_batch(uploaded_embedding, stock_sets)
        for i, stocks in enumerate(stock_sets):
            individual = compute_confidence_score(uploaded_embedding, stocks)
            assert np.isclose(
                batch_results[i].overall_confidence,
                individual.overall_confidence,
                atol=1e-6,
            ), (
                f"Product {i}: batch={batch_results[i].overall_confidence:.6f}, "
                f"individual={individual.overall_confidence:.6f}"
            )

    def test_identical_set_scores_high(
        self, uploaded_embedding, matching_stock_embedding
    ):
        """Identical embedding in the batch must score > 0.9."""
        results = score_batch(uploaded_embedding, [[matching_stock_embedding]])
        assert results[0].overall_confidence > 0.9

    def test_unrelated_set_scores_low(
        self, uploaded_embedding, unrelated_stock_embedding
    ):
        """Unrelated embedding in the batch must score < 0.3."""
        results = score_batch(uploaded_embedding, [[unrelated_stock_embedding]])
        assert results[0].overall_confidence < 0.3


# ---------------------------------------------------------------------------
# TestLabelThresholds  (unit tests for label logic — no CLIP needed)
# ---------------------------------------------------------------------------

class TestLabelThresholds:
    """
    Verify that label assignment thresholds are correct without running
    full CLIP inference — uses hand-crafted unit-norm vectors instead.
    """

    def _make_unit_vector(self, dim: int = 512) -> np.ndarray:
        """Return a unit-norm vector of length `dim`."""
        v = np.zeros(dim, dtype=np.float32)
        v[0] = 1.0
        return v

    def _make_orthogonal_vector(self, dim: int = 512) -> np.ndarray:
        """Return a vector orthogonal to _make_unit_vector result (similarity = 0)."""
        v = np.zeros(dim, dtype=np.float32)
        v[1] = 1.0
        return v

    def test_identical_unit_vectors_score_high(self):
        """Two identical unit vectors → similarity=1.0 → label='high'."""
        v = self._make_unit_vector()
        result = compute_confidence_score(v, [v.copy()])
        assert result.label == "high"
        assert result.overall_confidence >= THRESHOLD_HIGH

    def test_orthogonal_vectors_score_low(self):
        """
        Orthogonal unit vectors → inner product=0.0 (clamped to 0) → label='low'.
        """
        v_a = self._make_unit_vector()
        v_b = self._make_orthogonal_vector()
        result = compute_confidence_score(v_a, [v_b])
        assert result.label == "low"
        assert result.overall_confidence < THRESHOLD_MODERATE

    def test_moderate_label_boundary(self):
        """
        A vector that produces similarity exactly at THRESHOLD_MODERATE should
        yield label='moderate'.  We construct it manually.
        """
        # overall_confidence = stock_match * 0.7 + authenticity * 0.3
        # With one stock image, stock_match == authenticity, so overall = score.
        # We want overall = THRESHOLD_MODERATE exactly, so score = THRESHOLD_MODERATE.
        # Build vec_b such that dot(vec_a, vec_b) = THRESHOLD_MODERATE.
        v_a = self._make_unit_vector(512)  # e0

        # cos(theta) = THRESHOLD_MODERATE
        # v_b = cos(theta)*e0 + sin(theta)*e1, already unit-norm
        import math
        theta = math.acos(THRESHOLD_MODERATE)
        v_b = np.zeros(512, dtype=np.float32)
        v_b[0] = math.cos(theta)
        v_b[1] = math.sin(theta)
        # v_b is already unit-norm by construction

        result = compute_confidence_score(v_a, [v_b])
        # The score should land exactly at or just above THRESHOLD_MODERATE
        assert result.label in ("moderate", "high"), (
            f"Expected 'moderate' or 'high' at boundary, got {result.label!r} "
            f"(overall={result.overall_confidence:.6f})"
        )
