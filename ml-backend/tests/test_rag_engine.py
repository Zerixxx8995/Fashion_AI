"""
Tests for the RAG Engine — ml-backend/tests/test_rag_engine.py

Tests:
  1. assert explanation is non-empty string
  2. assert explanation length is between 80 and 350 characters
  3. assert cached explanation returns from Redis without calling LLM
  4. assert prompt contains retrieved product names (grounding check)
  5. assert GET /explanations/trend/{trend_id} returns correct response schema
  6. assert GET /explanations/recommendation/{product_id} returns correct response schema
  7. assert unauthenticated request returns 401
  8. assert invalid id returns 404

All tests use mocking — no real LLM calls, no real Redis, no real database.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Set TESTING env so auth middleware is bypassed
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_rag.db")
os.environ.setdefault("GOOGLE_API_KEY", "test-key-for-unit-tests")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_EXPLANATION = (
    "Oversized blazers are peaking right now driven by office-to-casual crossover "
    "dressing, especially popular in metro cities."
)

assert 80 <= len(FAKE_EXPLANATION) <= 350, "FAKE_EXPLANATION must be 80-350 chars for test validity"


def _make_trend(trend_id: str | None = None) -> MagicMock:
    """Return a mock TrendItem ORM object."""
    t = MagicMock()
    t.id = trend_id or str(uuid.uuid4())
    t.name = "Oversized Blazers"
    t.category = "tops"
    t.lifecycle_stage = "peaking"
    t.origin = "Myntra Bestsellers"
    t.signal_score = 8.7
    return t


def _make_product(product_id: str | None = None) -> MagicMock:
    """Return a mock Product ORM object."""
    p = MagicMock()
    p.id = product_id or str(uuid.uuid4())
    p.name = "H&M Oversized Blazer"
    p.brand = "H&M"
    p.price_inr = 2999
    p.platform = "myntra"
    p.category = "tops"
    return p


def _make_user(user_id: str | None = None) -> MagicMock:
    """Return a mock User ORM object."""
    u = MagicMock()
    u.id = user_id or str(uuid.uuid4())
    u.clerk_id = "clerk_test_123"
    u.body_type = "hourglass"
    u.style_preferences = json.dumps(["casual", "office"])
    return u


def _make_wardrobe_item() -> MagicMock:
    """Return a mock WardrobeItem ORM object."""
    w = MagicMock()
    w.id = str(uuid.uuid4())
    w.name = "White Oxford Shirt"
    w.category = "tops"
    w.color = "white"
    return w


# ---------------------------------------------------------------------------
# Test 1 — explanation is a non-empty string
# ---------------------------------------------------------------------------

def test_explanation_is_non_empty_string():
    """RAG engine must return a non-empty string."""
    from app.core.rag_engine import generate_trend_explanation

    with patch("app.core.rag_engine.get_llm_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.generate.return_value = FAKE_EXPLANATION
        mock_get_client.return_value = mock_client

        result = generate_trend_explanation(
            trend_name="Oversized Blazers",
            category="tops",
            lifecycle_stage="peaking",
            origin="Myntra Bestsellers",
            signal_score=8.7,
            products=[{"name": "H&M Blazer", "brand": "H&M", "price_inr": 2999, "platform": "myntra"}],
            reviews=[{"reviewer_text": "Love the fit!", "product_name": "H&M Blazer"}],
        )

    assert isinstance(result, str), "Explanation must be a string"
    assert len(result) > 0, "Explanation must be non-empty"


# ---------------------------------------------------------------------------
# Test 2 — explanation length between 80 and 350 characters
# ---------------------------------------------------------------------------

def test_explanation_length_within_bounds():
    """Explanation must be between 80 and 350 characters (spec NF11)."""
    from app.core.rag_engine import generate_trend_explanation

    with patch("app.core.rag_engine.get_llm_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.generate.return_value = FAKE_EXPLANATION
        mock_get_client.return_value = mock_client

        result = generate_trend_explanation(
            trend_name="Oversized Blazers",
            category="tops",
            lifecycle_stage="peaking",
            origin="Myntra Bestsellers",
            signal_score=8.7,
            products=[],
            reviews=[],
        )

    assert 80 <= len(result) <= 350, (
        f"Explanation length must be 80–350 chars, got {len(result)}: {result!r}"
    )


# ---------------------------------------------------------------------------
# Test 3 — cached explanation returns from Redis without calling LLM
# ---------------------------------------------------------------------------

def test_cache_hit_skips_llm():
    """If Redis has a cached explanation, the LLM must NOT be called."""
    from app.services.explanation_service import get_trend_explanation

    trend_id = str(uuid.uuid4())
    cached_payload = json.dumps({
        "trend_id": trend_id,
        "trend_name": "Oversized Blazers",
        "explanation": FAKE_EXPLANATION,
        "cached": False,
        "generated_at": "2026-01-01T00:00:00+00:00",
    })

    mock_db = MagicMock()
    mock_redis = MagicMock()
    mock_redis.get.return_value = cached_payload

    with (
        patch("app.services.explanation_service._get_redis", return_value=mock_redis),
        patch("app.core.rag_engine.get_llm_client") as mock_llm,
    ):
        result = get_trend_explanation(mock_db, trend_id=trend_id)

    # LLM must not have been called
    mock_llm.assert_not_called()
    assert result["cached"] is True, "Cache hit must set cached=True"
    assert result["explanation"] == FAKE_EXPLANATION


# ---------------------------------------------------------------------------
# Test 4 — prompt contains retrieved product names (grounding check)
# ---------------------------------------------------------------------------

def test_prompt_contains_product_names():
    """The prompt passed to the LLM must include retrieved product names."""
    from app.core.rag_engine import generate_trend_explanation

    captured_prompts: list[str] = []

    def capture_generate(prompt: str) -> str:
        captured_prompts.append(prompt)
        return FAKE_EXPLANATION

    with patch("app.core.rag_engine.get_llm_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.generate.side_effect = capture_generate
        mock_get_client.return_value = mock_client

        generate_trend_explanation(
            trend_name="Cargo Denim Jeans",
            category="jeans",
            lifecycle_stage="peaking",
            origin="Ajio Trends",
            signal_score=9.0,
            products=[
                {"name": "Roadster Cargo Jeans", "brand": "Roadster", "price_inr": 1499, "platform": "myntra"},
                {"name": "H&M Cargo Pants", "brand": "H&M", "price_inr": 1999, "platform": "amazon"},
            ],
            reviews=[],
        )

    assert len(captured_prompts) == 1
    prompt = captured_prompts[0]
    assert "Roadster Cargo Jeans" in prompt, "Prompt must contain first product name"
    assert "H&M Cargo Pants" in prompt, "Prompt must contain second product name"


# ---------------------------------------------------------------------------
# Test 5 — GET /explanations/trend/{trend_id} returns correct response schema
# ---------------------------------------------------------------------------

def test_trend_explanation_endpoint_schema():
    """GET /explanations/trend/{trend_id} must return the correct response schema."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db.database import get_db

    trend_id = str(uuid.uuid4())
    expected_response = {
        "trend_id": trend_id,
        "trend_name": "Oversized Blazers",
        "explanation": FAKE_EXPLANATION,
        "cached": False,
        "generated_at": "2026-01-01T00:00:00+00:00",
    }

    # Use FastAPI dependency_overrides instead of patching get_db directly
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with patch(
            "app.services.explanation_service.get_trend_explanation",
            return_value=expected_response
        ):
            client = TestClient(app)
            response = client.get(f"/api/v1/explanations/trend/{trend_id}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert "trend_id" in data
    assert "trend_name" in data
    assert "explanation" in data
    assert "cached" in data
    assert "generated_at" in data


# ---------------------------------------------------------------------------
# Test 6 — GET /explanations/recommendation/{product_id} returns correct schema
# ---------------------------------------------------------------------------

def test_recommendation_explanation_endpoint_schema():
    """GET /explanations/recommendation/{product_id} must return the correct schema."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db.database import get_db

    product_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    expected_response = {
        "product_id": product_id,
        "product_name": "Slim Fit Chinos",
        "explanation": FAKE_EXPLANATION,
        "cached": False,
        "generated_at": "2026-01-01T00:00:00+00:00",
    }

    # Use FastAPI dependency_overrides for DB injection
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with patch(
            "app.services.explanation_service.get_recommendation_explanation",
            return_value=expected_response
        ):
            client = TestClient(app)
            response = client.get(
                f"/api/v1/explanations/recommendation/{product_id}",
                params={"user_id": user_id},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert "product_id" in data
    assert "product_name" in data
    assert "explanation" in data
    assert "cached" in data
    assert "generated_at" in data


# ---------------------------------------------------------------------------
# Test 7 — unauthenticated request returns 401
# ---------------------------------------------------------------------------

def test_unauthenticated_request_returns_401():
    """
    When TESTING env is unset, ClerkAuthMiddleware is active.
    A request without a Bearer token must return 401.
    """
    # Temporarily remove TESTING flag to enable auth middleware
    original = os.environ.pop("TESTING", None)
    try:
        # Re-import with auth enabled
        import importlib
        import app.main as main_module
        importlib.reload(main_module)
        fresh_app = main_module.create_app()

        from fastapi.testclient import TestClient
        client = TestClient(fresh_app, raise_server_exceptions=False)

        # Protected route with no Authorization header must return 401
        response = client.post("/api/v1/budget/optimize", json={})
        assert response.status_code == 401, (
            f"Expected 401 for unauthenticated request to protected route, got {response.status_code}"
        )
    finally:
        # Restore TESTING flag
        if original is not None:
            os.environ["TESTING"] = original
        else:
            os.environ["TESTING"] = "1"


# ---------------------------------------------------------------------------
# Test 8 — invalid trend_id returns 404
# ---------------------------------------------------------------------------

def test_invalid_trend_id_returns_404():
    """A non-existent trend_id must return 404."""
    import importlib
    from fastapi.testclient import TestClient

    nonexistent_id = str(uuid.uuid4())

    # Ensure TESTING=1 so auth middleware is not added, then create a fresh app
    os.environ["TESTING"] = "1"

    import app.main as main_module
    importlib.reload(main_module)
    fresh_app = main_module.create_app()

    from app.db.database import get_db
    mock_db = MagicMock()
    fresh_app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with patch(
            "app.services.explanation_service.get_trend_explanation",
            side_effect=KeyError(f"TrendItem with id={nonexistent_id!r} not found")
        ):
            client = TestClient(fresh_app)
            response = client.get(f"/api/v1/explanations/trend/{nonexistent_id}")
    finally:
        fresh_app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404, (
        f"Expected 404 for invalid trend_id, got {response.status_code}: {response.text}"
    )


# ---------------------------------------------------------------------------
# Test 9 — LLM client initialises without error (with mocked API key)
# ---------------------------------------------------------------------------

def test_llm_client_initialises():
    """LLMClient must initialise without raising when GOOGLE_API_KEY is set."""
    os.environ["GOOGLE_API_KEY"] = "test-key-mock"

    with patch("langchain_google_genai.ChatGoogleGenerativeAI") as mock_llm_class:
        mock_llm_class.return_value = MagicMock()

        # Force re-init by resetting singleton
        import app.integrations.llm_client as llm_mod
        llm_mod._llm_client = None

        from app.integrations.llm_client import get_llm_client
        client = get_llm_client()
        assert client is not None

        # Reset for other tests
        llm_mod._llm_client = None


# ---------------------------------------------------------------------------
# Test 10 — generate() returns a string
# ---------------------------------------------------------------------------

def test_llm_client_generate_returns_string():
    """LLMClient.generate() must return a plain string."""
    from app.integrations.llm_client import LLMClient

    with patch("langchain_google_genai.ChatGoogleGenerativeAI") as mock_llm_class:
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.content = FAKE_EXPLANATION
        mock_instance.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_instance

        client = LLMClient()
        result = client.generate("Test prompt for fashion trend analysis.")

    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# Test 11 — Redis TTL is set correctly for trend explanations
# ---------------------------------------------------------------------------

def test_trend_cache_ttl_is_24_hours():
    """Trend explanation must be cached with TTL of 86400 seconds (24h)."""
    from app.services.explanation_service import get_trend_explanation, _TREND_TTL_SECONDS

    assert _TREND_TTL_SECONDS == 86400, (
        f"Trend TTL must be 86400s (24h), got {_TREND_TTL_SECONDS}"
    )

    trend_id = str(uuid.uuid4())
    mock_db = MagicMock()
    mock_redis = MagicMock()
    mock_redis.get.return_value = None  # cache miss

    trend = _make_trend(trend_id)
    mock_db.scalar.return_value = trend
    mock_db.scalars.return_value = MagicMock(all=lambda: [])

    with (
        patch("app.services.explanation_service._get_redis", return_value=mock_redis),
        patch("app.core.rag_engine.generate_trend_explanation", return_value=FAKE_EXPLANATION),
    ):
        get_trend_explanation(mock_db, trend_id=trend_id)

    # Assert setex was called with the 24h TTL
    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    assert call_args[0][1] == 86400, (
        f"Cache TTL must be 86400 (24h), got {call_args[0][1]}"
    )


# ---------------------------------------------------------------------------
# Test 12 — Redis TTL is set correctly for recommendation explanations
# ---------------------------------------------------------------------------

def test_recommendation_cache_ttl_is_6_hours():
    """Recommendation explanation must be cached with TTL of 21600 seconds (6h)."""
    from app.services.explanation_service import _REC_TTL_SECONDS

    assert _REC_TTL_SECONDS == 21600, (
        f"Recommendation TTL must be 21600s (6h), got {_REC_TTL_SECONDS}"
    )
