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
  POST   /cv/similar                      Find visually similar cheaper products
"""

from __future__ import annotations

from typing import Annotated, Any, List, Optional

from fastapi import APIRouter, Form, status

from app.controllers import cv_controller
from app.models.cv_models import SimilarProductsRequest

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

    Non-blocking — enqueues a Celery job and returns job_id immediately (HTTP 202).
    Client polls `/cv/score/{job_id}/status` until complete, then calls `/result`.
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

    `job_id` = `celery_task_id` returned by the submit endpoint.
    Status: pending | running | complete | failed
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

    Returns 409 if not yet complete. Returns 500 if job failed.
    """
    return cv_controller.handle_get_result(job_id)


# ---------------------------------------------------------------------------
# POST /cv/similar
# ---------------------------------------------------------------------------

@router.post(
    "/similar",
    status_code=status.HTTP_200_OK,
    summary="Find visually similar cheaper products",
    response_description="Ranked list of similar products sorted by similarity score",
)
def find_similar_products(body: SimilarProductsRequest) -> dict[str, Any]:
    """
    Find visually similar products via CLIP embeddings + Pinecone search.

    Accepts `image_url` (takes precedence) or `text_query`.
    Results ranked by cosine similarity (highest first).
    Set `max_price_inr` to filter for cheaper alternatives only.
    """
    return cv_controller.handle_find_similar(body=body)
