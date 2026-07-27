"""
Tests for core/clip_encoder.py

Assertions per plan:
  - Embeddings are the correct shape (512,)
  - Cosine similarity returns a float in range [0.0, 1.0]

Additional coverage:
  - Text embeddings are correct shape and normalized
  - Batch encoding returns (N, 512) array
  - Identical image embeddings have cosine similarity close to 1.0
  - cosine_similarity raises on shape mismatch
  - Empty text raises ValueError
"""

import numpy as np
import pytest
from PIL import Image

from app.core.clip_encoder import (
    EMBEDDING_DIM,
    cosine_similarity,
    encode_image,
    encode_images_batch,
    encode_text,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def random_rgb_image() -> Image.Image:
    """A synthetic 224x224 RGB PIL image with random pixel values."""
    rng = np.random.default_rng(seed=42)
    pixels = rng.integers(0, 256, (224, 224, 3), dtype=np.uint8)
    return Image.fromarray(pixels, mode="RGB")


@pytest.fixture(scope="module")
def another_random_rgb_image() -> Image.Image:
    """A second distinct synthetic image with a different seed."""
    rng = np.random.default_rng(seed=99)
    pixels = rng.integers(0, 256, (224, 224, 3), dtype=np.uint8)
    return Image.fromarray(pixels, mode="RGB")


@pytest.fixture(scope="module")
def image_embedding(random_rgb_image) -> np.ndarray:
    """Pre-computed embedding for the random image (expensive; done once per session)."""
    return encode_image(random_rgb_image)


@pytest.fixture(scope="module")
def text_embedding() -> np.ndarray:
    """Pre-computed text embedding for a fashion query."""
    return encode_text("blue cotton kurta with floral embroidery")


# ---------------------------------------------------------------------------
# Image embedding tests
# ---------------------------------------------------------------------------

class TestEncodeImage:
    def test_output_shape(self, image_embedding):
        """Embedding must be a 1-D vector of length EMBEDDING_DIM (512)."""
        assert image_embedding.ndim == 1, "Embedding must be 1-D"
        assert image_embedding.shape[0] == EMBEDDING_DIM, (
            f"Expected shape ({EMBEDDING_DIM},), got {image_embedding.shape}"
        )

    def test_output_dtype(self, image_embedding):
        """Embedding must be float32 for FAISS compatibility."""
        assert image_embedding.dtype == np.float32

    def test_embedding_is_unit_norm(self, image_embedding):
        """Embedding returned by encode_image must be L2-normalised."""
        norm = float(np.linalg.norm(image_embedding))
        assert np.isclose(norm, 1.0, atol=1e-5), (
            f"Expected L2 norm ≈ 1.0, got {norm}"
        )

    def test_accepts_pil_image(self, random_rgb_image):
        """encode_image must accept a PIL.Image.Image directly."""
        emb = encode_image(random_rgb_image)
        assert emb.shape == (EMBEDDING_DIM,)

    def test_accepts_bytes(self, random_rgb_image):
        """encode_image must accept raw image bytes."""
        import io
        buf = io.BytesIO()
        random_rgb_image.save(buf, format="PNG")
        emb = encode_image(buf.getvalue())
        assert emb.shape == (EMBEDDING_DIM,)

    def test_deterministic(self, random_rgb_image):
        """Same image should produce identical embeddings across two calls."""
        emb1 = encode_image(random_rgb_image)
        emb2 = encode_image(random_rgb_image)
        assert np.allclose(emb1, emb2, atol=1e-6), (
            "encode_image must be deterministic for the same input"
        )

    def test_different_images_produce_different_embeddings(
        self, random_rgb_image, another_random_rgb_image
    ):
        """Two distinct images must not produce the same embedding."""
        emb1 = encode_image(random_rgb_image)
        emb2 = encode_image(another_random_rgb_image)
        assert not np.allclose(emb1, emb2, atol=1e-4)

    def test_unsupported_type_raises(self):
        """encode_image must raise TypeError for unsupported input types."""
        with pytest.raises(TypeError):
            encode_image(12345)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Text embedding tests
# ---------------------------------------------------------------------------

class TestEncodeText:
    def test_output_shape(self, text_embedding):
        """Text embedding must be shape (512,)."""
        assert text_embedding.shape == (EMBEDDING_DIM,)

    def test_output_dtype(self, text_embedding):
        """Text embedding must be float32."""
        assert text_embedding.dtype == np.float32

    def test_embedding_is_unit_norm(self, text_embedding):
        """Text embedding must be L2-normalised."""
        norm = float(np.linalg.norm(text_embedding))
        assert np.isclose(norm, 1.0, atol=1e-5)

    def test_empty_text_raises(self):
        """encode_text must raise ValueError for empty or whitespace-only input."""
        with pytest.raises(ValueError):
            encode_text("")
        with pytest.raises(ValueError):
            encode_text("   ")

    def test_different_texts_differ(self):
        """Semantically different texts must produce distinct embeddings."""
        emb1 = encode_text("red saree with gold border")
        emb2 = encode_text("running shoes size 10")
        assert not np.allclose(emb1, emb2, atol=1e-4)


# ---------------------------------------------------------------------------
# Batch encoding tests
# ---------------------------------------------------------------------------

class TestEncodeImagesBatch:
    def test_output_shape(self, random_rgb_image, another_random_rgb_image):
        """Batch output must be shape (N, 512)."""
        embs = encode_images_batch([random_rgb_image, another_random_rgb_image])
        assert embs.shape == (2, EMBEDDING_DIM)

    def test_each_row_is_unit_norm(self, random_rgb_image, another_random_rgb_image):
        """Every row of the batch output must be L2-normalised."""
        embs = encode_images_batch([random_rgb_image, another_random_rgb_image])
        norms = np.linalg.norm(embs, axis=1)
        assert np.allclose(norms, 1.0, atol=1e-5), (
            f"Not all batch embeddings are unit-norm: {norms}"
        )

    def test_batch_matches_single(self, random_rgb_image):
        """Single-image batch must match output of encode_image."""
        single = encode_image(random_rgb_image)
        batch = encode_images_batch([random_rgb_image])
        assert np.allclose(single, batch[0], atol=1e-6)

    def test_empty_list_raises(self):
        """encode_images_batch must raise ValueError for an empty list."""
        with pytest.raises(ValueError):
            encode_images_batch([])


# ---------------------------------------------------------------------------
# Cosine similarity tests
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    def test_returns_float(self, image_embedding):
        """cosine_similarity must return a Python float."""
        sim = cosine_similarity(image_embedding, image_embedding)
        assert isinstance(sim, float)

    def test_identical_vectors_score_one(self, image_embedding):
        """Cosine similarity of a vector with itself must be ≈ 1.0."""
        sim = cosine_similarity(image_embedding, image_embedding)
        assert np.isclose(sim, 1.0, atol=1e-5), (
            f"Expected similarity ≈ 1.0 for identical vectors, got {sim}"
        )

    def test_result_in_valid_range(self, image_embedding, text_embedding):
        """Cosine similarity must always be in range [-1.0, 1.0]."""
        sim = cosine_similarity(image_embedding, text_embedding)
        assert -1.0 <= sim <= 1.0, (
            f"Similarity {sim} is outside [-1.0, 1.0]"
        )

    def test_image_text_similarity_non_negative(self, image_embedding, text_embedding):
        """
        For real fashion content, cosine similarity between an image and a
        relevant text description should be >= 0.0 (the plan specifies 0-1 range).
        """
        sim = cosine_similarity(image_embedding, text_embedding)
        assert sim >= 0.0, (
            f"Expected non-negative cross-modal similarity, got {sim}"
        )

    def test_shape_mismatch_raises(self, image_embedding):
        """cosine_similarity must raise ValueError for mismatched shapes."""
        wrong_shape = np.random.randn(256).astype(np.float32)
        with pytest.raises(ValueError):
            cosine_similarity(image_embedding, wrong_shape)

    def test_symmetry(self, image_embedding, text_embedding):
        """cosine_similarity(a, b) must equal cosine_similarity(b, a)."""
        sim_ab = cosine_similarity(image_embedding, text_embedding)
        sim_ba = cosine_similarity(text_embedding, image_embedding)
        assert np.isclose(sim_ab, sim_ba, atol=1e-6)
