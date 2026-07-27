"""
Product ORM model.

Maps to the `products` PostgreSQL table.
Indexed fields (per architecture plan): platform, platform_id
"""

from __future__ import annotations

import uuid

from sqlalchemy import Index, String, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Product(Base):
    """
    Represents a fashion product scraped from a platform listing.

    stock_image_urls is stored as JSON (list of URL strings).
    CLIP embeddings are stored in Pinecone — not here. Only the Pinecone
    vector ID is stored here for lookup.

    platform and platform_id are both indexed:
      - platform: for filtering by source (e.g., "myntra", "amazon")
      - platform_id: for deduplication and cross-reference lookups
    """

    __tablename__ = "products"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # One of: myntra | amazon | flipkart | meesho | ajio
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    platform_id: Mapped[str] = mapped_column(String(256), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    brand: Mapped[str] = mapped_column(String(256), nullable=True)
    price_inr: Mapped[int] = mapped_column(Integer, nullable=True)
    # JSON array of stock image URLs — raw bytes are NEVER stored, only URLs
    stock_image_urls: Mapped[str] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(128), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    seller_id: Mapped[str] = mapped_column(String(256), nullable=True)
    scraped_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    confidence_scores = relationship("ConfidenceScore", back_populates="product")
    reviews = relationship("Review", back_populates="product")
    alerts = relationship("Alert", back_populates="product")
    wardrobe_items = relationship("WardrobeItem", back_populates="product")

    # ---------------------------------------------------------------------------
    # Indexes — defined at model creation, never retrofitted
    # ---------------------------------------------------------------------------

    __table_args__ = (
        # platform: filters by source (e.g., all Myntra products)
        Index("ix_products_platform", "platform"),
        # platform_id: dedup check + cross-platform lookup
        Index("ix_products_platform_id", "platform_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Product id={self.id!r} platform={self.platform!r} "
            f"platform_id={self.platform_id!r} name={self.name!r}>"
        )
