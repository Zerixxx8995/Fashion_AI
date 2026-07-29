"""
Trends API and Core Tests — ml-backend.

Tests coverage:
  - core/trend_scorer.py: calculate_signal_score and determine_lifecycle_stage math functions.
  - services/trend_service.py: fetching, seeding, recalculation logic.
  - routers/trends.py: GET /trends and POST /trends/recalculate endpoints.

Strategy:
  - Use SQLite in-memory database.
  - Use FastAPI TestClient to verify HTTP responses, query param filtering,
    and payload format rules.
"""

from __future__ import annotations

import os
os.environ["TESTING"] = "1"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.database import Base, get_db
from app.db.models.trend_item import TrendItem
from app.db.models.product import Product
from app.core import trend_scorer
from app.services import trend_service

# ---------------------------------------------------------------------------
# Setup Database & Test Client
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()
    
    Session = sessionmaker(bind=connection)
    session = Session()

    # Clear TrendItem table before each test
    session.query(TrendItem).delete()
    session.query(Product).delete()
    session.commit()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Core Trend Scorer Tests
# ---------------------------------------------------------------------------

class TestTrendScorer:
    def test_calculate_signal_score_zero(self):
        score = trend_scorer.calculate_signal_score(appearance_count=0, growth_rate=0.5)
        assert score == 0.0

    def test_calculate_signal_score_positive(self):
        score = trend_scorer.calculate_signal_score(
            appearance_count=50,
            growth_rate=0.4,
            social_mention_count=200,
            review_volume=30
        )
        assert 0.0 <= score <= 10.0

    def test_determine_lifecycle_stage_dying(self):
        stage = trend_scorer.determine_lifecycle_stage(signal_score=1.5, acceleration=0.5)
        assert stage == "dying"

        stage = trend_scorer.determine_lifecycle_stage(signal_score=4.0, acceleration=-0.2)
        assert stage == "dying"

    def test_determine_lifecycle_stage_peaking(self):
        stage = trend_scorer.determine_lifecycle_stage(signal_score=7.0, acceleration=0.0)
        assert stage == "peaking"

    def test_determine_lifecycle_stage_emerging(self):
        stage = trend_scorer.determine_lifecycle_stage(signal_score=3.5, acceleration=0.5)
        assert stage == "emerging"


# ---------------------------------------------------------------------------
# Trend Service Tests
# ---------------------------------------------------------------------------

class TestTrendService:
    def test_seed_initial_trends(self, db_session):
        trends = trend_service.seed_initial_trends(db_session)
        assert len(trends) > 0
        db_trends = db_session.query(TrendItem).all()
        assert len(db_trends) == len(trends)

    def test_get_trending_items_auto_seeds(self, db_session):
        # Starts empty, should auto seed
        trends = trend_service.get_trending_items(db_session)
        assert len(trends) > 0
        assert any(t.lifecycle_stage == "emerging" for t in trends)

    def test_get_trending_items_category_filter(self, db_session):
        trend_service.seed_initial_trends(db_session)
        trends = trend_service.get_trending_items(db_session, category="kurtas")
        assert len(trends) > 0
        assert all(t.category == "kurtas" for t in trends)

    def test_recalculate_trends_from_products(self, db_session):
        # Create some mock products
        db_session.add(Product(
            platform="myntra",
            platform_id="p1",
            name="Jeans Alpha",
            brand="Brand X",
            price_inr=1999,
            category="jeans",
            url="http://example.com/p1",
            stock_image_urls='["http://example.com/p1.jpg"]'
        ))
        db_session.add(Product(
            platform="ajio",
            platform_id="p2",
            name="Kurta Beta",
            brand="Brand Y",
            price_inr=999,
            category="kurtas",
            url="http://example.com/p2",
            stock_image_urls='["http://example.com/p2.jpg"]'
        ))
        db_session.commit()

        trend_service.recalculate_trends_from_products(db_session)
        trends = db_session.query(TrendItem).all()
        assert len(trends) == 2
        categories = {t.category for t in trends}
        assert "jeans" in categories
        assert "kurtas" in categories


# ---------------------------------------------------------------------------
# HTTP Route Tests
# ---------------------------------------------------------------------------

class TestTrendsHTTP:
    def test_get_trends_returns_list_with_lifecycle_stage(self, client):
        response = client.get("/api/v1/trends")
        assert response.status_code == 200
        body = response.json()
        assert "trends" in body
        assert isinstance(body["trends"], list)
        
        for item in body["trends"]:
            assert "name" in item
            assert "category" in item
            assert "lifecycle_stage" in item
            assert "signal_score" in item
            assert "origin" in item
            assert "image_urls" in item
            assert item["lifecycle_stage"] in ["emerging", "peaking", "dying"]

    def test_get_trends_limit(self, client):
        response = client.get("/api/v1/trends?limit=2")
        assert response.status_code == 200
        body = response.json()
        assert len(body["trends"]) <= 2

    def test_get_trends_invalid_limit(self, client):
        response = client.get("/api/v1/trends?limit=-5")
        assert response.status_code == 422  # validation failure

    def test_get_trends_category_filter(self, client):
        response = client.get("/api/v1/trends?category=jeans")
        assert response.status_code == 200
        body = response.json()
        for item in body["trends"]:
            assert item["category"] == "jeans"

    def test_recalculate_endpoint(self, client):
        response = client.post("/api/v1/trends/recalculate")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
