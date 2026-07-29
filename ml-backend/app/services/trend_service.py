"""
Trend Service — ml-backend.

Responsibility: Handles business logic for trend discovery, retrieval, and
recalculating trends based on database stats.

Layer rules:
  - Calls core/trend_scorer.py for pure ML calculations.
  - Queries SQLAlchemy models/trend_item.py.
  - Does NOT contain HTTP or routing knowledge.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.core import trend_scorer
from app.db.models.trend_item import TrendItem
from app.db.models.product import Product

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seed Data
# ---------------------------------------------------------------------------

SEED_TRENDS = [
    {
        "name": "Oversized Floral Kurtas",
        "category": "kurtas",
        "lifecycle_stage": "emerging",
        "signal_score": 7.2,
        "origin": "Myntra Bestsellers",
        "image_urls": ["https://images.unsplash.com/photo-1610030469983-98e550d6193c?w=500"],
    },
    {
        "name": "Cargo Style Denim Jeans",
        "category": "jeans",
        "lifecycle_stage": "peaking",
        "signal_score": 8.9,
        "origin": "Ajio Trends",
        "image_urls": ["https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=500"],
    },
    {
        "name": "Neon Crochet Crop Tops",
        "category": "tops",
        "lifecycle_stage": "dying",
        "signal_score": 1.5,
        "origin": "Social Media Mentions",
        "image_urls": ["https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=500"],
    },
    {
        "name": "Pastel Organza Sarees",
        "category": "sarees",
        "lifecycle_stage": "emerging",
        "signal_score": 6.8,
        "origin": "Instagram Influencer Feed",
        "image_urls": ["https://images.unsplash.com/photo-1583391733956-3750e0ff4e8b?w=500"],
    },
    {
        "name": "Retro Chunky Sneakers",
        "category": "sneakers",
        "lifecycle_stage": "peaking",
        "signal_score": 9.4,
        "origin": "Amazon Fashion",
        "image_urls": ["https://images.unsplash.com/photo-1552346154-21d32810aba3?w=500"],
    }
]


# ---------------------------------------------------------------------------
# Public Service API
# ---------------------------------------------------------------------------

def get_trending_items(
    db: Session,
    *,
    category: Optional[str] = None,
    limit: int = 10,
) -> list[TrendItem]:
    """
    Fetch trending items, optionally filtered by category.
    If the db has no trends, automatically seeds initial trends.
    """
    stmt = select(TrendItem)
    if category:
        stmt = stmt.where(TrendItem.category == category.lower())
    
    # Order by highest signal score first
    stmt = stmt.order_by(TrendItem.signal_score.desc()).limit(limit)
    results = db.scalars(stmt).all()

    if not results:
        logger.info("[trend_service] No trends found in database. Seeding initial trend data.")
        results = seed_initial_trends(db)
        # Apply filtering & sorting to the seeded results if needed
        if category:
            results = [r for r in results if r.category == category.lower()]
        results.sort(key=lambda x: x.signal_score, reverse=True)
        results = results[:limit]

    return results


def seed_initial_trends(db: Session) -> list[TrendItem]:
    """
    Seed initial TrendItem entries in the database.
    """
    seeded = []
    for data in SEED_TRENDS:
        trend = TrendItem(
            name=data["name"],
            category=data["category"],
            lifecycle_stage=data["lifecycle_stage"],
            signal_score=data["signal_score"],
            origin=data["origin"],
            image_urls=data["image_urls"],
            updated_at=datetime.utcnow()
        )
        db.add(trend)
        seeded.append(trend)
    
    db.commit()
    logger.info("[trend_service] Seeded %d trend items.", len(seeded))
    return seeded


def recalculate_trends_from_products(db: Session) -> None:
    """
    Scan existing products to dynamically calculate trends.
    For each distinct category:
      1. Aggregates product counts, avg price, etc.
      2. Computes a signal score via core/trend_scorer.
      3. Classifies lifecycle_stage.
      4. Upserts or updates a TrendItem.
    """
    # Find all distinct product categories and sizes
    categories_stmt = select(Product.category).distinct()
    categories = db.scalars(categories_stmt).all()

    for cat in categories:
        if not cat:
            continue
        
        # Calculate stats for the category
        # Total products count
        count_stmt = select(func.count()).select_from(Product).where(Product.category == cat)
        product_count = db.scalar(count_stmt) or 0

        if product_count == 0:
            continue

        # In a real environment we'd compare volume growth over time.
        # For simulation, growth is randomized/derived from total volume.
        growth_rate = 0.15 if product_count > 10 else -0.05
        social_mentions = product_count * 2
        review_vol = product_count // 3

        # Compute signal score
        score = trend_scorer.calculate_signal_score(
            appearance_count=product_count,
            growth_rate=growth_rate,
            social_mention_count=social_mentions,
            review_volume=review_vol,
        )

        # Acceleration/Momentum
        acceleration = 0.3 if growth_rate > 0 else -0.2

        # Lifecycle stage classification
        stage = trend_scorer.determine_lifecycle_stage(
            signal_score=score,
            acceleration=acceleration,
        )

        # Check if trend already exists
        trend_stmt = select(TrendItem).where(TrendItem.category == cat)
        trend = db.scalar(trend_stmt)

        if trend:
            trend.signal_score = score
            trend.lifecycle_stage = stage
            trend.updated_at = datetime.utcnow()
            logger.info("[trend_service] Updated trend for category '%s' (score=%s, stage=%s)", cat, score, stage)
        else:
            # Create new trend item
            trend = TrendItem(
                name=f"Trending {cat.title()}",
                category=cat,
                lifecycle_stage=stage,
                signal_score=score,
                origin="Platform Scrapes & Mentions",
                image_urls=["https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=500"],
                updated_at=datetime.utcnow()
            )
            db.add(trend)
            logger.info("[trend_service] Created new trend for category '%s' (score=%s, stage=%s)", cat, score, stage)
            
    db.commit()
