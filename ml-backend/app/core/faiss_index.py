"""
FAISS Index — Pure ML/CV layer.

Responsibility: Build, update, persist, and query a FAISS vector similarity
index over CLIP image embeddings.

Rules (enforced by architecture):
  - No HTTP knowledge. No business logic. No database calls.
  - All public functions are self-contained and operate only on numpy arrays
    and product IDs passed in from the service layer.
  - Index lives in memory and can be serialised/deserialised to disk.

Index type: IndexFlatIP (Inner Product on L2-normalised vectors = Cosine Similarity)
  - Exact search — no approximation. Chosen for correctness during MVP.
  - For scale (>1M vectors) swap to IndexIVFFlat or IndexHNSWFlat — the
    interface stays identical.

Embedding dimension: 512 (must match CLIP ViT-B/32 output from clip_encoder.py)
"""

from __future__ import annotations

import logging
import os
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import faiss
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMBEDDING_DIM = 512
DEFAULT_INDEX_PATH = Path("faiss_store/fashion.index")
DEFAULT_META_PATH = Path("faiss_store/fashion.meta")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    """A single result returned by a similarity search."""
    product_id: str
    score: float  # Cosine similarity in range [0.0, 1.0] for L2-normalised vectors


# ---------------------------------------------------------------------------
# FashionFAISSIndex
# ---------------------------------------------------------------------------

class FashionFAISSIndex:
    """
    In-memory FAISS index with a product_id mapping layer.

    FAISS only works with integer row indices (0, 1, 2, ...) — this class
    maintains a bidirectional mapping between FAISS row positions and
    arbitrary product ID strings (UUIDs).

    Usage:
        index = FashionFAISSIndex()
        index.add("product-uuid-1", embedding_vector)
        results = index.search(query_vector, top_k=5)
        index.save()
        index.load()
    """

    def __init__(self, dimension: int = EMBEDDING_DIM) -> None:
        """
        Initialise an empty FAISS index.

        Args:
            dimension: Embedding dimension. Must match CLIP output (512).
        """
        self.dimension = dimension
        # IndexFlatIP: exact inner product search. On L2-normalised vectors,
        # inner product == cosine similarity.
        self._index: faiss.IndexFlatIP = faiss.IndexFlatIP(dimension)
        # Ordered list of product IDs — index i maps to FAISS row i
        self._id_map: list[str] = []

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def add(self, product_id: str, embedding: np.ndarray) -> None:
        """
        Add a single product embedding to the index.

        Args:
            product_id: Unique string identifier for the product (e.g. UUID).
            embedding: L2-normalised float32 array of shape (512,).

        Raises:
            ValueError: If the embedding shape does not match the index dimension.
        """
        self._validate_embedding(embedding)
        # FAISS expects shape (n, d) — add row dimension
        vector = embedding.reshape(1, self.dimension).astype(np.float32)
        self._index.add(vector)
        self._id_map.append(product_id)
        logger.debug("Added product '%s'. Index size: %d", product_id, self.total)

    def add_batch(
        self,
        product_ids: list[str],
        embeddings: np.ndarray,
    ) -> None:
        """
        Add multiple embeddings in one operation (more efficient than add() in a loop).

        Args:
            product_ids: List of product ID strings, length N.
            embeddings: L2-normalised float32 array of shape (N, 512).

        Raises:
            ValueError: If lengths do not match or shapes are invalid.
        """
        if len(product_ids) != embeddings.shape[0]:
            raise ValueError(
                f"product_ids length ({len(product_ids)}) must match "
                f"embeddings rows ({embeddings.shape[0]})."
            )
        for embedding in embeddings:
            self._validate_embedding(embedding)

        batch = embeddings.astype(np.float32)
        self._index.add(batch)
        self._id_map.extend(product_ids)
        logger.info(
            "Batch-added %d products. Total index size: %d",
            len(product_ids),
            self.total,
        )

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> list[SearchResult]:
        """
        Find the top-k most similar products for a query embedding.

        Args:
            query_embedding: L2-normalised float32 array of shape (512,).
            top_k: Maximum number of results to return.
            min_score: Minimum cosine similarity threshold (0.0 to 1.0).
                       Results below this score are excluded.

        Returns:
            List of SearchResult objects sorted by score descending.
            May be shorter than top_k if the index has fewer items or
            min_score filters results out.

        Raises:
            ValueError: If the index is empty or the query shape is invalid.
        """
        if self.total == 0:
            raise ValueError("Cannot search an empty index. Add embeddings first.")
        self._validate_embedding(query_embedding)

        effective_k = min(top_k, self.total)
        query = query_embedding.reshape(1, self.dimension).astype(np.float32)

        # scores: (1, k) float32 — inner products (= cosine similarity)
        # indices: (1, k) int64 — FAISS row positions
        scores, indices = self._index.search(query, effective_k)

        results: list[SearchResult] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:  # FAISS returns -1 for unfilled slots
                continue
            similarity = float(np.clip(score, -1.0, 1.0))
            if similarity < min_score:
                continue
            results.append(SearchResult(
                product_id=self._id_map[idx],
                score=similarity,
            ))

        return results

    def get_embedding(self, product_id: str) -> Optional[np.ndarray]:
        """
        Retrieve the stored embedding for a known product ID.

        Args:
            product_id: The product UUID to look up.

        Returns:
            float32 array of shape (512,) if found, else None.
        """
        if product_id not in self._id_map:
            return None
        row = self._id_map.index(product_id)
        # FAISS reconstruct returns shape (d,)
        return self._index.reconstruct(row).astype(np.float32)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(
        self,
        index_path: Path = DEFAULT_INDEX_PATH,
        meta_path: Path = DEFAULT_META_PATH,
    ) -> None:
        """
        Persist the FAISS index and ID map to disk.

        Args:
            index_path: Path to write the FAISS binary index file.
            meta_path:  Path to write the Python pickle of the ID map.
        """
        index_path = Path(index_path)
        meta_path = Path(meta_path)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.parent.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self._index, str(index_path))
        with open(meta_path, "wb") as f:
            pickle.dump(self._id_map, f)

        logger.info(
            "Saved FAISS index (%d vectors) to '%s'", self.total, index_path
        )

    def load(
        self,
        index_path: Path = DEFAULT_INDEX_PATH,
        meta_path: Path = DEFAULT_META_PATH,
    ) -> None:
        """
        Load a persisted FAISS index and ID map from disk.

        Args:
            index_path: Path to the FAISS binary index file.
            meta_path:  Path to the Python pickle of the ID map.

        Raises:
            FileNotFoundError: If either file does not exist.
        """
        index_path = Path(index_path)
        meta_path = Path(meta_path)

        if not index_path.exists():
            raise FileNotFoundError(f"FAISS index file not found: {index_path}")
        if not meta_path.exists():
            raise FileNotFoundError(f"FAISS metadata file not found: {meta_path}")

        self._index = faiss.read_index(str(index_path))
        with open(meta_path, "rb") as f:
            self._id_map = pickle.load(f)

        logger.info(
            "Loaded FAISS index with %d vectors from '%s'", self.total, index_path
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @property
    def total(self) -> int:
        """Total number of vectors currently stored in the index."""
        return self._index.ntotal

    @property
    def product_ids(self) -> list[str]:
        """Read-only view of all product IDs in insertion order."""
        return list(self._id_map)

    def _validate_embedding(self, embedding: np.ndarray) -> None:
        """
        Raise ValueError if the embedding is not the expected shape.

        Args:
            embedding: Array to validate.

        Raises:
            ValueError: If shape is wrong or dtype is incompatible.
        """
        if embedding.ndim != 1 or embedding.shape[0] != self.dimension:
            raise ValueError(
                f"Expected embedding of shape ({self.dimension},), "
                f"got {embedding.shape}."
            )


# ---------------------------------------------------------------------------
# Module-level singleton (shared across the process)
# ---------------------------------------------------------------------------

_global_index: Optional[FashionFAISSIndex] = None


def get_index() -> FashionFAISSIndex:
    """
    Return the module-level shared FashionFAISSIndex instance.

    Creates a new empty index on the first call. Subsequent calls return
    the same object. In production, call load() on the returned index to
    restore a previously persisted state from disk.

    Returns:
        The shared FashionFAISSIndex instance.
    """
    global _global_index
    if _global_index is None:
        _global_index = FashionFAISSIndex()
        logger.info("Initialised new global FAISS index.")
    return _global_index
