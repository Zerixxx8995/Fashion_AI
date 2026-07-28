"""
CV API Tests — ml-backend.

Tests the full HTTP layer: router → controller → service for the CV endpoints.

Strategy:
  - Use FastAPI TestClient (httpx-based, synchronous, no server needed).
  - Mock cv_service functions so no Celery broker, no Redis, no CLIP model.
  - Assert correct HTTP status codes, response shapes, and error cases.

Requirements tested (from build order Step 7):
  POST /api/v1/cv/score    → returns job_id + celery_task_id (HTTP 202)
  GET  /api/v1/cv/score/{job_id}/status → returns status string
  GET  /api/v1/cv/score/{job_id}/result → returns score object or error

Test groups:
  TestSubmitCVScore       — POST /cv/score
  TestGetCVScoreStatus    — GET  /cv/score/{job_id}/status
  TestGetCVScoreResult    — GET  /cv/score/{job_id}/result
  TestHealthEndpoint      — GET  /health sanity check
"""

from __future__ import annotations

import uuid
from unittest.mock import patch, MagicMock
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

FAKE_JOB_ID = str(uuid.uuid4())
FAKE_TASK_ID = str(uuid.uuid4())
FAKE_PRODUCT_ID = str(uuid.uuid4())
FAKE_USER_ID = str(uuid.uuid4())
FAKE_UPLOADED_URL = "https://b2.example.com/user-uploads/shirt.jpg"
FAKE_STOCK_URLS = [
    "https://images.myntra.com/stock_a.jpg",
    "https://images.myntra.com/stock_b.jpg",
]

MOCK_SUBMIT_RESPONSE: dict[str, Any] = {
    "job_id": FAKE_JOB_ID,
    "celery_task_id": FAKE_TASK_ID,
    "status": "pending",
}

MOCK_STATUS_RESPONSE: dict[str, str] = {
    "celery_task_id": FAKE_TASK_ID,
    "status": "complete",
}

MOCK_RESULT_RESPONSE: dict[str, Any] = {
    "job_id": FAKE_JOB_ID,
    "status": "complete",
    "stock_match_score": 0.82,
    "authenticity_score": 0.78,
    "overall_confidence": 0.81,
    "label": "moderate",
    "num_stock_images_used": 2,
    "uploaded_image_url": FAKE_UPLOADED_URL,
    "product_id": FAKE_PRODUCT_ID,
    "user_id": FAKE_USER_ID,
}


def _form_data(**kwargs) -> dict:
    """Build multipart form data for POST /cv/score."""
    return {
        "product_id": FAKE_PRODUCT_ID,
        "user_id": FAKE_USER_ID,
        "uploaded_image_url": FAKE_UPLOADED_URL,
        "stock_image_urls": FAKE_STOCK_URLS,
        **kwargs,
    }


# ---------------------------------------------------------------------------
# TestHealthEndpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_returns_200(self):
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_returns_ok(self):
        response = client.get("/api/v1/health")
        assert response.json()["status"] == "ok"

    def test_health_returns_service_name(self):
        response = client.get("/api/v1/health")
        assert response.json()["service"] == "ml-backend"


# ---------------------------------------------------------------------------
# TestSubmitCVScore — POST /api/v1/cv/score
# ---------------------------------------------------------------------------

class TestSubmitCVScore:
    """Assert POST /cv/score enqueues job and returns 202 with job envelope."""

    def _post(self, **overrides) -> Any:
        data = _form_data(**overrides)
        with patch("app.controllers.cv_controller.cv_service") as mock_svc:
            mock_svc.submit_cv_score_job.return_value = MOCK_SUBMIT_RESPONSE
            response = client.post("/api/v1/cv/score", data=data)
        return response

    def test_submit_returns_202(self):
        response = self._post()
        assert response.status_code == 202, \
            f"Expected 202, got {response.status_code}: {response.text}"

    def test_submit_response_has_job_id(self):
        response = self._post()
        body = response.json()
        assert "job_id" in body, f"Missing job_id in response: {body}"

    def test_submit_response_has_celery_task_id(self):
        response = self._post()
        body = response.json()
        assert "celery_task_id" in body, f"Missing celery_task_id: {body}"

    def test_submit_response_status_is_pending(self):
        response = self._post()
        assert response.json()["status"] == "pending"

    def test_submit_calls_service_with_correct_args(self):
        data = _form_data()
        with patch("app.controllers.cv_controller.cv_service") as mock_svc:
            mock_svc.submit_cv_score_job.return_value = MOCK_SUBMIT_RESPONSE
            client.post("/api/v1/cv/score", data=data)
            mock_svc.submit_cv_score_job.assert_called_once()
            call_kwargs = mock_svc.submit_cv_score_job.call_args.kwargs
            assert call_kwargs["product_id"] == FAKE_PRODUCT_ID
            assert call_kwargs["user_id"] == FAKE_USER_ID
            assert call_kwargs["uploaded_image_url"] == FAKE_UPLOADED_URL

    def test_submit_missing_product_id_returns_422(self):
        data = {
            "user_id": FAKE_USER_ID,
            "uploaded_image_url": FAKE_UPLOADED_URL,
            "stock_image_urls": FAKE_STOCK_URLS,
        }
        response = client.post("/api/v1/cv/score", data=data)
        assert response.status_code == 422

    def test_submit_missing_user_id_returns_422(self):
        data = {
            "product_id": FAKE_PRODUCT_ID,
            "uploaded_image_url": FAKE_UPLOADED_URL,
            "stock_image_urls": FAKE_STOCK_URLS,
        }
        response = client.post("/api/v1/cv/score", data=data)
        assert response.status_code == 422

    def test_submit_missing_uploaded_image_url_returns_422(self):
        data = {
            "product_id": FAKE_PRODUCT_ID,
            "user_id": FAKE_USER_ID,
            "stock_image_urls": FAKE_STOCK_URLS,
        }
        response = client.post("/api/v1/cv/score", data=data)
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# TestGetCVScoreStatus — GET /api/v1/cv/score/{job_id}/status
# ---------------------------------------------------------------------------

class TestGetCVScoreStatus:
    """Assert GET /cv/score/{job_id}/status returns correct status."""

    def _get_status(self, task_id: str = FAKE_TASK_ID, status_val: str = "complete") -> Any:
        with patch("app.controllers.cv_controller.cv_service") as mock_svc:
            mock_svc.get_job_status.return_value = {
                "celery_task_id": task_id,
                "status": status_val,
            }
            return client.get(f"/api/v1/cv/score/{task_id}/status")

    def test_status_returns_200(self):
        response = self._get_status()
        assert response.status_code == 200

    def test_status_response_has_status_field(self):
        response = self._get_status()
        assert "status" in response.json()

    def test_status_complete(self):
        response = self._get_status(status_val="complete")
        assert response.json()["status"] == "complete"

    def test_status_pending(self):
        response = self._get_status(status_val="pending")
        assert response.json()["status"] == "pending"

    def test_status_running(self):
        response = self._get_status(status_val="running")
        assert response.json()["status"] == "running"

    def test_status_failed(self):
        response = self._get_status(status_val="failed")
        assert response.json()["status"] == "failed"

    def test_status_calls_service_with_job_id(self):
        custom_id = str(uuid.uuid4())
        with patch("app.controllers.cv_controller.cv_service") as mock_svc:
            mock_svc.get_job_status.return_value = {
                "celery_task_id": custom_id, "status": "pending"
            }
            client.get(f"/api/v1/cv/score/{custom_id}/status")
            mock_svc.get_job_status.assert_called_once_with(custom_id)


# ---------------------------------------------------------------------------
# TestGetCVScoreResult — GET /api/v1/cv/score/{job_id}/result
# ---------------------------------------------------------------------------

class TestGetCVScoreResult:
    """Assert GET /cv/score/{job_id}/result returns full score or correct error."""

    def test_result_returns_200_when_complete(self):
        with patch("app.controllers.cv_controller.cv_service") as mock_svc:
            mock_svc.get_job_result.return_value = MOCK_RESULT_RESPONSE
            response = client.get(f"/api/v1/cv/score/{FAKE_TASK_ID}/result")
        assert response.status_code == 200

    def test_result_has_overall_confidence(self):
        with patch("app.controllers.cv_controller.cv_service") as mock_svc:
            mock_svc.get_job_result.return_value = MOCK_RESULT_RESPONSE
            response = client.get(f"/api/v1/cv/score/{FAKE_TASK_ID}/result")
        body = response.json()
        assert "overall_confidence" in body
        assert 0.0 <= body["overall_confidence"] <= 1.0

    def test_result_has_stock_match_score(self):
        with patch("app.controllers.cv_controller.cv_service") as mock_svc:
            mock_svc.get_job_result.return_value = MOCK_RESULT_RESPONSE
            response = client.get(f"/api/v1/cv/score/{FAKE_TASK_ID}/result")
        body = response.json()
        assert "stock_match_score" in body
        assert 0.0 <= body["stock_match_score"] <= 1.0

    def test_result_has_label(self):
        with patch("app.controllers.cv_controller.cv_service") as mock_svc:
            mock_svc.get_job_result.return_value = MOCK_RESULT_RESPONSE
            response = client.get(f"/api/v1/cv/score/{FAKE_TASK_ID}/result")
        assert response.json()["label"] in ("high", "moderate", "low")

    def test_result_returns_409_when_not_complete(self):
        """If the job is still pending/running, service raises ValueError → 409."""
        with patch("app.controllers.cv_controller.cv_service") as mock_svc:
            mock_svc.get_job_result.side_effect = ValueError(
                "Task abc is not yet complete. Current state: pending."
            )
            response = client.get(f"/api/v1/cv/score/{FAKE_TASK_ID}/result")
        assert response.status_code == 409

    def test_result_returns_500_when_failed(self):
        """If the job failed, service raises ValueError with 'failed with state=' → 500."""
        with patch("app.controllers.cv_controller.cv_service") as mock_svc:
            mock_svc.get_job_result.side_effect = ValueError(
                "Task abc failed with state=FAILURE."
            )
            response = client.get(f"/api/v1/cv/score/{FAKE_TASK_ID}/result")
        assert response.status_code == 500

    def test_result_calls_service_with_job_id(self):
        custom_id = str(uuid.uuid4())
        with patch("app.controllers.cv_controller.cv_service") as mock_svc:
            mock_svc.get_job_result.return_value = MOCK_RESULT_RESPONSE
            client.get(f"/api/v1/cv/score/{custom_id}/result")
            mock_svc.get_job_result.assert_called_once_with(custom_id)
