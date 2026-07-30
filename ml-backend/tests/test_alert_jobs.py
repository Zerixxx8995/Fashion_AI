"""
Tests for Alert Celery Jobs — ml-backend.

Strategy:
  - Mock requests.post to intercept calls to the Node.js backend.
  - SQLite in-memory database to query mock products.
  - Assert that product prices are correctly read from DB and forwarded with correct headers.
"""

from __future__ import annotations

import os
os.environ["TESTING"] = "1"

from unittest.mock import patch, MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Test configuration — eager mode (no broker needed)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True, scope="module")
def celery_eager_mode():
    """
    Configure Celery to run tasks synchronously (ALWAYS_EAGER).
    """
    from app.jobs.celery_app import celery_app
    celery_app.conf.update(
        broker_url="memory://",
        task_always_eager=True,
        task_eager_propagates=True,
        result_backend="cache+memory://",
    )
    yield
    celery_app.conf.update(task_always_eager=False)


from app.db.database import Base, get_db
from app.db.models.product import Product
from app.jobs.alert_jobs import check_price_alerts, check_restock_alerts


# ---------------------------------------------------------------------------
# Setup Database Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function", autouse=True)
def setup_db(test_engine):
    # Override SessionLocal in alert_jobs to use our test engine
    with patch("app.jobs.alert_jobs.SessionLocal", sessionmaker(bind=test_engine)):
        # Clear tables before each test
        connection = test_engine.connect()
        transaction = connection.begin()
        session = sessionmaker(bind=connection)()
        session.query(Product).delete()
        session.commit()
        
        yield session
        
        session.close()
        transaction.rollback()
        connection.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@patch("app.jobs.alert_jobs.requests.post")
def test_check_price_alerts_calls_node_with_prices(mock_post, setup_db):
    # Seed mock products in database
    setup_db.add(Product(
        id="22222222-2222-2222-2222-222222222222",
        platform="myntra",
        platform_id="m1",
        name="Red Kurta",
        price_inr=1500,
        url="https://myntra.com/p1",
    ))
    setup_db.add(Product(
        id="33333333-3333-3333-3333-333333333333",
        platform="ajio",
        platform_id="a1",
        name="Blue Jeans",
        price_inr=2200,
        url="https://ajio.com/p2",
    ))
    setup_db.commit()

    # Mock response from Node.js backend
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "ok", "fired": 1, "checked": 2}
    mock_post.return_value = mock_response

    # Execute eager task
    result = check_price_alerts.delay().get()

    # Assertions
    assert result["status"] == "ok"
    assert result["fired"] == 1
    assert result["checked"] == 2
    assert result["product_count"] == 2

    # Verify requests.post payload and headers
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0].endswith("/internal/check-prices")
    assert kwargs["headers"]["X-Internal-Secret"] == "dev-internal-secret"
    assert kwargs["json"]["prices"] == {
        "22222222-2222-2222-2222-222222222222": 1500,
        "33333333-3333-3333-3333-333333333333": 2200,
    }


@patch("app.jobs.alert_jobs.requests.post")
def test_check_price_alerts_skips_when_no_prices(mock_post):
    # Database is empty
    result = check_price_alerts.delay().get()

    assert result["status"] == "no_products"
    assert result["fired"] == 0
    mock_post.assert_not_called()


@patch("app.jobs.alert_jobs.requests.post")
def test_check_restock_alerts(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "ok", "fired": 1, "checked": 1}
    mock_post.return_value = mock_response

    restocked_ids = ["22222222-2222-2222-2222-222222222222"]
    result = check_restock_alerts.delay(restocked_ids).get()

    assert result["status"] == "ok"
    assert result["restocked_count"] == 1
    
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0].endswith("/internal/check-restock")
    assert kwargs["headers"]["X-Internal-Secret"] == "dev-internal-secret"
    assert kwargs["json"]["restocked_product_ids"] == restocked_ids
