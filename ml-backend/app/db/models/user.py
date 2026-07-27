"""
User ORM model.

Maps to the `users` PostgreSQL table.
Indexed fields (per architecture plan): clerk_id
"""

from __future__ import annotations

import uuid

from sqlalchemy import Index, String, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy import DateTime

from app.db.database import Base


class User(Base):
    """
    Represents an authenticated app user synced from Clerk.

    clerk_id is the primary external identifier — indexed for fast lookups
    on every authenticated request.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    clerk_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=True)
    body_type: Mapped[str] = mapped_column(String(64), nullable=True)
    height_cm: Mapped[int] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[int] = mapped_column(Integer, nullable=True)
    # Stored as JSON: {"chest": 90, "waist": 75, "hips": 95}
    measurements: Mapped[dict] = mapped_column(Text, nullable=True)
    # Stored as JSON array: ["casual", "streetwear"]
    style_preferences: Mapped[str] = mapped_column(Text, nullable=True)
    skin_tone: Mapped[str] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    confidence_scores = relationship("ConfidenceScore", back_populates="user")
    wardrobe_items = relationship("WardrobeItem", back_populates="user")
    alerts = relationship("Alert", back_populates="user")

    # ---------------------------------------------------------------------------
    # Indexes — defined at model creation, never retrofitted
    # ---------------------------------------------------------------------------

    __table_args__ = (
        # clerk_id: looked up on every authenticated request
        Index("ix_users_clerk_id", "clerk_id"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id!r} clerk_id={self.clerk_id!r} email={self.email!r}>"
