"""
CV Celery Jobs — ml-backend.

Responsibility: Define Celery task wrappers for all computer vision jobs.
These tasks are the ONLY code that bridges between the async job queue and
the pure ML core. They do NOT contain algorithm code — they delegate to
core/ and services/.

Architecture rules (from project plan):
  Layer: Jobs
  One job: Async Celery task lifecycle management only.
  Never does: Algorithm code, HTTP routing, direct business logic.

Jobs defined here:
  score_product_image  — CV confidence scoring for a user-uploaded photo.
                         Called by the CV service after uploading to B2.
                         Enqueued via: score_product_image.delay(...)
                         Result stored in Celery backend (Redis) keyed by job_id.

Job lifecycle:
  1. FastAPI route receives image upload.
  2. Service uploads image to Backblaze B2, gets image URL.
  3. Service calls score_product_image.delay(...) → returns AsyncResult with job_id.
  4. Route returns {job_id, status: "pending"} immediately.
  5. Frontend polls GET /cv/score/{job_id}/status.
  6. When task completes, result is stored in Redis.
  7. Frontend calls GET /cv/score/{job_id}/result to retrieve scores.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import numpy as np

from app.jobs.celery_app import celery_app

# Top-level import so patch('app.jobs.cv_jobs.encode_image') works in tests.
# CLIP model is loaded lazily inside encode_image via lru_cache.
from app.core.clip_encoder import encode_image

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CV Confidence Scoring Task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="app.jobs.cv_jobs.score_product_image",
    bind=True,
    max_retries=2,
    default_retry_delay=10,  # seconds between retries
    acks_late=True,          # ack only after task completes (safer)
)
def score_product_image(
    self,
    *,
    job_id: str,
    uploaded_image_url: str,
    stock_image_urls: list[str],
    product_id: str,
    user_id: str,
) -> dict[str, Any]:
    """
    Celery task: fetch image bytes, generate CLIP embeddings, compute
    confidence score, and return a structured result dict.

    This is an async task — FastAPI enqueues it and returns the job_id
    immediately. The frontend polls /cv/score/{job_id}/status until done.

    Args:
        job_id:             UUID string — used for status polling.
        uploaded_image_url: Backblaze B2 URL of the user-uploaded photo.
        stock_image_urls:   List of stock image URLs from the product listing.
        product_id:         PostgreSQL Product ID (UUID string).
        user_id:            PostgreSQL User ID (UUID string).

    Returns:
        dict with keys:
            job_id, status, stock_match_score, authenticity_score,
            overall_confidence, label, num_stock_images_used,
            uploaded_image_url, product_id, user_id

    Raises:
        Retries (up to 2x) on transient errors (network, model load).
        Raises original exception after exhausting retries.
    """
    logger.info(
        "[score_product_image] starting job_id=%s product_id=%s user_id=%s",
        job_id, product_id, user_id,
    )

    try:
        # Deferred import of the scorer keeps compute_confidence_score out of
        # the FastAPI process import chain (only needed in the worker).
        from app.core.confidence_scorer import compute_confidence_score

        # 1. Generate uploaded image embedding (encode_image accepts URL strings directly)
        logger.info("[score_product_image] encoding uploaded image from URL")
        uploaded_embedding: np.ndarray = encode_image(uploaded_image_url)

        # 2. Generate all stock image embeddings
        logger.info(
            "[score_product_image] encoding %d stock image(s)",
            len(stock_image_urls),
        )
        stock_embeddings: list[np.ndarray] = [
            encode_image(url) for url in stock_image_urls
        ]

        # 3. Compute the full confidence score
        result = compute_confidence_score(uploaded_embedding, stock_embeddings)

        logger.info(
            "[score_product_image] completed job_id=%s overall=%.4f label=%s",
            job_id, result.overall_confidence, result.label,
        )

        return {
            "job_id": job_id,
            "status": "complete",
            "stock_match_score": result.stock_match_score,
            "authenticity_score": result.authenticity_score,
            "overall_confidence": result.overall_confidence,
            "label": result.label,
            "num_stock_images_used": result.num_stock_images_used,
            "uploaded_image_url": uploaded_image_url,
            "product_id": product_id,
            "user_id": user_id,
        }

    except Exception as exc:
        logger.error(
            "[score_product_image] failed job_id=%s error=%s, retry %d/%d",
            job_id, exc, self.request.retries, self.max_retries,
        )
        raise self.retry(exc=exc)
