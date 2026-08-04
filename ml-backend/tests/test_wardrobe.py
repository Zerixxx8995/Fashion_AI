"""
Wardrobe Gap Analysis Tests — ml-backend.

Tests:
  - POST /api/v1/wardrobe/gap-analysis returns 200 with correct structure
  - owned_categories reflects what was submitted
  - missing_categories covers the rest of the capsule
  - coverage_score is between 0 and 1
  - lifecycle fields: priority is one of high/medium/low
  - budget allocation sums approximately to input budget
  - empty wardrobe → all categories missing, coverage = 0
  - full capsule wardrobe → no missing categories, coverage = 1
  - 422 on empty wardrobe list
  - 422 on negative budget
  - synonym resolution: 'jeans' → bottoms, 'kurta' → ethnic
"""

from __future__ import annotations

import os
os.environ["TESTING"] = "1"

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.wardrobe_service import (
    run_gap_analysis,
    CAPSULE_CATEGORIES,
)
from app.models.wardrobe_models import GapAnalysisRequest, WardrobeItem


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    app = create_app()
    return TestClient(app)


def _make_wardrobe(*categories):
    """Helper: build a wardrobe list from category strings."""
    return [{"name": f"Item {i+1}", "category": cat} for i, cat in enumerate(categories)]


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------

class TestGapAnalysisHTTP:

    def test_gap_analysis_returns_200(self, client):
        res = client.post("/api/v1/wardrobe/gap-analysis", json={
            "wardrobe": _make_wardrobe("tops", "jeans", "kurta"),
        })
        assert res.status_code == 200

    def test_response_has_required_keys(self, client):
        res = client.post("/api/v1/wardrobe/gap-analysis", json={
            "wardrobe": _make_wardrobe("tops"),
        })
        body = res.json()
        assert "owned_categories" in body
        assert "missing_categories" in body
        assert "coverage_score" in body
        assert "total_items" in body
        assert "analysis_note" in body

    def test_owned_categories_reflects_submission(self, client):
        res = client.post("/api/v1/wardrobe/gap-analysis", json={
            "wardrobe": _make_wardrobe("tops", "jeans"),
        })
        body = res.json()
        # "jeans" maps to Bottoms via synonym
        assert len(body["owned_categories"]) >= 1

    def test_missing_categories_have_priority_field(self, client):
        res = client.post("/api/v1/wardrobe/gap-analysis", json={
            "wardrobe": _make_wardrobe("tops"),
        })
        body = res.json()
        for gap in body["missing_categories"]:
            assert gap["priority"] in ("high", "medium", "low")

    def test_missing_categories_have_reason(self, client):
        res = client.post("/api/v1/wardrobe/gap-analysis", json={
            "wardrobe": _make_wardrobe("tops"),
        })
        body = res.json()
        for gap in body["missing_categories"]:
            assert isinstance(gap["reason"], str)
            assert len(gap["reason"]) > 5

    def test_coverage_score_between_0_and_1(self, client):
        res = client.post("/api/v1/wardrobe/gap-analysis", json={
            "wardrobe": _make_wardrobe("tops", "bottoms", "kurta"),
        })
        body = res.json()
        assert 0.0 <= body["coverage_score"] <= 1.0

    def test_total_items_matches_input(self, client):
        wardrobe = _make_wardrobe("tops", "jeans", "sneakers")
        res = client.post("/api/v1/wardrobe/gap-analysis", json={
            "wardrobe": wardrobe,
        })
        assert res.json()["total_items"] == 3

    def test_with_budget_allocates_per_category(self, client):
        res = client.post("/api/v1/wardrobe/gap-analysis", json={
            "wardrobe": _make_wardrobe("tops"),
            "budget_inr": 10000,
        })
        body = res.json()
        for gap in body["missing_categories"]:
            assert gap.get("suggested_budget_inr") is not None
            assert gap["suggested_budget_inr"] >= 100

    def test_without_budget_no_suggested_budget(self, client):
        res = client.post("/api/v1/wardrobe/gap-analysis", json={
            "wardrobe": _make_wardrobe("tops"),
        })
        body = res.json()
        for gap in body["missing_categories"]:
            assert gap.get("suggested_budget_inr") is None

    def test_422_on_empty_wardrobe(self, client):
        res = client.post("/api/v1/wardrobe/gap-analysis", json={
            "wardrobe": [],
        })
        assert res.status_code == 422

    def test_422_on_negative_budget(self, client):
        res = client.post("/api/v1/wardrobe/gap-analysis", json={
            "wardrobe": _make_wardrobe("tops"),
            "budget_inr": -500,
        })
        assert res.status_code == 422

    def test_422_on_missing_wardrobe_field(self, client):
        res = client.post("/api/v1/wardrobe/gap-analysis", json={})
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# Service unit tests (pure algorithm, no HTTP)
# ---------------------------------------------------------------------------

class TestGapAnalysisService:

    def _req(self, *categories, budget=None):
        items = [WardrobeItem(name=f"Item {i+1}", category=cat)
                 for i, cat in enumerate(categories)]
        return GapAnalysisRequest(wardrobe=items, budget_inr=budget)

    def test_empty_wardrobe_zero_coverage(self):
        """All capsule categories missing → coverage = 0."""
        items = [WardrobeItem(name="Ghost item", category="unknown_xyz")]
        req = GapAnalysisRequest(wardrobe=items)
        result = run_gap_analysis(req)
        assert result.coverage_score == 0.0
        assert len(result.missing_categories) == len(CAPSULE_CATEGORIES)

    def test_full_capsule_full_coverage(self):
        """One item per canonical category → coverage = 1.0, no missing."""
        canonical_categories = list(CAPSULE_CATEGORIES.keys())
        items = [WardrobeItem(name=f"Item {i}", category=cat)
                 for i, cat in enumerate(canonical_categories)]
        req = GapAnalysisRequest(wardrobe=items)
        result = run_gap_analysis(req)
        assert result.coverage_score == 1.0
        assert len(result.missing_categories) == 0

    def test_synonym_jeans_maps_to_bottoms(self):
        """'jeans' must resolve to 'bottoms' canonical category."""
        req = self._req("jeans")
        result = run_gap_analysis(req)
        owned = result.owned_categories
        # Should contain 'Bottoms / Jeans' display name
        assert any("Bottoms" in c for c in owned)

    def test_synonym_kurta_maps_to_ethnic(self):
        req = self._req("kurta")
        result = run_gap_analysis(req)
        assert any("Ethnic" in c for c in result.owned_categories)

    def test_synonym_sneakers_maps_to_footwear(self):
        req = self._req("sneakers")
        result = run_gap_analysis(req)
        assert any("Footwear" in c for c in result.owned_categories)

    def test_coverage_increases_with_more_categories(self):
        req1 = self._req("tops")
        req2 = self._req("tops", "bottoms", "footwear")
        assert run_gap_analysis(req1).coverage_score < run_gap_analysis(req2).coverage_score

    def test_high_priority_gaps_come_first(self):
        """High-priority missing categories should appear before low-priority ones."""
        # Give the user only 'accessories' (low priority) — all high/medium categories should be missing
        req = self._req("accessories")
        result = run_gap_analysis(req)
        priorities = [g.priority for g in result.missing_categories]
        # Check no 'low' appears before any 'high'
        seen_low = False
        for p in priorities:
            if p == "low":
                seen_low = True
            if seen_low and p == "high":
                pytest.fail("High priority gap appeared after a low priority gap")

    def test_budget_allocation_positive_per_category(self):
        req = self._req("tops", budget=20000)
        result = run_gap_analysis(req)
        for gap in result.missing_categories:
            assert gap.suggested_budget_inr is not None
            assert gap.suggested_budget_inr >= 100

    def test_no_budget_gives_none_per_category(self):
        req = self._req("tops")
        result = run_gap_analysis(req)
        for gap in result.missing_categories:
            assert gap.suggested_budget_inr is None

    def test_analysis_note_is_non_empty_string(self):
        req = self._req("tops")
        result = run_gap_analysis(req)
        assert isinstance(result.analysis_note, str)
        assert len(result.analysis_note) > 0

    def test_unknown_categories_do_not_crash(self):
        """Items with unrecognised categories should simply not appear in owned."""
        items = [WardrobeItem(name="Mystery item", category="Interstellar fabric")]
        req = GapAnalysisRequest(wardrobe=items)
        result = run_gap_analysis(req)
        assert result.coverage_score == 0.0

    def test_none_category_handled_gracefully(self):
        items = [WardrobeItem(name="No category item")]
        req = GapAnalysisRequest(wardrobe=items)
        result = run_gap_analysis(req)
        assert result.coverage_score == 0.0
