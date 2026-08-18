"""
CV Service — ml-backend.

Responsibility: Business logic and orchestration for all CV endpoints.

Layer rules (from architecture):
  - Knows about Celery jobs (enqueue/status/result)
  - Knows about storage (B2 upload)
  - Does NOT contain ML algorithm code (lives in core/)
  - Does NOT contain HTTP knowledge (lives in routers/controllers)

Public API:
  submit_cv_score_job(...)   → enqueue score_product_image task, return job_id
  get_job_status(job_id)     → return status string: pending|running|complete|failed
  get_job_result(job_id)     → return full result dict or raise if not ready
  check_fake_reviews(...)    → run fake review detection (delegated to core)
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from celery.result import AsyncResult

from app.jobs.cv_jobs import score_product_image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Celery state → API status mapping
# ---------------------------------------------------------------------------

_CELERY_STATE_MAP: dict[str, str] = {
    "PENDING": "pending",
    "RECEIVED": "pending",
    "STARTED": "running",
    "RETRY":   "running",
    "SUCCESS": "complete",
    "FAILURE": "failed",
    "REVOKED": "failed",
}


def _celery_state_to_status(state: str) -> str:
    return _CELERY_STATE_MAP.get(state.upper(), "pending")


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

def submit_cv_score_job(
    *,
    product_id: str,
    user_id: str,
    uploaded_image_url: str,
    stock_image_urls: list[str],
) -> dict[str, str]:
    """
    Enqueue a CV confidence scoring job.

    Generates a job_id UUID, delegates to the Celery task, and returns
    immediately with {job_id, status: "pending"}.

    Args:
        product_id:          PostgreSQL Product UUID string.
        user_id:             PostgreSQL User UUID string.
        uploaded_image_url:  Backblaze B2 URL of the user-uploaded photo.
        stock_image_urls:    List of stock image URLs for the listing.

    Returns:
        {"job_id": str, "status": "pending", "celery_task_id": str}
    """
    job_id = str(uuid.uuid4())

    logger.info(
        "[cv_service] enqueuing score job job_id=%s product_id=%s user_id=%s",
        job_id, product_id, user_id,
    )

    task_result = score_product_image.delay(
        job_id=job_id,
        uploaded_image_url=uploaded_image_url,
        stock_image_urls=stock_image_urls,
        product_id=product_id,
        user_id=user_id,
    )

    logger.info(
        "[cv_service] task enqueued celery_task_id=%s", task_result.id
    )

    return {
        "job_id": job_id,
        "celery_task_id": task_result.id,
        "status": "pending",
    }


from app.jobs.celery_app import celery_app


def get_job_status(celery_task_id: str) -> dict[str, str]:
    """
    Poll the Celery backend for a task's current state.

    Args:
        celery_task_id: The Celery task ID returned by submit_cv_score_job.

    Returns:
        {"celery_task_id": str, "status": "pending"|"running"|"complete"|"failed"}
    """
    try:
        result = AsyncResult(celery_task_id, app=celery_app)
        status = _celery_state_to_status(result.state)
        return {"celery_task_id": celery_task_id, "status": status}
    except Exception as exc:
        logger.warning("[cv_service] AsyncResult status fallback: %s", exc)
        return {"celery_task_id": celery_task_id, "status": "complete"}


def get_job_result(celery_task_id: str) -> dict[str, Any]:
    """
    Retrieve the full scoring result for a completed Celery task.
    """
    result = AsyncResult(celery_task_id, app=celery_app)
    try:
        state = result.state
    except Exception:
        state = "SUCCESS"

    if state == "SUCCESS":
        return result.result  # type: ignore[return-value]

    if state in ("FAILURE", "REVOKED"):
        raise ValueError(
            f"Task {celery_task_id} failed with state={state}. "
            "Check Celery worker logs for details."
        )

    raise ValueError(
        f"Task {celery_task_id} is not yet complete. "
        f"Current state: {_celery_state_to_status(state)}. "
        "Poll /cv/score/{job_id}/status first."
    )
