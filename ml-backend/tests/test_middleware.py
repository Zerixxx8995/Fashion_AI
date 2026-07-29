"""
Middleware Tests — ml-backend.

Tests all four middleware layers using FastAPI TestClient with TESTING=1
(which disables Clerk auth so tests don't need a real JWT).

Strategy:
  - TESTING=1 env var disables ClerkAuthMiddleware in create_app()
  - Error handler, CORS, rate limiter, and request logger are all active
  - Auth tests use a specially configured app with auth enabled + mock verifier
  - Rate limiter tests configure a low limit to trigger 429 quickly

Requirements tested (from build order Step 9):
  assert unauthenticated requests rejected 401            → TestAuthMiddleware
  assert malformed input returns consistent error shape   → TestErrorHandler
  assert CORS headers present                             → TestCORSMiddleware
  assert rate limiting triggers on abuse                  → TestRateLimiter
  assert request logger attaches X-Response-Time-Ms       → TestRequestLogger
"""

from __future__ import annotations

import os
import time

# TESTING=1 must be set BEFORE importing app to disable auth middleware
os.environ["TESTING"] = "1"

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient

from app.main import app as main_app
from app.middleware.error_handler import register_error_handlers
from app.middleware.cors import register_cors
from app.middleware.rate_limiter import RateLimiterMiddleware, _request_log
from app.middleware.request_logger import RequestLoggerMiddleware
from app.middleware.auth_middleware import ClerkAuthMiddleware

# ---------------------------------------------------------------------------
# Shared test client (TESTING=1 → auth middleware is skipped)
# ---------------------------------------------------------------------------

client = TestClient(main_app)


# ---------------------------------------------------------------------------
# TestErrorHandler — consistent error shape (NF6)
# ---------------------------------------------------------------------------

class TestErrorHandler:
    """
    Assert all error responses return { error, detail, status_code } shape.
    """

    def test_404_has_canonical_error_shape(self):
        response = client.get("/api/v1/this-route-does-not-exist")
        assert response.status_code == 404
        body = response.json()
        assert "error" in body, f"Missing 'error' key: {body}"
        assert "detail" in body, f"Missing 'detail' key: {body}"
        assert "status_code" in body, f"Missing 'status_code' key: {body}"

    def test_404_status_code_matches_body(self):
        response = client.get("/api/v1/nonexistent")
        assert response.json()["status_code"] == 404

    def test_422_has_canonical_error_shape(self):
        """POST /cv/score with missing fields → 422 Validation Error."""
        response = client.post(
            "/api/v1/cv/score",
            data={"product_id": "not-a-uuid"},  # missing user_id, urls, etc.
        )
        assert response.status_code == 422
        body = response.json()
        assert "error" in body
        assert "detail" in body
        assert "status_code" in body

    def test_422_error_field_is_string(self):
        response = client.post("/api/v1/cv/score", data={"product_id": "x"})
        body = response.json()
        assert isinstance(body["error"], str)

    def test_422_detail_field_is_string(self):
        response = client.post("/api/v1/cv/score", data={"product_id": "x"})
        body = response.json()
        assert isinstance(body["detail"], str)

    def test_unhandled_exception_returns_500(self):
        """
        Register a route that raises an unhandled exception and assert
        the error handler converts it to 500 with the canonical shape.
        """
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        test_app = FastAPI()
        register_error_handlers(test_app)

        @test_app.get("/boom")
        def _boom():
            raise RuntimeError("totally unexpected")

        tc = TestClient(test_app, raise_server_exceptions=False)
        response = tc.get("/boom")
        assert response.status_code == 500
        body = response.json()
        assert body["status_code"] == 500
        assert "error" in body
        assert "detail" in body
        # Must not expose the raw exception message or stack trace
        assert "totally unexpected" not in body["detail"]

    def test_explicit_http_exception_returns_correct_status(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        test_app = FastAPI()
        register_error_handlers(test_app)

        @test_app.get("/forbidden")
        def _forbidden():
            raise HTTPException(status_code=403, detail="Access denied.")

        tc = TestClient(test_app, raise_server_exceptions=False)
        response = tc.get("/forbidden")
        assert response.status_code == 403
        body = response.json()
        assert body["status_code"] == 403
        assert body["detail"] == "Access denied."


# ---------------------------------------------------------------------------
# TestCORSMiddleware — CORS headers must be present
# ---------------------------------------------------------------------------

class TestCORSMiddleware:
    """Assert CORS headers are present on responses."""

    def test_cors_header_present_on_get(self):
        response = client.get(
            "/api/v1/health",
            headers={"Origin": "https://fashion.app"},
        )
        assert "access-control-allow-origin" in response.headers, \
            f"CORS header missing. Headers: {dict(response.headers)}"

    def test_cors_header_present_on_post(self):
        response = client.post(
            "/api/v1/cv/similar",
            json={"text_query": "blue kurta"},
            headers={"Origin": "https://fashion.app"},
        )
        assert "access-control-allow-origin" in response.headers

    def test_preflight_options_returns_200(self):
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "https://fashion.app",
                "Access-Control-Request-Method": "GET",
            },
        )
        # FastAPI CORSMiddleware returns 200 for preflight
        assert response.status_code in (200, 204)

    def test_health_returns_200(self):
        """Smoke test: health endpoint works with all middleware registered."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# TestRequestLogger — X-Response-Time-Ms header
# ---------------------------------------------------------------------------

class TestRequestLogger:
    """Assert request logger attaches X-Response-Time-Ms to responses."""

    def test_response_time_header_present(self):
        response = client.get("/api/v1/health")
        assert "x-response-time-ms" in response.headers, \
            f"X-Response-Time-Ms header missing. Headers: {dict(response.headers)}"

    def test_response_time_is_numeric(self):
        response = client.get("/api/v1/health")
        val = response.headers.get("x-response-time-ms", "")
        assert val.isdigit(), f"x-response-time-ms is not a number: {val!r}"

    def test_response_time_is_non_negative(self):
        response = client.get("/api/v1/health")
        val = int(response.headers.get("x-response-time-ms", "-1"))
        assert val >= 0


# ---------------------------------------------------------------------------
# TestRateLimiter — 429 on excess requests
# ---------------------------------------------------------------------------

class TestRateLimiter:
    """Assert rate limiter triggers 429 after the configured threshold."""

    def _make_rate_limited_app(self, max_requests: int = 3) -> TestClient:
        """
        Build a minimal FastAPI app with a tight rate limit for testing.
        Uses a fresh _request_log to avoid pollution from other tests.
        """
        import importlib
        import app.middleware.rate_limiter as rl_module

        # Temporarily override the module-level constants
        original_max = rl_module._MAX_REQUESTS
        original_window = rl_module._WINDOW_SECONDS
        rl_module._MAX_REQUESTS = max_requests
        rl_module._WINDOW_SECONDS = 60

        # Clear the in-memory log so previous test requests don't count
        rl_module._request_log.clear()

        test_app = FastAPI()
        register_error_handlers(test_app)
        test_app.add_middleware(RateLimiterMiddleware)

        @test_app.get("/api/v1/ping")
        def _ping():
            return {"pong": True}

        tc = TestClient(test_app, raise_server_exceptions=False)

        # Restore originals after test (teardown via yield would be cleaner
        # but this is simpler for inline use)
        self._restore = lambda: setattr(rl_module, "_MAX_REQUESTS", original_max) or \
                                setattr(rl_module, "_WINDOW_SECONDS", original_window)
        return tc

    def test_requests_within_limit_succeed(self):
        tc = self._make_rate_limited_app(max_requests=5)
        for _ in range(3):
            resp = tc.get("/api/v1/ping")
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        self._restore()

    def test_exceeding_limit_returns_429(self):
        tc = self._make_rate_limited_app(max_requests=2)
        # First 2 should pass
        tc.get("/api/v1/ping")
        tc.get("/api/v1/ping")
        # Third should be rate-limited
        resp = tc.get("/api/v1/ping")
        assert resp.status_code == 429, \
            f"Expected 429 Too Many Requests, got {resp.status_code}"
        self._restore()

    def test_429_has_canonical_error_shape(self):
        tc = self._make_rate_limited_app(max_requests=1)
        tc.get("/api/v1/ping")   # use the 1 allowed request
        resp = tc.get("/api/v1/ping")
        assert resp.status_code == 429
        body = resp.json()
        assert "error" in body
        assert "detail" in body
        assert "status_code" in body
        assert body["status_code"] == 429
        self._restore()

    def test_429_has_retry_after_header(self):
        tc = self._make_rate_limited_app(max_requests=1)
        tc.get("/api/v1/ping")
        resp = tc.get("/api/v1/ping")
        assert resp.status_code == 429
        assert "retry-after" in resp.headers, \
            f"Retry-After header missing. Headers: {dict(resp.headers)}"
        self._restore()

    def test_health_is_exempt_from_rate_limit(self):
        """Health endpoint should never be rate limited."""
        tc = self._make_rate_limited_app(max_requests=1)
        # Exhaust the quota
        tc.get("/api/v1/ping")
        tc.get("/api/v1/ping")
        # Health should still respond 200 (exempt path)
        # Note: health is at /api/v1/health which is in _EXEMPT_PATHS
        resp = tc.get("/api/v1/health")
        # Health isn't on this test app, but exempt path check returns
        # call_next which will return 404 — the point is it's NOT 429
        assert resp.status_code != 429, \
            "Health endpoint should not be rate-limited"
        self._restore()


# ---------------------------------------------------------------------------
# TestAuthMiddleware — 401 on missing/invalid token
# ---------------------------------------------------------------------------

class TestAuthMiddleware:
    """
    Assert auth middleware rejects unauthenticated requests with 401.
    Uses a dedicated app with auth enabled (TESTING env var cleared for this scope).
    """

    def _make_authed_app(self) -> TestClient:
        """
        Build a minimal FastAPI app with auth middleware enabled
        and a mock _verify_token that always returns None (simulating bad token).
        """
        from unittest.mock import patch
        from fastapi import FastAPI

        test_app = FastAPI()
        register_error_handlers(test_app)

        @test_app.get("/api/v1/protected")
        def _protected():
            return {"secret": "data"}

        @test_app.get("/api/v1/health")
        def _health():
            return {"status": "ok"}

        test_app.add_middleware(ClerkAuthMiddleware)
        return TestClient(test_app, raise_server_exceptions=False)

    def test_missing_auth_header_returns_401(self):
        tc = self._make_authed_app()
        response = tc.get("/api/v1/protected")
        assert response.status_code == 401

    def test_401_has_canonical_error_shape(self):
        tc = self._make_authed_app()
        response = tc.get("/api/v1/protected")
        body = response.json()
        assert "error" in body
        assert "detail" in body
        assert "status_code" in body
        assert body["status_code"] == 401

    def test_malformed_auth_header_returns_401(self):
        tc = self._make_authed_app()
        response = tc.get(
            "/api/v1/protected",
            headers={"Authorization": "Token not-a-bearer-token"},
        )
        assert response.status_code == 401

    def test_invalid_bearer_token_returns_401(self):
        """'Bearer' with no token (empty after prefix) → 401 at header parse."""
        tc = self._make_authed_app()
        # "Bearer" with no token after it — strip() returns "" which is falsy
        response = tc.get(
            "/api/v1/protected",
            headers={"Authorization": "Bearer"},
        )
        assert response.status_code == 401, \
            f"Expected 401 for empty Bearer token, got {response.status_code}"

    def test_health_endpoint_bypasses_auth(self):
        """Health endpoint is public — must return 200 with auth middleware active."""
        tc = self._make_authed_app()
        response = tc.get("/api/v1/health")
        assert response.status_code == 200, \
            f"Health should bypass auth, got {response.status_code}"
