"""
Tests for Celery job queue — ml-backend.

Strategy:
  - Override broker_url to "memory://" and use task_always_eager so tasks
    run synchronously in-process with zero network calls and no Redis needed.
  - Mock app.jobs.cv_jobs.encode_image so no CLIP model load, no GPU.
  - Assert that:
      1. score_product_image can be enqueued (delay() returns a result with .id)
      2. When run eagerly, result contains all expected fields
      3. Job status lifecycle: task state = SUCCESS after completion
      4. Result shape matches the defined contract
      5. Failure path raises an exception

Requirements tested (from build order Step 6):
  CV job enqueues correctly (job_id returned immediately)
  job_id returned immediately
  Status polling works (result.state = 'SUCCESS' on success)
  Result shape includes all required score fields
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Test configuration — eager mode (no broker needed)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True, scope="module")
def celery_eager_mode():
    """
    Configure Celery to run tasks synchronously (ALWAYS_EAGER).

    Key overrides:
      broker_url = "memory://" avoids loading the Redis transport entirely.
      result_backend = "cache+memory://" provides an in-process result store.
      task_always_eager = True makes delay() run the task inline.
      task_eager_propagates = True lets exceptions bubble up.
    """
    from app.jobs.celery_app import celery_app
    celery_app.conf.update(
        broker_url="memory://",
        task_always_eager=True,
        task_eager_propagates=True,
        result_backend="cache+memory://",
    )
    yield
    celery_app.conf.update(task_always_eager=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _random_embedding() -> np.ndarray:
    """Return a normalised random CLIP-shaped embedding (512,)."""
    vec = np.random.randn(512).astype(np.float32)
    return vec / np.linalg.norm(vec)


STOCK_URLS = [
    "https://images.myntra.com/product/stock_1.jpg",
    "https://images.myntra.com/product/stock_2.jpg",
]
UPLOADED_URL = "https://b2.example.com/user-uploads/photo.jpg"
PRODUCT_ID = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())
JOB_ID = str(uuid.uuid4())


def _mock_encode(url: str) -> np.ndarray:
    """Return a random normalised embedding for any URL (no network/GPU)."""
    return _random_embedding()


def _run_task() -> dict:
    from app.jobs.cv_jobs import score_product_image
    with patch("app.jobs.cv_jobs.encode_image", side_effect=_mock_encode):
        result = score_product_image.delay(
            job_id=JOB_ID,
            uploaded_image_url=UPLOADED_URL,
            stock_image_urls=STOCK_URLS,
            product_id=PRODUCT_ID,
            user_id=USER_ID,
        )
        return result.get()


# ---------------------------------------------------------------------------
# TestCeleryConfig — assert the Celery app is correctly configured
# ---------------------------------------------------------------------------

class TestCeleryConfig:
    """Assert Celery app-level configuration."""

    def test_celery_app_name(self):
        from app.jobs.celery_app import celery_app
        assert celery_app.main == "fashion_ai"

    def test_task_serializer_is_json(self):
        from app.jobs.celery_app import celery_app
        assert celery_app.conf.task_serializer == "json"

    def test_result_serializer_is_json(self):
        from app.jobs.celery_app import celery_app
        assert celery_app.conf.result_serializer == "json"

    def test_result_expires_is_24h(self):
        from app.jobs.celery_app import celery_app
        assert celery_app.conf.result_expires == 86_400

    def test_cv_queue_routing_registered(self):
        from app.jobs.celery_app import celery_app
        routes = celery_app.conf.task_routes
        assert "app.jobs.cv_jobs.*" in routes
        assert routes["app.jobs.cv_jobs.*"]["queue"] == "cv"

    def test_cv_jobs_task_registered(self):
        from app.jobs.celery_app import celery_app
        assert "app.jobs.cv_jobs.score_product_image" in celery_app.tasks


# ---------------------------------------------------------------------------
# TestJobEnqueue — assert delay() returns a result object with an ID
# ---------------------------------------------------------------------------

class TestJobEnqueue:
    """
    In ALWAYS_EAGER mode, delay() executes synchronously and returns an
    EagerResult. Interface is identical to AsyncResult (.id, .get(), .state).
    """

    def test_delay_returns_result_with_id(self):
        """Enqueuing returns a result object with a task ID immediately."""
        from app.jobs.cv_jobs import score_product_image
        with patch("app.jobs.cv_jobs.encode_image", side_effect=_mock_encode):
            result = score_product_image.delay(
                job_id=JOB_ID,
                uploaded_image_url=UPLOADED_URL,
                stock_image_urls=STOCK_URLS,
                product_id=PRODUCT_ID,
                user_id=USER_ID,
            )
        assert result is not None, "delay() returned None — task not enqueued"
        assert result.id is not None, "AsyncResult.id must not be None"

    def test_delay_returns_result_id_is_string(self):
        from app.jobs.cv_jobs import score_product_image
        with patch("app.jobs.cv_jobs.encode_image", side_effect=_mock_encode):
            result = score_product_image.delay(
                job_id=JOB_ID,
                uploaded_image_url=UPLOADED_URL,
                stock_image_urls=STOCK_URLS,
                product_id=PRODUCT_ID,
                user_id=USER_ID,
            )
        assert isinstance(result.id, str), "AsyncResult.id must be a string"


# ---------------------------------------------------------------------------
# TestJobResult — assert result shape and status
# ---------------------------------------------------------------------------

class TestJobResult:
    """Assert result contains all expected fields with correct types/ranges."""

    def test_result_status_is_complete(self):
        assert _run_task()["status"] == "complete"

    def test_result_has_job_id(self):
        result = _run_task()
        assert "job_id" in result
        assert result["job_id"] == JOB_ID

    def test_result_has_stock_match_score(self):
        result = _run_task()
        assert "stock_match_score" in result
        assert 0.0 <= result["stock_match_score"] <= 1.0, \
            f"stock_match_score out of range: {result['stock_match_score']}"

    def test_result_has_authenticity_score(self):
        result = _run_task()
        assert "authenticity_score" in result
        assert 0.0 <= result["authenticity_score"] <= 1.0

    def test_result_has_overall_confidence(self):
        result = _run_task()
        assert "overall_confidence" in result
        assert 0.0 <= result["overall_confidence"] <= 1.0

    def test_result_has_label(self):
        result = _run_task()
        assert "label" in result
        assert result["label"] in ("high", "moderate", "low"), \
            f"label must be high/moderate/low, got {result['label']!r}"

    def test_result_has_num_stock_images_used(self):
        result = _run_task()
        assert "num_stock_images_used" in result
        assert result["num_stock_images_used"] == len(STOCK_URLS)

    def test_result_has_uploaded_image_url(self):
        assert _run_task()["uploaded_image_url"] == UPLOADED_URL

    def test_result_has_product_id(self):
        assert _run_task()["product_id"] == PRODUCT_ID

    def test_result_has_user_id(self):
        assert _run_task()["user_id"] == USER_ID


# ---------------------------------------------------------------------------
# TestStatusPolling — assert status lifecycle (task completes as SUCCESS)
# ---------------------------------------------------------------------------

class TestStatusPolling:
    """
    In ALWAYS_EAGER mode tasks run synchronously, so state goes directly
    to SUCCESS. We verify the polling contract is honoured.
    """

    def test_status_is_success_after_completion(self):
        from app.jobs.cv_jobs import score_product_image
        with patch("app.jobs.cv_jobs.encode_image", side_effect=_mock_encode):
            result = score_product_image.delay(
                job_id=JOB_ID,
                uploaded_image_url=UPLOADED_URL,
                stock_image_urls=STOCK_URLS,
                product_id=PRODUCT_ID,
                user_id=USER_ID,
            )
        assert result.state == "SUCCESS", \
            f"Expected state='SUCCESS', got {result.state!r}"

    def test_result_retrievable_after_completion(self):
        from app.jobs.cv_jobs import score_product_image
        with patch("app.jobs.cv_jobs.encode_image", side_effect=_mock_encode):
            result = score_product_image.delay(
                job_id=JOB_ID,
                uploaded_image_url=UPLOADED_URL,
                stock_image_urls=STOCK_URLS,
                product_id=PRODUCT_ID,
                user_id=USER_ID,
            )
        data = result.get()
        assert data is not None
        assert data["status"] == "complete"


# ---------------------------------------------------------------------------
# TestJobRetry — assert retry/failure path
# ---------------------------------------------------------------------------

class TestJobRetry:
    """
    Assert that when encode_image raises an exception the task propagates it.
    task_eager_propagates=True is set in the fixture.
    """

    def test_task_raises_on_encode_failure(self):
        """When CLIP encoding fails, the task should raise (after retries)."""
        from app.jobs.cv_jobs import score_product_image

        def _failing_encode(url: str) -> np.ndarray:
            raise RuntimeError("Simulated network failure")

        # In eager mode with task_eager_propagates=True, retry() re-raises
        # the original exception after exhausting retries.
        with patch("app.jobs.cv_jobs.encode_image", side_effect=_failing_encode):
            with pytest.raises(Exception):
                score_product_image.delay(
                    job_id=JOB_ID,
                    uploaded_image_url=UPLOADED_URL,
                    stock_image_urls=STOCK_URLS,
                    product_id=PRODUCT_ID,
                    user_id=USER_ID,
                )
