"""
CV Router — ml-backend.

Responsibility: Map URLs and HTTP methods to controller functions. Nothing else.

Layer rules:
  - Defines routes with @router.{method}
  - Extracts path params, query params, form fields, and file uploads from Request
  - Calls controller functions with extracted, typed arguments
  - NEVER contains business logic, service calls, or ML code

Endpoints:
  POST   /cv/score                        Submit image for confidence scoring
  GET    /cv/score/{job_id}/status        Poll job status
  GET    /cv/score/{job_id}/result        Retrieve completed result

Design note on job_id vs celery_task_id:
  The API exposes a friendly "job_id" concept (a UUID we generate) but the
  submit endpoint also returns celery_task_id (the internal Celery task ID).
  Status + result endpoints accept celery_task_id for simplicity —
  in Step 8 a mapping table can be added if needed.
"""

from __future__ import annotations

from typing import Annotated, Any, List

from fastapi import APIRouter, Form, Query, UploadFile, File, status
from fastapi.responses import JSONResponse

from app.controllers import cv_controller

router = APIRouter(prefix="/cv", tags=["Computer Vision"])


# ---------------------------------------------------------------------------
# POST /cv/score
# ---------------------------------------------------------------------------

@router.post(
    "/score",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit product image for CV confidence scoring",
    response_description="Job envelope with job_id returned immediately",
)
async def submit_cv_score(
    product_id: Annotated[str, Form(..., description="Product UUID")],
    user_id: Annotated[str, Form(..., description="User UUID")],
    uploaded_image_url: Annotated[str, Form(..., description="Backblaze B2 URL of uploaded image")],
    stock_image_urls: Annotated[List[str], Form(..., description="Stock image URLs for the product listing")],
) -> dict[str, Any]:
    """
    Submit a user-uploaded product photo for CV confidence scoring.

    This endpoint is **non-blocking** — it enqueues a Celery job and returns
    a `job_id` immediately (HTTP 202 Accepted). The client polls
    `/cv/score/{job_id}/status` until status is `complete`, then retrieves
    the full result from `/cv/score/{job_id}/result`.

    **Form fields:**
    - `product_id` — UUID of the product being evaluated
    - `user_id` — UUID of the requesting user
    - `uploaded_image_url` — Backblaze B2 URL of the user-uploaded photo
    - `stock_image_urls` — one or more stock image URLs from the listing
    """
    return await cv_controller.handle_submit_score(
        product_id=product_id,
        user_id=user_id,
        uploaded_image_url=uploaded_image_url,
        stock_image_urls=stock_image_urls,
    )


# ---------------------------------------------------------------------------
# GET /cv/score/{job_id}/status
# ---------------------------------------------------------------------------

@router.get(
    "/score/{job_id}/status",
    status_code=status.HTTP_200_OK,
    summary="Poll CV job status",
    response_description="Current job status: pending | running | complete | failed",
)
def get_cv_score_status(job_id: str) -> dict[str, str]:
    """
    Poll the status of a CV scoring job.

    `job_id` here is the `celery_task_id` returned by the submit endpoint.

    **Status values:**
    - `pending` — job is queued, not yet picked up by a worker
    - `running` — worker is actively processing
    - `complete` — result is ready; call `/result`
    - `failed` — the job failed; check worker logs
    """
    return cv_controller.handle_get_status(job_id)


# ---------------------------------------------------------------------------
# GET /cv/score/{job_id}/result
# ---------------------------------------------------------------------------

@router.get(
    "/score/{job_id}/result",
    status_code=status.HTTP_200_OK,
    summary="Retrieve completed CV scoring result",
    response_description="Full confidence score object",
)
def get_cv_score_result(job_id: str) -> dict[str, Any]:
    """
    Retrieve the full confidence score result for a completed job.

    `job_id` here is the `celery_task_id` returned by the submit endpoint.

    **Returns 409** if the job is not yet complete — poll `/status` first.
    **Returns 500** if the job failed.

    **Result fields:**
    - `stock_match_score` — cosine similarity vs primary stock image [0–1]
    - `authenticity_score` — weighted aggregate across all stock images [0–1]
    - `overall_confidence` — blended final score [0–1]
    - `label` — `high` | `moderate` | `low`
    - `num_stock_images_used` — number of stock images compared
    """
    return cv_controller.handle_get_result(job_id)
