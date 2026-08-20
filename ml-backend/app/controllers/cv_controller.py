"""
CV Controller — ml-backend.

Responsibility: Parse the HTTP request, call the appropriate service,
and shape the HTTP response. Nothing else.

Layer rules:
  - Receives FastAPI Form data / path params / JSON bodies from routers
  - Calls cv_service or similarity_service — never core/ or jobs/ directly
  - Raises HTTPException for client errors (4xx)
  - Returns plain dicts for FastAPI to serialise

Functions:
  handle_submit_score    → POST /cv/score
  handle_get_status      → GET  /cv/score/{job_id}/status
  handle_get_result      → GET  /cv/score/{job_id}/result
  handle_find_similar    → POST /cv/similar
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, status

import app.services.cv_service as cv_service
import app.services.similarity_service as similarity_service
from app.models.cv_models import SimilarProductsRequest

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Controller functions
# ---------------------------------------------------------------------------

async def handle_submit_score(
    *,
    product_id: str,
    user_id: str,
    uploaded_image_url: Optional[str] = None,
    file: Optional[Any] = None,
    stock_image_urls: list[str],
    stock_files: list[Any] = [],
) -> dict[str, Any]:
    """
    Controller for POST /cv/score. Accepts binary file upload or URL string.
    """
    image_source: Any = None
    if file is not None:
        image_source = await file.read()
    elif uploaded_image_url:
        image_source = uploaded_image_url
    else:
        image_source = "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=500"

    stock_sources: list[Any] = []
    if stock_files:
        for sf in stock_files:
            bytes_data = await sf.read()
            stock_sources.append(bytes_data)
    elif stock_image_urls:
        stock_sources = list(stock_image_urls)
    else:
        stock_sources = ["https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=500"]

    logger.info(
        "[cv_controller] submit score product_id=%s user_id=%s file=%s url=%s stock_files=%d stock_urls=%d",
        product_id, user_id, file is not None, uploaded_image_url, len(stock_files), len(stock_image_urls),
    )

    return cv_service.submit_cv_score_job(
        product_id=product_id,
        user_id=user_id,
        uploaded_image_url=image_source,
        stock_image_urls=stock_sources,
    )


def handle_get_status(celery_task_id: str) -> dict[str, str]:
    """
    Controller for GET /cv/score/{job_id}/status.
    """
    logger.debug("[cv_controller] get status celery_task_id=%s", celery_task_id)
    return cv_service.get_job_status(celery_task_id)


def handle_get_result(celery_task_id: str) -> dict[str, Any]:
    """
    Controller for GET /cv/score/{job_id}/result.

    Raises:
        HTTPException 409: Task not yet complete.
        HTTPException 500: Task failed.
    """
    logger.debug("[cv_controller] get result celery_task_id=%s", celery_task_id)
    try:
        return cv_service.get_job_result(celery_task_id)
    except ValueError as exc:
        msg = str(exc)
        if "failed with state=" in msg:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=msg,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=msg,
        ) from exc


def handle_find_similar(*, body: SimilarProductsRequest) -> dict[str, Any]:
    """
    Controller for POST /cv/similar.

    Delegates to similarity_service.find_similar_products and wraps the
    result list in a response envelope.

    Returns:
        {
            "results": [...],
            "count": int,
            "query_type": "image" | "text"
        }
    """
    logger.info(
        "[cv_controller] find_similar image=%s text=%s limit=%d",
        body.image_url, body.text_query, body.limit,
    )

    try:
        results = similarity_service.find_similar_products(
            image_url=body.image_url,
            text_query=body.text_query,
            limit=body.limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("[cv_controller] find_similar failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Similarity search is temporarily unavailable.",
        ) from exc

    return {
        "results": results,
        "count": len(results),
        "query_type": "image" if body.image_url else "text",
    }
