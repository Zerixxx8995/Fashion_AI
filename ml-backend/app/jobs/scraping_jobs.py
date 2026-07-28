"""
Scraping Jobs — ml-backend Celery tasks.

Placeholder for scraping job tasks.
Implemented in STEP 15 (Scraper: Myntra spider).
"""

from app.jobs.celery_app import celery_app


@celery_app.task(name="app.jobs.scraping_jobs.trigger_product_scrape")
def trigger_product_scrape(platform: str, category: str) -> dict:
    """Placeholder — implemented in Step 15."""
    return {"status": "not_implemented", "platform": platform, "category": category}
