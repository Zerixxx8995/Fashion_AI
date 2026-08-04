"""
Budget Optimizer Tests — ml-backend.

Tests:
  - POST /api/v1/budget/optimize returns 200 with correct structure
  - Allocations sum exactly to the total input budget
  - Hero piece allocation is greater than the accessories allocation
  - Input validation: reject budget < 500 (422)
  - Input validation: reject unsupported occasions (422)
  - Verify custom categories allocation works
"""

from __future__ import annotations

import os
os.environ["TESTING"] = "1"

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    return TestClient(app)


def test_budget_optimize_valid_casual(client):
    """
    Assert basic validation and response structure for a valid request.
    """
    payload = {
        "budget_inr": 5000,
        "occasion": "casual"
    }
    response = client.post("/api/v1/budget/optimize", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["total_budget_inr"] == 5000
    assert data["occasion"] == "casual"
    assert "allocations" in data
    assert len(data["allocations"]) > 0
    assert data["allocated_sum_inr"] == 5000
    assert data["unused_budget_inr"] == 0
    assert len(data["tips"]) > 0

    # Ensure all allocations are non-negative
    for item in data["allocations"]:
        assert item["allocated_amount_inr"] >= 50
        assert item["percentage"] > 0
        assert len(item["category"]) > 0
        assert len(item["description"]) > 0


def test_budget_hero_greater_than_accessories(client):
    """
    Assert that the hero piece allocation is greater than the accessories allocation.
    """
    payload = {
        "budget_inr": 10000,
        "occasion": "wedding"
    }
    response = client.post("/api/v1/budget/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    allocations = {item["category"]: item["allocated_amount_inr"] for item in data["allocations"]}
    
    # Hero category should be the highest
    hero_key = "Sherwani / Kurta / Saree (Hero)"
    acc_key = "Accessories (Safa / Dupatta / Jewelry / Watch)"
    
    assert hero_key in allocations
    assert acc_key in allocations
    assert allocations[hero_key] > allocations[acc_key]


def test_budget_optimize_invalid_occasion(client):
    """
    Assert that unsupported occasions return a 422 validation error.
    """
    payload = {
        "budget_inr": 5000,
        "occasion": "space_suit_party"
    }
    response = client.post("/api/v1/budget/optimize", json=payload)
    assert response.status_code == 422


def test_budget_optimize_invalid_budget(client):
    """
    Assert that budgets less than 500 return a 422 validation error.
    """
    payload = {
        "budget_inr": 499,
        "occasion": "casual"
    }
    response = client.post("/api/v1/budget/optimize", json=payload)
    assert response.status_code == 422


def test_budget_custom_categories(client):
    """
    Assert that custom categories override standard templates and sum to the total budget.
    """
    payload = {
        "budget_inr": 12000,
        "occasion": "casual",
        "custom_categories": ["Premium Watch", "Sneakers", "Jeans"]
    }
    response = client.post("/api/v1/budget/optimize", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["allocated_sum_inr"] == 12000
    categories = [item["category"] for item in data["allocations"]]
    assert len(categories) == 3
    assert "Premium Watch" in categories
    assert "Sneakers" in categories
    assert "Jeans" in categories


@pytest.mark.parametrize("budget", [500, 733, 1000, 3550, 15023, 100000])
def test_budget_exact_sums(client, budget):
    """
    Test various budget values to verify the rounding-adjustment logic always
    results in a sum that matches the total budget exactly.
    """
    payload = {
        "budget_inr": budget,
        "occasion": "formal"
    }
    response = client.post("/api/v1/budget/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["allocated_sum_inr"] == budget
    assert data["unused_budget_inr"] == 0
