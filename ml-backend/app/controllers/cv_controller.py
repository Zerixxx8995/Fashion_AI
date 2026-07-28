"""
CV Controller — ml-backend.

Responsibility: Parse the HTTP request, call the CV service, and shape
the HTTP response. Nothing else.

Layer rules:
  - Receives FastAPI Request / Form data / UploadFile from the router
  - Calls cv_service functions ONLY — never calls core/ or jobs/ directly
  - Returns Pydantic response models or plain dicts for FastAPI to serialise
  - Raises HTTPException for client errors (4xx)

Functions:
  handle_submit_score    → POST /cv/score
  handle_get_status      → GET  /cv/score/{job_id}/status
  handle_get_result      → GET  /cv/score/{job_id}/result
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, UploadFile, status

import app.services.cv_service as cv_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Controller functions
# ---------------------------------------------------------------------------

async def handle_submit_score(
    *,
    product_id: str,
    user_id: str,
    uploaded_image_url: str,
    stock_image_urls: list[str],
) -> dict[str, Any]:
    """
    Controller for POST /cv/score.

    Validates that stock_image_urls is non-empty, then enqueues the Celery
    job via cv_service and returns the job envelope.

    Returns:
        {
            "job_id": str,
            "celery_task_id": str,
            "status": "pending"
        }
    """
    if not stock_image_urls:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="stock_image_urls must not be empty.",
        )

    logger.info(
        "[cv_controller] submit score product_id=%s user_id=%s",
        product_id, user_id,
    )

    result = cv_service.submit_cv_score_job(
        product_id=product_id,
        user_id=user_id,
        uploaded_image_url=uploaded_image_url,
        stock_image_urls=stock_image_urls,
    )
    return result


def handle_get_status(celery_task_id: str) -> dict[str, str]:
    """
    Controller for GET /cv/score/{job_id}/status.

    Args:
        celery_task_id: The celery_task_id returned from the submit endpoint.

    Returns:
        {"celery_task_id": str, "status": "pending"|"running"|"complete"|"failed"}
    """
    logger.debug("[cv_controller] get status celery_task_id=%s", celery_task_id)
    return cv_service.get_job_status(celery_task_id)


def handle_get_result(celery_task_id: str) -> dict[str, Any]:
    """
    Controller for GET /cv/score/{job_id}/result.

    Args:
        celery_task_id: The celery_task_id returned from the submit endpoint.

    Returns:
        Full confidence score result dict.

    Raises:
        HTTPException 409: If the job is not yet complete.
        HTTPException 500: If the job failed.
    """
    logger.debug("[cv_controller] get result celery_task_id=%s", celery_task_id)
    try:
        return cv_service.get_job_result(celery_task_id)
    except ValueError as exc:
        msg = str(exc)
        # Failed/revoked task → 500 Internal Server Error
        if "failed with state=" in msg:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=msg,
            ) from exc
        # Not yet complete → 409 Conflict (job still in progress)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=msg,
        ) from exc
