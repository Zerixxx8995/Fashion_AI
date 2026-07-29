"""
TrendItem SQLAlchemy ORM Model — ml-backend.

Maps to the `trend_items` table.
Indexed fields: name, category, lifecycle_stage.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List

from sqlalchemy import DateTime, Float, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class TrendItem(Base):
    __tablename__ = "trend_items"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    lifecycle_stage: Mapped[str] = mapped_column(
        String(32),  # emerging | peaking | dying
        nullable=False,
        index=True,
    )
    signal_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    origin: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        default="unknown",
    )
    image_urls: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "category": self.category,
            "lifecycle_stage": self.lifecycle_stage,
            "signal_score": self.signal_score,
            "origin": self.origin,
            "image_urls": self.image_urls,
            "updated_at": self.updated_at.isoformat() + "Z",
        }
