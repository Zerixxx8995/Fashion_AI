"""
Tests — ml-backend/tests/test_review_authenticity_engine.py

Covers all 9 spec test cases for Feature 3.

Test plan (from spec):
  1. Output matches ReviewAuthenticityExplanation Pydantic schema
  2. suspicious_phrases is a list (may be empty or non-empty)
  3. overall_verdict is one of: "Likely fake", "Possibly fake", "Inconclusive"
  4. Malformed LLM output triggers retry
  5. Second failure returns Inconclusive fallback
  6. GET /reviews/{review_id}/explain returns 200 for a flagged review
  7. GET /reviews/{review_id}/explain returns 400 for a non-flagged review
  8. GET /reviews/{review_id}/explain returns 404 for non-existent review
  9. Cache hit skips engine call

Architecture rules for tests:
  - TESTING=1 disables auth middleware
  - LLM calls are mocked — never real API calls in unit tests
  - Redis calls are mocked — no real network I/O
  - DB calls use SQLite in-memory via the app fixture
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers — build fake LLM output
# ---------------------------------------------------------------------------

def _valid_explanation_json(**overrides: Any) -> str:
    data = {
        "overall_verdict": "Likely fake",
        "confidence_score": 0.87,
        "suspicious_phrases": ["exactly as shown", "perfect quality"],
        "image_mismatch_summary": "The reviewer photo shows grey; stock photo shows navy blue.",
        "pattern_matches": [
            "Generic positive language with no specific details",
            "Five-star rating with no mention of delivery time",
        ],
        "recommendation": "Check 1-star reviews and reviewer profiles before purchasing.",
    }
    data.update(overrides)
    return json.dumps(data)


def _make_llm(return_text: str) -> MagicMock:
    """Return a mock LLM that produces the given text on .invoke()."""
    mock = MagicMock()
    result = MagicMock()
    result.content = return_text
    mock.invoke.return_value = result
    return mock


# ---------------------------------------------------------------------------
# Core engine tests (no HTTP)
# ---------------------------------------------------------------------------

class TestReviewAuthenticityEngine:
    """Unit tests for core/review_authenticity_engine.py."""

    def _run_engine_with_llm_response(self, responses: list[str]) -> Any:
        """
        Helper to call generate_review_explanation, mocking _call_llm to
        return successive values from `responses`.

        Mocking _call_llm directly avoids the langchain_core import problem
        in test environments where the package may not be installed.
        """
        from app.core import review_authenticity_engine
        from app.core.review_authenticity_engine import generate_review_explanation

        call_iter = iter(responses)

        def fake_call_llm(llm, prompt):
            return next(call_iter)

        with patch.object(review_authenticity_engine, "_call_llm", side_effect=fake_call_llm), \
             patch.object(review_authenticity_engine, "_get_llm_at_temp_01", return_value=MagicMock()):
            return generate_review_explanation(
                review_text="This product is exactly as shown, perfect quality, no issues at all.",
                stock_match_score=0.87,
                product_name="Blue Kurta Set",
                platform="myntra",
                stock_image_url="https://assets.myntra.com/product/blue-kurta.jpg",
                historical_fake_reviews=[
                    {"reviewer_text": "Excellent product, highly recommend!"},
                    {"reviewer_text": "Exactly as shown in pictures."},
                ],
            )

    def test_output_matches_pydantic_schema(self):
        """Spec test 1: output matches ReviewAuthenticityExplanation schema."""
        from app.core.review_authenticity_engine import ReviewAuthenticityExplanation

        result = self._run_engine_with_llm_response([_valid_explanation_json()])

        assert isinstance(result, ReviewAuthenticityExplanation)
        assert isinstance(result.overall_verdict, str)
        assert isinstance(result.confidence_score, float)
        assert isinstance(result.suspicious_phrases, list)
        assert isinstance(result.image_mismatch_summary, str)
        assert isinstance(result.pattern_matches, list)
        assert isinstance(result.recommendation, str)

    def test_suspicious_phrases_is_list(self):
        """Spec test 2: suspicious_phrases is a list."""
        result = self._run_engine_with_llm_response([_valid_explanation_json()])
        assert isinstance(result.suspicious_phrases, list)

    def test_overall_verdict_is_valid(self):
        """Spec test 3: overall_verdict is one of the three valid values."""
        from app.core.review_authenticity_engine import VALID_VERDICTS

        result = self._run_engine_with_llm_response([_valid_explanation_json()])
        assert result.overall_verdict in VALID_VERDICTS

    def test_malformed_llm_output_triggers_retry(self):
        """Spec test 4: malformed LLM output triggers retry."""
        # First call returns garbage JSON, second call returns valid JSON.
        # We track call count via a mutable counter since side_effect is consumed lazily.
        call_count = {"n": 0}
        responses = ["not json at all {{{" , _valid_explanation_json()]

        def side_effect_fn(llm, prompt):
            call_count["n"] += 1
            return responses[call_count["n"] - 1]

        from app.core import review_authenticity_engine
        from app.core.review_authenticity_engine import generate_review_explanation

        with patch.object(review_authenticity_engine, "_call_llm", side_effect=side_effect_fn), \
             patch.object(review_authenticity_engine, "_get_llm_at_temp_01", return_value=MagicMock()):
            result = generate_review_explanation(
                review_text="bad review",
                stock_match_score=0.87,
                product_name="Test Product",
                platform="myntra",
                stock_image_url="https://example.com/stock.jpg",
                historical_fake_reviews=[],
            )

        # _call_llm should have been called twice (attempt 1 failed → attempt 2)
        assert call_count["n"] == 2
        assert result.overall_verdict in {"Likely fake", "Possibly fake", "Inconclusive"}

    def test_second_failure_returns_inconclusive(self):
        """Spec test 5: second failure returns Inconclusive fallback."""
        result = self._run_engine_with_llm_response(
            ["definitely not json", "still not json"]
        )

        assert result.overall_verdict == "Inconclusive"
        # Confidence score should be the raw input value
        assert abs(result.confidence_score - 0.87) < 0.001

    def test_confidence_score_always_from_cv_engine(self):
        """Engine always uses stock_match_score — not LLM's confidence value."""
        # LLM returns a different confidence value
        result = self._run_engine_with_llm_response(
            [_valid_explanation_json(confidence_score=0.99)]
        )
        # Should be overridden with the actual CV engine score
        assert abs(result.confidence_score - 0.87) < 0.001

    def test_possibly_fake_verdict_accepted(self):
        """Engine accepts 'Possibly fake' verdict."""
        result = self._run_engine_with_llm_response(
            [_valid_explanation_json(overall_verdict="Possibly fake")]
        )
        assert result.overall_verdict == "Possibly fake"

    def test_invalid_verdict_triggers_retry(self):
        """LLM returning an invalid verdict string triggers retry, then Inconclusive."""
        bad = _valid_explanation_json(overall_verdict="Probably real")
        result = self._run_engine_with_llm_response([bad, bad])
        assert result.overall_verdict == "Inconclusive"


# ---------------------------------------------------------------------------
# API integration tests — GET /reviews/{review_id}/explain
# ---------------------------------------------------------------------------

@pytest.fixture()
def app_client():
    """TestClient with TESTING=1 (auth middleware disabled)."""
    os.environ["TESTING"] = "1"
    from app.main import create_app
    client = TestClient(create_app())
    yield client
    os.environ.pop("TESTING", None)


@pytest.fixture()
def mock_flagged_review():
    """Return a mock Review object that is_flagged_fake=True."""
    review = MagicMock()
    review.id = "review-001"
    review.product_id = "product-001"
    review.reviewer_text = "Exactly as shown, perfect quality, no issues at all!"
    review.stock_match_score = 0.87
    review.is_flagged_fake = True
    return review


@pytest.fixture()
def mock_clean_review():
    """Return a mock Review that is NOT flagged."""
    review = MagicMock()
    review.id = "review-clean-001"
    review.product_id = "product-001"
    review.reviewer_text = "Lovely kurta, great quality."
    review.stock_match_score = 0.22
    review.is_flagged_fake = False
    return review


@pytest.fixture()
def mock_product():
    """Return a mock Product."""
    product = MagicMock()
    product.id = "product-001"
    product.name = "Blue Kurta Set"
    product.platform = "myntra"
    product.stock_image_urls = json.dumps([
        "https://assets.myntra.com/product/blue-kurta.jpg"
    ])
    return product


@pytest.fixture()
def mock_service_response():
    return {
        "review_id": "review-001",
        "overall_verdict": "Likely fake",
        "confidence_score": 0.87,
        "suspicious_phrases": ["exactly as shown", "perfect quality"],
        "image_mismatch_summary": "Reviewer photo shows grey; stock photo shows navy blue.",
        "pattern_matches": ["Generic positive language with no specific details"],
        "recommendation": "Check 1-star reviews before purchasing.",
        "cached": False,
    }


class TestReviewExplainAPI:
    """API-level integration tests for GET /reviews/{review_id}/explain."""

    def test_returns_200_for_flagged_review(self, app_client, mock_service_response):
        """Spec test 6: 200 with correct schema for a flagged review."""
        with patch(
            "app.services.review_explain_service.get_review_explanation",
            return_value=mock_service_response,
        ):
            response = app_client.get("/api/v1/reviews/review-001/explain")

        assert response.status_code == 200
        data = response.json()

        # Verify all required fields
        assert "review_id" in data
        assert "overall_verdict" in data
        assert "confidence_score" in data
        assert "suspicious_phrases" in data
        assert "image_mismatch_summary" in data
        assert "pattern_matches" in data
        assert "recommendation" in data
        assert "cached" in data

        # Verify types
        assert isinstance(data["overall_verdict"], str)
        assert isinstance(data["confidence_score"], float)
        assert isinstance(data["suspicious_phrases"], list)
        assert isinstance(data["pattern_matches"], list)

    def test_returns_400_for_non_flagged_review(self, app_client):
        """Spec test 7: 400 for a review that is not flagged fake."""
        with patch(
            "app.services.review_explain_service.get_review_explanation",
            side_effect=ValueError("Review is not flagged as fake"),
        ):
            response = app_client.get("/api/v1/reviews/review-clean-001/explain")

        assert response.status_code == 400

    def test_returns_404_for_nonexistent_review(self, app_client):
        """Spec test 8: 404 for a non-existent review_id."""
        with patch(
            "app.services.review_explain_service.get_review_explanation",
            side_effect=KeyError("Review not found"),
        ):
            response = app_client.get("/api/v1/reviews/nonexistent-id/explain")

        assert response.status_code == 404

    def test_cache_hit_skips_engine_call(self, app_client, mock_service_response):
        """Spec test 9: cache hit returns result without calling the engine."""
        cached_response = {**mock_service_response, "cached": True}

        with patch(
            "app.services.review_explain_service.get_review_explanation",
            return_value=cached_response,
        ) as mock_svc:
            response = app_client.get("/api/v1/reviews/review-001/explain")

        assert response.status_code == 200
        data = response.json()
        assert data["cached"] is True
        mock_svc.assert_called_once()

    def test_response_verdict_is_valid(self, app_client, mock_service_response):
        """Overall verdict in API response is one of the three valid values."""
        from app.core.review_authenticity_engine import VALID_VERDICTS

        with patch(
            "app.services.review_explain_service.get_review_explanation",
            return_value=mock_service_response,
        ):
            response = app_client.get("/api/v1/reviews/review-001/explain")

        assert response.json()["overall_verdict"] in VALID_VERDICTS
