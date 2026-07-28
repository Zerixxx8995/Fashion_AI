"""
Alert Jobs — ml-backend Celery tasks.

Placeholder for price alert checking tasks.
Implemented in STEP 12 (Alerts system).
"""

from app.jobs.celery_app import celery_app


@celery_app.task(name="app.jobs.alert_jobs.check_price_alerts")
def check_price_alerts() -> dict:
    """Placeholder — implemented in Step 12."""
    return {"status": "not_implemented"}
