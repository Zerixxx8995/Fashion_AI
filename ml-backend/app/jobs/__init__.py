"""
Jobs package — ml-backend.

Exports the shared Celery app and all task functions.
"""

from app.jobs.celery_app import celery_app
from app.jobs.cv_jobs import score_product_image
from app.jobs.scraping_jobs import trigger_product_scrape
from app.jobs.alert_jobs import check_price_alerts

__all__ = [
    "celery_app",
    "score_product_image",
    "trigger_product_scrape",
    "check_price_alerts",
]
