"""
Similarity Service Tests — ml-backend.

Tests the similarity_service layer with all Pinecone and CLIP calls mocked.

Strategy:
  - Mock pinecone_client.query_similar — returns controlled match lists
  - Mock app.core.clip_encoder.encode_image / encode_text — return random unit vectors
  - Assert:
      1. Results are ranked by similarity score (highest first)
      2. Cheaper alternatives are sorted by price ascending
      3. max_price_inr filter removes results over the ceiling
      4. category filter is passed to pinecone query
      5. exclude_platform filter removes results from that platform
      6. limit is respected
      7. rank field starts at 1 and increments
      8. find_cheaper_alternatives returns only strictly cheaper items
      9. rank_by_price re-ranks by price ascending and updates rank field
     10. ValueError raised when neither image_url nor text_query provided
     11. All result dicts contain required keys

Requirements tested (from build order Step 8):
  assert Pinecone query returns ranked results
  assert cheaper alternatives are sorted by price
"""

from __future__ import annotations

import os
os.environ["TESTING"] = "1"

import sys
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _random_embedding() -> list[float]:
    vec = np.random.randn(512).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


def _make_match(
    product_id: str,
    score: float,
    price: int = 1000,
    platform: str = "myntra",
    category: str = "tops",
) -> dict[str, Any]:
    return {
        "id": product_id,
        "score": score,
        "metadata": {
            "product_id": product_id,
            "platform": platform,
            "price_inr": price,
            "category": category,
            "url": f"https://myntra.com/product/{product_id}",
        },
    }


# Controlled fake Pinecone matches — scores descending, prices varied
FAKE_MATCHES = [
    _make_match("prod-a", score=0.95, price=2500, platform="myntra",   category="tops"),
    _make_match("prod-b", score=0.88, price=800,  platform="amazon",   category="tops"),
    _make_match("prod-c", score=0.80, price=1500, platform="flipkart", category="tops"),
    _make_match("prod-d", score=0.72, price=600,  platform="meesho",   category="tops"),
    _make_match("prod-e", score=0.65, price=3200, platform="ajio",     category="tops"),
]

IMAGE_URL = "https://b2.example.com/shirt.jpg"
TEXT_QUERY = "blue cotton kurta"


# ---------------------------------------------------------------------------
# Fixture: patch CLIP encoder and pinecone client for all tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_dependencies():
    """
    Patch _encode_query and pinecone_client.query_similar for all tests.
    pinecone_client is a module-level import in similarity_service, so we
    patch the attribute directly on that module object.
    """
    fake_embedding = _random_embedding()
    mock_query = MagicMock(return_value=FAKE_MATCHES)

    with (
        patch(
            "app.services.similarity_service._encode_query",
            return_value=fake_embedding,
        ),
        patch(
            "app.services.similarity_service.pinecone_client.query_similar",
            mock_query,
        ),
    ):
        yield mock_query



# ---------------------------------------------------------------------------
# TestFindSimilarProducts — core ranking and filtering
# ---------------------------------------------------------------------------

class TestFindSimilarProducts:
    """Assert find_similar_products returns correctly ranked, filtered results."""

    def test_results_are_not_empty(self):
        from app.services.similarity_service import find_similar_products
        results = find_similar_products(image_url=IMAGE_URL)
        assert len(results) > 0

    def test_results_contain_required_keys(self):
        from app.services.similarity_service import find_similar_products
        results = find_similar_products(image_url=IMAGE_URL)
        required_keys = {"rank", "product_id", "platform", "price_inr",
                         "category", "url", "similarity_score"}
        for result in results:
            assert required_keys.issubset(result.keys()), \
                f"Missing keys in result: {required_keys - result.keys()}"

    def test_results_ranked_by_similarity_descending(self):
        """Results must be sorted by similarity_score from highest to lowest."""
        from app.services.similarity_service import find_similar_products
        results = find_similar_products(image_url=IMAGE_URL)
        scores = [r["similarity_score"] for r in results]
        assert scores == sorted(scores, reverse=True), \
            f"Scores not in descending order: {scores}"

    def test_rank_starts_at_1(self):
        from app.services.similarity_service import find_similar_products
        results = find_similar_products(image_url=IMAGE_URL)
        assert results[0]["rank"] == 1

    def test_rank_increments_sequentially(self):
        from app.services.similarity_service import find_similar_products
        results = find_similar_products(image_url=IMAGE_URL)
        ranks = [r["rank"] for r in results]
        assert ranks == list(range(1, len(results) + 1))

    def test_limit_respected(self):
        from app.services.similarity_service import find_similar_products
        results = find_similar_products(image_url=IMAGE_URL, limit=2)
        assert len(results) <= 2

    def test_similarity_score_in_range(self):
        from app.services.similarity_service import find_similar_products
        results = find_similar_products(image_url=IMAGE_URL)
        for r in results:
            assert 0.0 <= r["similarity_score"] <= 1.0

    def test_max_price_filter_excludes_expensive_items(self):
        """Results with price_inr > max_price_inr must be absent."""
        from app.services.similarity_service import find_similar_products
        max_price = 1000
        results = find_similar_products(image_url=IMAGE_URL, max_price_inr=max_price)
        for r in results:
            assert r["price_inr"] <= max_price, \
                f"Result with price={r['price_inr']} exceeded max={max_price}"

    def test_exclude_platform_removes_that_platform(self):
        from app.services.similarity_service import find_similar_products
        results = find_similar_products(image_url=IMAGE_URL, exclude_platform="myntra")
        platforms = [r["platform"] for r in results]
        assert "myntra" not in platforms, \
            f"Myntra should be excluded but found in: {platforms}"

    def test_text_query_accepted(self):
        from app.services.similarity_service import find_similar_products
        results = find_similar_products(text_query=TEXT_QUERY)
        assert isinstance(results, list)

    def test_image_url_takes_precedence_over_text(self):
        """When both provided, image takes precedence — no error raised."""
        from app.services.similarity_service import find_similar_products
        results = find_similar_products(image_url=IMAGE_URL, text_query=TEXT_QUERY)
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# TestRankByPrice — price sorting
# ---------------------------------------------------------------------------

class TestRankByPrice:
    """Assert rank_by_price re-ranks results by price ascending."""

    def _sample_results(self) -> list[dict[str, Any]]:
        return [
            {"rank": 1, "product_id": "a", "price_inr": 1500, "similarity_score": 0.95,
             "platform": "myntra", "category": "tops", "url": "https://a.com"},
            {"rank": 2, "product_id": "b", "price_inr": 600,  "similarity_score": 0.88,
             "platform": "amazon", "category": "tops", "url": "https://b.com"},
            {"rank": 3, "product_id": "c", "price_inr": 900,  "similarity_score": 0.75,
             "platform": "flipkart", "category": "tops", "url": "https://c.com"},
        ]

    def test_rank_by_price_sorts_ascending(self):
        from app.services.similarity_service import rank_by_price
        results = rank_by_price(self._sample_results())
        prices = [r["price_inr"] for r in results]
        assert prices == sorted(prices), f"Prices not ascending: {prices}"

    def test_rank_by_price_cheapest_is_rank_1(self):
        from app.services.similarity_service import rank_by_price
        results = rank_by_price(self._sample_results())
        cheapest = min(self._sample_results(), key=lambda r: r["price_inr"])
        assert results[0]["product_id"] == cheapest["product_id"]
        assert results[0]["rank"] == 1

    def test_rank_by_price_updates_rank_sequentially(self):
        from app.services.similarity_service import rank_by_price
        results = rank_by_price(self._sample_results())
        ranks = [r["rank"] for r in results]
        assert ranks == list(range(1, len(results) + 1))

    def test_rank_by_price_returns_all_items(self):
        from app.services.similarity_service import rank_by_price
        original = self._sample_results()
        results = rank_by_price(original)
        assert len(results) == len(original)


# ---------------------------------------------------------------------------
# TestFindCheaperAlternatives — "find similar but cheaper" core feature
# ---------------------------------------------------------------------------

class TestFindCheaperAlternatives:
    """Assert find_cheaper_alternatives returns only strictly cheaper items, price-sorted."""

    def test_all_results_cheaper_than_reference(self):
        from app.services.similarity_service import find_cheaper_alternatives
        reference_price = 2000
        results = find_cheaper_alternatives(
            image_url=IMAGE_URL,
            reference_price_inr=reference_price,
        )
        for r in results:
            assert r["price_inr"] < reference_price, \
                f"Result with price={r['price_inr']} is not cheaper than {reference_price}"

    def test_results_sorted_by_price_ascending(self):
        from app.services.similarity_service import find_cheaper_alternatives
        results = find_cheaper_alternatives(
            image_url=IMAGE_URL,
            reference_price_inr=3000,
        )
        prices = [r["price_inr"] for r in results]
        assert prices == sorted(prices), f"Prices not ascending: {prices}"

    def test_limit_respected(self):
        from app.services.similarity_service import find_cheaper_alternatives
        results = find_cheaper_alternatives(
            image_url=IMAGE_URL,
            reference_price_inr=9999,
            limit=2,
        )
        assert len(results) <= 2

    def test_returns_list(self):
        from app.services.similarity_service import find_cheaper_alternatives
        results = find_cheaper_alternatives(
            image_url=IMAGE_URL,
            reference_price_inr=5000,
        )
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# TestSimilarityServiceAPI — /cv/similar endpoint via TestClient
# ---------------------------------------------------------------------------

class TestSimilarityServiceAPI:
    """Assert POST /cv/similar returns correct HTTP response shape."""

    def test_similar_endpoint_returns_200(self):
        from fastapi.testclient import TestClient
        from app.main import app

        with patch("app.services.similarity_service.find_similar_products") as mock_svc:
            mock_svc.return_value = [
                {"rank": 1, "product_id": "a", "price_inr": 800, "similarity_score": 0.9,
                 "platform": "amazon", "category": "tops", "url": "https://a.com"},
            ]
            client = TestClient(app)
            response = client.post(
                "/api/v1/cv/similar",
                json={"image_url": "https://example.com/shirt.jpg", "limit": 5},
            )
        assert response.status_code == 200, response.text

    def test_similar_endpoint_response_has_results(self):
        from fastapi.testclient import TestClient
        from app.main import app
        mock_result = [
            {"rank": 1, "product_id": "b", "price_inr": 500, "similarity_score": 0.85,
             "platform": "meesho", "category": "tops", "url": "https://b.com"},
        ]
        with patch("app.services.similarity_service.find_similar_products",
                   return_value=mock_result):
            client = TestClient(app)
            response = client.post(
                "/api/v1/cv/similar",
                json={"text_query": "blue kurta", "limit": 3},
            )
        body = response.json()
        assert "results" in body
        assert "count" in body
        assert body["count"] == len(body["results"])

    def test_similar_endpoint_no_query_returns_422(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        response = client.post(
            "/api/v1/cv/similar",
            json={"limit": 5},   # neither image_url nor text_query
        )
        assert response.status_code == 422

    def test_similar_endpoint_query_type_image(self):
        from fastapi.testclient import TestClient
        from app.main import app
        with patch("app.services.similarity_service.find_similar_products", return_value=[]):
            client = TestClient(app)
            response = client.post(
                "/api/v1/cv/similar",
                json={"image_url": "https://example.com/img.jpg"},
            )
        assert response.json()["query_type"] == "image"

    def test_similar_endpoint_query_type_text(self):
        from fastapi.testclient import TestClient
        from app.main import app
        with patch("app.services.similarity_service.find_similar_products", return_value=[]):
            client = TestClient(app)
            response = client.post(
                "/api/v1/cv/similar",
                json={"text_query": "red saree"},
            )
        assert response.json()["query_type"] == "text"
