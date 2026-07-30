"""
Alert Jobs — ml-backend Celery tasks.

Responsibility: Scheduled Celery beat tasks for:
  - check_price_alerts: compares current product prices from PostgreSQL against
    active price_drop alert thresholds and triggers notifications via the
    Node.js backend's internal API.
  - check_restock_alerts: detects when previously out-of-stock products are
    available again and triggers restock notifications.

Architecture rules:
  Layer: Jobs (async task lifecycle only)
  One job: Celery task definition and scheduling
  Never does: Business logic, socket management, direct DB queries from Python
              (Node.js owns the alert DB; this job calls the internal Node API)

How it works:
  1. Celery beat fires check_price_alerts on a schedule (e.g. every 5 minutes)
  2. This job queries the products table in PostgreSQL for current prices
  3. POSTs current prices to Node.js backend /internal/alerts/check endpoint
  4. Node.js alertService evaluates thresholds + emits Socket.io events

Environment variables required:
  NODE_BACKEND_URL    — Base URL of Node.js api-backend (e.g. http://localhost:3000)
  INTERNAL_API_SECRET — Shared secret for internal service auth (no Clerk needed)
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

from app.jobs.celery_app import celery_app
from app.db.database import SessionLocal
from app.db.models.product import Product

logger = logging.getLogger(__name__)

NODE_BACKEND_URL = os.getenv("NODE_BACKEND_URL", "http://localhost:3000")
INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "dev-internal-secret")

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_current_prices() -> dict[str, int]:
    """
    Query the products table for current prices.

    Returns:
        Dict mapping product_id (str) → price_inr (int).
    """
    db = SessionLocal()
    try:
        products = db.query(Product.id, Product.price_inr).filter(
            Product.price_inr.isnot(None)
        ).all()
        return {str(p.id): p.price_inr for p in products}
    finally:
        db.close()


def _notify_node_price_check(current_prices: dict[str, int]) -> dict[str, Any]:
    """
    POST current product prices to the Node.js backend for alert evaluation.
    Node.js will compare against active alert thresholds and emit Socket.io events.
    """
    url = f"{NODE_BACKEND_URL}/internal/alerts/check-prices"
    try:
        response = requests.post(
            url,
            json={"prices": current_prices},
            headers={"X-Internal-Secret": INTERNAL_API_SECRET},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.error("[alert_jobs] Failed to notify Node.js of price check: %s", exc)
        return {"error": str(exc)}


def _notify_node_restock(restocked_ids: list[str]) -> dict[str, Any]:
    """
    POST a list of restocked product IDs to the Node.js backend.
    """
    url = f"{NODE_BACKEND_URL}/internal/alerts/check-restock"
    try:
        response = requests.post(
            url,
            json={"restocked_product_ids": restocked_ids},
            headers={"X-Internal-Secret": INTERNAL_API_SECRET},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.error("[alert_jobs] Failed to notify Node.js of restock check: %s", exc)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Celery tasks
# ---------------------------------------------------------------------------

@celery_app.task(
    name="app.jobs.alert_jobs.check_price_alerts",
    bind=True,
    max_retries=2,
)
def check_price_alerts(self) -> dict[str, Any]:
    """
    Celery beat task: scan all active price_drop alerts.

    Steps:
      1. Fetch current prices from PostgreSQL product table.
      2. POST prices to Node.js backend.
      3. Node.js evaluates thresholds, deactivates fired alerts, emits Socket.io events.

    Returns:
        Dict with product count and Node.js response summary.
    """
    logger.info("[alert_jobs] check_price_alerts started")

    try:
        current_prices = _get_current_prices()
        logger.info("[alert_jobs] fetched %d product prices", len(current_prices))

        if not current_prices:
            logger.info("[alert_jobs] no products with prices found — skipping alert check")
            return {"status": "no_products", "fired": 0, "checked": 0}

        result = _notify_node_price_check(current_prices)
        logger.info("[alert_jobs] price alert check complete: %s", result)
        return {"status": "ok", "product_count": len(current_prices), **result}

    except Exception as exc:
        logger.error("[alert_jobs] check_price_alerts failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(
    name="app.jobs.alert_jobs.check_restock_alerts",
    bind=True,
    max_retries=2,
)
def check_restock_alerts(self, restocked_product_ids: list[str]) -> dict[str, Any]:
    """
    Celery task: notify Node.js of products that just came back in stock.

    Called from scraping pipeline when a product listing changes from
    out-of-stock → in-stock during a scrape cycle.

    Args:
        restocked_product_ids: List of product UUIDs (as strings) now in stock.

    Returns:
        Dict with restock notification result.
    """
    logger.info("[alert_jobs] check_restock_alerts: %d products restocked", len(restocked_product_ids))

    try:
        result = _notify_node_restock(restocked_product_ids)
        logger.info("[alert_jobs] restock alert check complete: %s", result)
        return {"status": "ok", "restocked_count": len(restocked_product_ids), **result}

    except Exception as exc:
        logger.error("[alert_jobs] check_restock_alerts failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)
