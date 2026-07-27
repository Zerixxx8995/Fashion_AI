"""
Tests for core/faiss_index.py

Assertions:
  - Index starts empty, total grows on add()
  - search() returns SearchResult objects with scores in [0.0, 1.0]
  - Identical query returns the added product as top result with score ≈ 1.0
  - add_batch() correctly maps product IDs to embeddings
  - save() and load() round-trip preserves search results
  - Searching an empty index raises ValueError
  - Shape mismatch raises ValueError
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from app.core.clip_encoder import encode_text
from app.core.faiss_index import EMBEDDING_DIM, FashionFAISSIndex, SearchResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _random_unit_vec(seed: int = 0) -> np.ndarray:
    """Return a deterministic L2-normalised float32 vector of shape (512,)."""
    rng = np.random.default_rng(seed=seed)
    vec = rng.standard_normal(EMBEDDING_DIM).astype(np.float32)
    return vec / np.linalg.norm(vec)


def _random_unit_batch(n: int, seed: int = 0) -> np.ndarray:
    """Return a batch of n L2-normalised vectors, shape (n, 512)."""
    rng = np.random.default_rng(seed=seed)
    batch = rng.standard_normal((n, EMBEDDING_DIM)).astype(np.float32)
    norms = np.linalg.norm(batch, axis=1, keepdims=True)
    return batch / norms


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def empty_index() -> FashionFAISSIndex:
    """Fresh empty index for each test."""
    return FashionFAISSIndex()


@pytest.fixture
def populated_index() -> FashionFAISSIndex:
    """Index pre-loaded with 5 products."""
    idx = FashionFAISSIndex()
    for i in range(5):
        idx.add(f"product-{i}", _random_unit_vec(seed=i))
    return idx


# ---------------------------------------------------------------------------
# Index state tests
# ---------------------------------------------------------------------------

class TestFashionFAISSIndexState:
    def test_starts_empty(self, empty_index):
        assert empty_index.total == 0

    def test_add_increments_total(self, empty_index):
        empty_index.add("p1", _random_unit_vec(seed=1))
        assert empty_index.total == 1
        empty_index.add("p2", _random_unit_vec(seed=2))
        assert empty_index.total == 2

    def test_product_ids_property(self, empty_index):
        empty_index.add("alpha", _random_unit_vec(seed=10))
        empty_index.add("beta", _random_unit_vec(seed=11))
        assert empty_index.product_ids == ["alpha", "beta"]

    def test_add_wrong_shape_raises(self, empty_index):
        wrong = np.random.randn(256).astype(np.float32)
        with pytest.raises(ValueError):
            empty_index.add("bad", wrong)


# ---------------------------------------------------------------------------
# Batch add tests
# ---------------------------------------------------------------------------

class TestBatchAdd:
    def test_add_batch_updates_total(self, empty_index):
        ids = ["p0", "p1", "p2"]
        vecs = _random_unit_batch(3, seed=5)
        empty_index.add_batch(ids, vecs)
        assert empty_index.total == 3

    def test_add_batch_id_length_mismatch_raises(self, empty_index):
        ids = ["p0", "p1"]
        vecs = _random_unit_batch(3, seed=5)
        with pytest.raises(ValueError):
            empty_index.add_batch(ids, vecs)


# ---------------------------------------------------------------------------
# Search tests
# ---------------------------------------------------------------------------

class TestSearch:
    def test_empty_index_raises(self, empty_index):
        """Searching an empty index must raise ValueError."""
        query = _random_unit_vec(seed=0)
        with pytest.raises(ValueError):
            empty_index.search(query)

    def test_returns_search_result_objects(self, populated_index):
        query = _random_unit_vec(seed=99)
        results = populated_index.search(query, top_k=3)
        assert all(isinstance(r, SearchResult) for r in results)

    def test_scores_in_valid_range(self, populated_index):
        """All returned scores must be in [0.0, 1.0] for L2-normalised vectors."""
        query = _random_unit_vec(seed=77)
        results = populated_index.search(query, top_k=5)
        for r in results:
            assert 0.0 <= r.score <= 1.0, (
                f"Score {r.score} for product '{r.product_id}' is out of range"
            )

    def test_exact_match_scores_near_one(self, empty_index):
        """
        When the query IS the stored embedding, the top result must have
        cosine similarity ≈ 1.0.
        """
        vec = _random_unit_vec(seed=42)
        empty_index.add("exact-match", vec)
        results = empty_index.search(vec, top_k=1)
        assert len(results) == 1
        assert results[0].product_id == "exact-match"
        assert np.isclose(results[0].score, 1.0, atol=1e-5), (
            f"Expected score ≈ 1.0 for exact match, got {results[0].score}"
        )

    def test_results_sorted_descending(self, populated_index):
        """Results must be sorted by score in descending order."""
        query = _random_unit_vec(seed=123)
        results = populated_index.search(query, top_k=5)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True), (
            "Results are not sorted by score (descending)"
        )

    def test_top_k_limits_results(self, populated_index):
        """top_k parameter must limit number of returned results."""
        results = populated_index.search(_random_unit_vec(seed=0), top_k=2)
        assert len(results) <= 2

    def test_min_score_filters_results(self, empty_index):
        """min_score=1.0 must only allow perfect matches through."""
        vec = _random_unit_vec(seed=7)
        empty_index.add("near", vec)
        # Add a clearly different vector
        other = _random_unit_vec(seed=999)
        empty_index.add("other", other)
        results = empty_index.search(vec, top_k=2, min_score=0.99)
        # Only the exact match should survive the threshold
        assert all(r.score >= 0.99 for r in results)

    def test_returns_product_ids(self, empty_index):
        """Returned product IDs must match what was added."""
        empty_index.add("shirt-001", _random_unit_vec(seed=1))
        results = empty_index.search(_random_unit_vec(seed=1), top_k=1)
        assert results[0].product_id == "shirt-001"


# ---------------------------------------------------------------------------
# Retrieval test
# ---------------------------------------------------------------------------

class TestGetEmbedding:
    def test_get_known_id(self, empty_index):
        vec = _random_unit_vec(seed=55)
        empty_index.add("known", vec)
        retrieved = empty_index.get_embedding("known")
        assert retrieved is not None
        assert np.allclose(retrieved, vec, atol=1e-5)

    def test_get_unknown_id_returns_none(self, empty_index):
        assert empty_index.get_embedding("does-not-exist") is None


# ---------------------------------------------------------------------------
# Persistence tests
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_save_and_load_roundtrip(self, empty_index):
        """
        Index saved and reloaded must produce identical search results.
        """
        vec = _random_unit_vec(seed=42)
        empty_index.add("product-save-test", vec)

        with tempfile.TemporaryDirectory() as tmpdir:
            idx_path = Path(tmpdir) / "test.index"
            meta_path = Path(tmpdir) / "test.meta"

            empty_index.save(index_path=idx_path, meta_path=meta_path)

            # Load into a fresh index
            loaded = FashionFAISSIndex()
            loaded.load(index_path=idx_path, meta_path=meta_path)

        assert loaded.total == 1
        results = loaded.search(vec, top_k=1)
        assert results[0].product_id == "product-save-test"
        assert np.isclose(results[0].score, 1.0, atol=1e-5)

    def test_load_missing_file_raises(self, empty_index):
        with pytest.raises(FileNotFoundError):
            empty_index.load(
                index_path=Path("nonexistent.index"),
                meta_path=Path("nonexistent.meta"),
            )
