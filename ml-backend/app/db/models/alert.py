"""
Alert ORM model.

Maps to the `alerts` PostgreSQL table.
Indexed fields (per architecture plan): user_id

Stores price drop and restock alert configurations.
The Celery beat job reads active alerts, checks current prices,
and fires Socket.io events when a threshold is crossed.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Index, String, Integer, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Alert(Base):
    """
    A price drop or restock alert set by a user on a specific product.

    alert_type: 'price_drop' | 'restock'
    target_price_inr: nullable — only used for price_drop alerts.
    is_active: False once the alert has fired or been manually removed.

    The Celery beat job queries:
        SELECT * FROM alerts WHERE is_active = True
    and checks each product's current price against target_price_inr.
    """

    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    # 'price_drop' or 'restock'
    alert_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # Only set for price_drop alerts
    target_price_inr: Mapped[int] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="alerts")
    product = relationship("Product", back_populates="alerts")

    # ---------------------------------------------------------------------------
    # Indexes
    # ---------------------------------------------------------------------------

    __table_args__ = (
        # user_id: fetched on alerts page load and during alert management
        Index("ix_alerts_user_id", "user_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Alert id={self.id!r} user_id={self.user_id!r} "
            f"type={self.alert_type!r} active={self.is_active}>"
        )
