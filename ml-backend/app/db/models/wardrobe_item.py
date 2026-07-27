"""
WardrobeItem ORM model.

Maps to the `wardrobe_items` PostgreSQL table.
Indexed fields (per architecture plan): user_id

Each row is one clothing item in a user's personal wardrobe.
The image_url points to the user's own photo stored in Backblaze B2
(the only images we store — stock and review images are URL-only).
"""

from __future__ import annotations

import uuid

from sqlalchemy import Index, String, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class WardrobeItem(Base):
    """
    A single item in a user's personal wardrobe.

    product_id is nullable: a user can add an item they didn't find on
    the platform (e.g., a gift or a foreign purchase).

    image_url is a Backblaze B2 URL — user-uploaded photos are the ONLY
    images we store in object storage. All other images are URL-only.

    image_embedding is stored in Pinecone for wardrobe gap analysis
    (finding which outfit categories the user is missing).
    """

    __tablename__ = "wardrobe_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Nullable: item may not be linked to a platform product
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=True)
    color: Mapped[str] = mapped_column(String(64), nullable=True)
    # Backblaze B2 URL — user uploaded this photo
    image_url: Mapped[str] = mapped_column(Text, nullable=True)
    purchase_price_inr: Mapped[int] = mapped_column(Integer, nullable=True)
    times_worn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    added_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="wardrobe_items")
    product = relationship("Product", back_populates="wardrobe_items")

    # ---------------------------------------------------------------------------
    # Indexes
    # ---------------------------------------------------------------------------

    __table_args__ = (
        # user_id: fetched on every wardrobe page load
        Index("ix_wardrobe_items_user_id", "user_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<WardrobeItem id={self.id!r} user_id={self.user_id!r} "
            f"name={self.name!r} category={self.category!r}>"
        )
