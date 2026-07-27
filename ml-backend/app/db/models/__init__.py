"""
DB models package — import all models here so that:

1. Alembic's env.py can do `from app.db.models import *` and discover every
   table automatically when generating migrations.
2. Any code that calls `Base.metadata.create_all(engine)` will include all
   tables without having to import each model file individually.
"""

from app.db.models.alert import Alert
from app.db.models.confidence_score import ConfidenceScore
from app.db.models.product import Product
from app.db.models.review import Review
from app.db.models.user import User
from app.db.models.wardrobe_item import WardrobeItem

__all__ = [
    "Alert",
    "ConfidenceScore",
    "Product",
    "Review",
    "User",
    "WardrobeItem",
]
