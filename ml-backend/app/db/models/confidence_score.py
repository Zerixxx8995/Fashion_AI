"""
ConfidenceScore ORM model.

Maps to the `confidence_scores` PostgreSQL table.
Stores the result of a CV scan job — one row per user-uploaded photo scan.

Note: uploaded_image_embedding is stored in Pinecone (not here).
Only the Pinecone vector ID is referenced from this table.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Index, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class ConfidenceScore(Base):
    """
    Result of a CV confidence scoring job.

    One row per scan request. Created by the Celery CV job when it completes.
    The frontend polls /cv/score/{job_id}/result to read this row.
    """

    __tablename__ = "confidence_scores"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Backblaze B2 URL of the user-uploaded photo
    uploaded_image_url: Mapped[str] = mapped_column(Text, nullable=False)
    # Component scores — all in [0.0, 1.0]
    stock_match_score: Mapped[float] = mapped_column(Float, nullable=False)
    authenticity_score: Mapped[float] = mapped_column(Float, nullable=False)
    overall_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    product = relationship("Product", back_populates="confidence_scores")
    user = relationship("User", back_populates="confidence_scores")

    def __repr__(self) -> str:
        return (
            f"<ConfidenceScore id={self.id!r} product_id={self.product_id!r} "
            f"overall={self.overall_confidence:.3f}>"
        )
