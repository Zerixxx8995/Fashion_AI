"""
Review ORM model.

Maps to the `reviews` PostgreSQL table.
Indexed fields (per architecture plan): product_id

Stores publicly visible reviewer photos (as URLs only — never raw bytes)
and the pre-computed fake review detection result.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Index, String, Float, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Review(Base):
    """
    A single product review with reviewer-submitted photo URLs.

    Fake review scores are computed at scrape time by the Celery pipeline
    and written here. The frontend reads these pre-computed values — no
    real-time CV inference is triggered when a user views a product listing.

    reviewer_images: JSON array of reviewer photo URLs from the platform.
    review_image_embeddings: stored in Pinecone — not in this table.
    stock_match_score: highest cosine similarity of any review image vs stock.
    is_flagged_fake: True if mismatch_score >= threshold at scrape time.
    """

    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    platform_review_id: Mapped[str] = mapped_column(String(256), nullable=True)
    reviewer_text: Mapped[str] = mapped_column(Text, nullable=True)
    # JSON array of reviewer photo URLs — raw bytes NEVER stored
    reviewer_images: Mapped[str] = mapped_column(Text, nullable=True)
    # Pre-computed by fake_review_detector at scrape time
    stock_match_score: Mapped[float] = mapped_column(Float, nullable=True)
    is_flagged_fake: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    product = relationship("Product", back_populates="reviews")

    # ---------------------------------------------------------------------------
    # Indexes
    # ---------------------------------------------------------------------------

    __table_args__ = (
        # product_id: fetched in bulk when loading a product's trust score
        Index("ix_reviews_product_id", "product_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Review id={self.id!r} product_id={self.product_id!r} "
            f"flagged={self.is_flagged_fake}>"
        )
