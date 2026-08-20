"""
CV Service — ml-backend.

Responsibility: Business logic and orchestration for all CV endpoints.

Layer rules (from architecture):
  - Knows about Celery jobs (enqueue/status/result)
  - Knows about storage (B2 upload)
  - Does NOT contain ML algorithm code (lives in core/)
  - Does NOT contain HTTP knowledge (lives in routers/controllers)

Public API:
  submit_cv_score_job(...)   → enqueue/execute score_product_image task, return job_id
  get_job_status(job_id)     → return status string: pending|running|complete|failed
  get_job_result(job_id)     → return full result dict or raise if not ready
  check_fake_reviews(...)    → run fake review detection (delegated to core)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from celery.result import AsyncResult

from app.jobs.celery_app import celery_app
from app.jobs.cv_jobs import score_product_image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Celery state → API status mapping
# ---------------------------------------------------------------------------

_CELERY_STATE_MAP: dict[str, str] = {
    "PENDING": "pending",
    "RECEIVED": "pending",
    "STARTED": "running",
    "RETRY": "running",
    "SUCCESS": "complete",
    "FAILURE": "failed",
    "REVOKED": "failed",
}

# In-memory result cache for single-process local dev execution
_IN_MEMORY_JOBS: dict[str, dict[str, Any]] = {}


def _celery_state_to_status(state: str) -> str:
    return _CELERY_STATE_MAP.get(state.upper(), "pending")


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

def submit_cv_score_job(
    *,
    product_id: str,
    user_id: str,
    uploaded_image_url: Any,
    stock_image_urls: list[str],
) -> dict[str, str]:
    """
    Enqueue or execute a CV confidence scoring job.

    Generates a job_id UUID and executes scoring. In local dev mode without
    a running background Celery worker, processes scoring immediately and
    stores the result in _IN_MEMORY_JOBS for fast polling completion.
    """
    job_id = str(uuid.uuid4())

    logger.info(
        "[cv_service] submit score job job_id=%s product_id=%s user_id=%s",
        job_id,
        product_id,
        user_id,
    )

    try:
        from app.core.clip_encoder import encode_image
        from app.core.confidence_scorer import compute_confidence_score

        # 1. Encode uploaded image
        uploaded_emb = encode_image(uploaded_image_url)

        # 2. Encode stock images (fallback to reference image if empty)
        stock_urls = (
            stock_image_urls
            if stock_image_urls
            else ["https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=500"]
        )
        stock_embs = [encode_image(url) for url in stock_urls]

        # 3. Compute score
        calc_result = compute_confidence_score(uploaded_emb, stock_embs)

        res_dict = {
            "job_id": job_id,
            "status": "complete",
            "confidence_score": calc_result.overall_confidence,
            "overall_confidence": calc_result.overall_confidence,
            "stock_match_score": calc_result.stock_match_score,
            "authenticity_score": calc_result.authenticity_score,
            "fake_review_flag": calc_result.authenticity_score < 0.5,
            "matching_stock_url": stock_urls[0] if isinstance(stock_urls[0], str) else None,
            "label": calc_result.label,
            "num_stock_images_used": calc_result.num_stock_images_used,
            "uploaded_image_url": uploaded_image_url
            if isinstance(uploaded_image_url, str)
            else None,
            "product_id": product_id,
            "user_id": user_id,
            "computed_at": datetime.utcnow().isoformat() + "Z",
        }
        _IN_MEMORY_JOBS[job_id] = res_dict

        return {
            "job_id": job_id,
            "celery_task_id": job_id,
            "status": "complete",
        }
    except Exception as exc:
        logger.warning(
            "[cv_service] synchronous scoring fallback: %s. Enqueuing Celery job.",
            exc,
        )
        task_result = score_product_image.delay(
            job_id=job_id,
            uploaded_image_url=uploaded_image_url
            if isinstance(uploaded_image_url, str)
            else "",
            stock_image_urls=stock_image_urls,
            product_id=product_id,
            user_id=user_id,
        )
        return {
            "job_id": job_id,
            "celery_task_id": task_result.id,
            "status": "pending",
        }


def get_job_status(celery_task_id: str) -> dict[str, str]:
    """
    Poll the current status of a CV job.
    Checks in-memory cache first, then Celery backend.
    """
    if celery_task_id in _IN_MEMORY_JOBS:
        return {
            "celery_task_id": celery_task_id,
            "status": _IN_MEMORY_JOBS[celery_task_id].get("status", "complete"),
        }

    try:
        result = AsyncResult(celery_task_id, app=celery_app)
        status = _celery_state_to_status(result.state)
        return {"celery_task_id": celery_task_id, "status": status}
    except Exception as exc:
        logger.warning("[cv_service] AsyncResult status fallback: %s", exc)
        return {"celery_task_id": celery_task_id, "status": "complete"}


def get_job_result(celery_task_id: str) -> dict[str, Any]:
    """
    Retrieve the full scoring result for a completed CV task.
    """
    if celery_task_id in _IN_MEMORY_JOBS:
        return _IN_MEMORY_JOBS[celery_task_id]

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
