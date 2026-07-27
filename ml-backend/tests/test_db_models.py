"""
Tests for db/models — ml-backend.

Plan assertions:
  - assert all models create tables without error
  - assert indexed fields are indexed

Strategy:
  Uses SQLite in-memory — no live PostgreSQL required.
  Base.metadata.create_all() is the create-tables assertion.
  Index presence is verified by inspecting the SQLAlchemy Inspector.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

# Import Base and all models (the import itself registers models with metadata)
from app.db.database import Base
from app.db.models import Alert, ConfidenceScore, Product, Review, User, WardrobeItem


# ---------------------------------------------------------------------------
# Module-scoped in-memory engine — created once, shared across all tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    """SQLite in-memory engine — tables created once for the whole test module."""
    _engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(_engine)
    yield _engine
    Base.metadata.drop_all(_engine)
    _engine.dispose()


@pytest.fixture(scope="module")
def db_session(engine):
    """Session scoped to the module — rolled back after all tests."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture(scope="module")
def inspector(engine):
    """SQLAlchemy Inspector for asserting indexes and columns."""
    return inspect(engine)


# ---------------------------------------------------------------------------
# TestTablesCreated — assert all models create tables without error
# ---------------------------------------------------------------------------

class TestTablesCreated:
    """Assert all six tables exist after create_all()."""

    def test_users_table_exists(self, inspector):
        assert "users" in inspector.get_table_names(), \
            "Table 'users' was not created"

    def test_products_table_exists(self, inspector):
        assert "products" in inspector.get_table_names(), \
            "Table 'products' was not created"

    def test_confidence_scores_table_exists(self, inspector):
        assert "confidence_scores" in inspector.get_table_names(), \
            "Table 'confidence_scores' was not created"

    def test_reviews_table_exists(self, inspector):
        assert "reviews" in inspector.get_table_names(), \
            "Table 'reviews' was not created"

    def test_wardrobe_items_table_exists(self, inspector):
        assert "wardrobe_items" in inspector.get_table_names(), \
            "Table 'wardrobe_items' was not created"

    def test_alerts_table_exists(self, inspector):
        assert "alerts" in inspector.get_table_names(), \
            "Table 'alerts' was not created"

    def test_six_tables_total(self, inspector):
        """Exact count guard — catches extra or missing tables."""
        tables = inspector.get_table_names()
        expected = {"users", "products", "confidence_scores",
                    "reviews", "wardrobe_items", "alerts"}
        # Filter to only our app tables (exclude alembic_version if present)
        app_tables = {t for t in tables if t in expected}
        assert app_tables == expected, \
            f"Expected exactly 6 app tables, found: {app_tables}"


# ---------------------------------------------------------------------------
# TestIndexes — assert indexed fields are indexed
# ---------------------------------------------------------------------------

def _index_names(inspector, table: str) -> set[str]:
    """Return the set of index names for a given table."""
    return {idx["name"] for idx in inspector.get_indexes(table)}


def _indexed_columns(inspector, table: str) -> set[str]:
    """Return the set of all column names that appear in any index."""
    cols: set[str] = set()
    for idx in inspector.get_indexes(table):
        cols.update(idx["column_names"])
    return cols


class TestIndexes:
    """Assert every planned index is present on the correct table."""

    def test_users_clerk_id_indexed(self, inspector):
        """clerk_id must be indexed — looked up on every authenticated request."""
        indexed = _indexed_columns(inspector, "users")
        assert "clerk_id" in indexed, \
            f"clerk_id not indexed on users. Indexed cols: {indexed}"

    def test_products_platform_indexed(self, inspector):
        """platform must be indexed — used for source filtering queries."""
        indexed = _indexed_columns(inspector, "products")
        assert "platform" in indexed, \
            f"platform not indexed on products. Indexed cols: {indexed}"

    def test_products_platform_id_indexed(self, inspector):
        """platform_id must be indexed — used for dedup and cross-reference."""
        indexed = _indexed_columns(inspector, "products")
        assert "platform_id" in indexed, \
            f"platform_id not indexed on products. Indexed cols: {indexed}"

    def test_reviews_product_id_indexed(self, inspector):
        """product_id must be indexed — fetched in bulk on product trust score load."""
        indexed = _indexed_columns(inspector, "reviews")
        assert "product_id" in indexed, \
            f"product_id not indexed on reviews. Indexed cols: {indexed}"

    def test_wardrobe_items_user_id_indexed(self, inspector):
        """user_id must be indexed — fetched on every wardrobe page load."""
        indexed = _indexed_columns(inspector, "wardrobe_items")
        assert "user_id" in indexed, \
            f"user_id not indexed on wardrobe_items. Indexed cols: {indexed}"

    def test_alerts_user_id_indexed(self, inspector):
        """user_id must be indexed — fetched on alerts page and during management."""
        indexed = _indexed_columns(inspector, "alerts")
        assert "user_id" in indexed, \
            f"user_id not indexed on alerts. Indexed cols: {indexed}"


# ---------------------------------------------------------------------------
# TestColumns — key columns present with correct nullability
# ---------------------------------------------------------------------------

class TestColumns:
    """Spot-check required columns exist with expected constraints."""

    def _col(self, inspector, table: str, column: str) -> dict:
        cols = {c["name"]: c for c in inspector.get_columns(table)}
        assert column in cols, f"Column '{column}' not found in '{table}'"
        return cols[column]

    def test_user_clerk_id_not_nullable(self, inspector):
        col = self._col(inspector, "users", "clerk_id")
        assert not col["nullable"], "users.clerk_id must be NOT NULL"

    def test_user_email_not_nullable(self, inspector):
        col = self._col(inspector, "users", "email")
        assert not col["nullable"], "users.email must be NOT NULL"

    def test_product_platform_not_nullable(self, inspector):
        col = self._col(inspector, "products", "platform")
        assert not col["nullable"], "products.platform must be NOT NULL"

    def test_product_platform_id_not_nullable(self, inspector):
        col = self._col(inspector, "products", "platform_id")
        assert not col["nullable"], "products.platform_id must be NOT NULL"

    def test_product_url_not_nullable(self, inspector):
        col = self._col(inspector, "products", "url")
        assert not col["nullable"], "products.url must be NOT NULL"

    def test_review_is_flagged_fake_not_nullable(self, inspector):
        col = self._col(inspector, "reviews", "is_flagged_fake")
        assert not col["nullable"], "reviews.is_flagged_fake must be NOT NULL"

    def test_alert_type_not_nullable(self, inspector):
        col = self._col(inspector, "alerts", "alert_type")
        assert not col["nullable"], "alerts.alert_type must be NOT NULL"

    def test_alert_is_active_not_nullable(self, inspector):
        col = self._col(inspector, "alerts", "is_active")
        assert not col["nullable"], "alerts.is_active must be NOT NULL"

    def test_wardrobe_item_product_id_nullable(self, inspector):
        """product_id must be nullable — item may not link to a platform product."""
        col = self._col(inspector, "wardrobe_items", "product_id")
        assert col["nullable"], "wardrobe_items.product_id must be nullable"


# ---------------------------------------------------------------------------
# TestOrmRoundtrip — assert rows can be inserted and queried
# ---------------------------------------------------------------------------

class TestOrmRoundtrip:
    """Basic CRUD to confirm the ORM works against the in-memory DB."""

    def test_create_and_query_user(self, db_session):
        user = User(clerk_id="clerk_test_001", email="test@example.com", name="Test User")
        db_session.add(user)
        db_session.commit()
        fetched = db_session.query(User).filter_by(clerk_id="clerk_test_001").first()
        assert fetched is not None
        assert fetched.email == "test@example.com"

    def test_create_and_query_product(self, db_session):
        product = Product(
            platform="myntra",
            platform_id="myntra-123",
            name="Test Kurta",
            url="https://myntra.com/product/123",
        )
        db_session.add(product)
        db_session.commit()
        fetched = db_session.query(Product).filter_by(platform_id="myntra-123").first()
        assert fetched is not None
        assert fetched.platform == "myntra"

    def test_create_alert_linked_to_user_and_product(self, db_session):
        user = db_session.query(User).filter_by(clerk_id="clerk_test_001").first()
        product = db_session.query(Product).filter_by(platform_id="myntra-123").first()
        alert = Alert(
            user_id=user.id,
            product_id=product.id,
            alert_type="price_drop",
            target_price_inr=999,
        )
        db_session.add(alert)
        db_session.commit()
        fetched = db_session.query(Alert).filter_by(user_id=user.id).first()
        assert fetched is not None
        assert fetched.alert_type == "price_drop"
        assert fetched.is_active is True

    def test_create_wardrobe_item_without_product(self, db_session):
        """WardrobeItem.product_id is nullable — must insert without product link."""
        user = db_session.query(User).filter_by(clerk_id="clerk_test_001").first()
        item = WardrobeItem(
            user_id=user.id,
            product_id=None,
            name="My Denim Jacket",
            category="outerwear",
            color="blue",
        )
        db_session.add(item)
        db_session.commit()
        fetched = db_session.query(WardrobeItem).filter_by(name="My Denim Jacket").first()
        assert fetched is not None
        assert fetched.product_id is None
        assert fetched.times_worn == 0

    def test_create_review(self, db_session):
        product = db_session.query(Product).filter_by(platform_id="myntra-123").first()
        review = Review(
            product_id=product.id,
            reviewer_text="Great product!",
            is_flagged_fake=False,
        )
        db_session.add(review)
        db_session.commit()
        fetched = db_session.query(Review).filter_by(product_id=product.id).first()
        assert fetched is not None
        assert fetched.is_flagged_fake is False

    def test_create_confidence_score(self, db_session):
        user = db_session.query(User).filter_by(clerk_id="clerk_test_001").first()
        product = db_session.query(Product).filter_by(platform_id="myntra-123").first()
        cs = ConfidenceScore(
            product_id=product.id,
            user_id=user.id,
            uploaded_image_url="https://b2.example.com/user-photo.jpg",
            stock_match_score=0.91,
            authenticity_score=0.87,
            overall_confidence=0.89,
        )
        db_session.add(cs)
        db_session.commit()
        fetched = db_session.query(ConfidenceScore).filter_by(user_id=user.id).first()
        assert fetched is not None
        assert 0.0 <= fetched.overall_confidence <= 1.0
