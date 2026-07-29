"""
Error Handler Middleware — ml-backend.

Responsibility: Catch all unhandled exceptions and return a consistent
error shape, as required by NF6:
  { "error": str, "detail": str, "status_code": int }

Architecture rules:
  Layer: Middleware
  One job: Global exception → consistent error shape
  Never does: Business logic, auth checks, logging decisions

Registered in: app/main.py via app.add_exception_handler(...)
"""

from __future__ import annotations

import logging
import traceback

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Consistent error response shape (NF6)
# ---------------------------------------------------------------------------

def _error_response(
    *,
    status_code: int,
    error: str,
    detail: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error,
            "detail": detail,
            "status_code": status_code,
        },
    )


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """
    Handle FastAPI / Starlette HTTPException (raised explicitly in routes).
    Converts to the canonical { error, detail, status_code } shape.
    """
    logger.warning(
        "HTTPException %d on %s %s: %s",
        exc.status_code, request.method, request.url.path, exc.detail,
    )
    return _error_response(
        status_code=exc.status_code,
        error=_status_to_error_name(exc.status_code),
        detail=str(exc.detail),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handle Pydantic / FastAPI validation errors (422 Unprocessable Entity).
    Formats the error list into a human-readable detail string.
    """
    errors = exc.errors()
    # Build readable detail: "field: message; field2: message2"
    detail_parts = []
    for err in errors:
        loc = " → ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "invalid value")
        detail_parts.append(f"{loc}: {msg}" if loc else msg)
    detail = "; ".join(detail_parts)

    logger.warning(
        "ValidationError on %s %s: %s",
        request.method, request.url.path, detail,
    )
    return _error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error="Validation Error",
        detail=detail,
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """
    Catch-all for unexpected exceptions. Returns 500 Internal Server Error.
    Logs the full traceback — never exposes internal stack traces to clients.
    """
    logger.error(
        "Unhandled exception on %s %s:\n%s",
        request.method,
        request.url.path,
        traceback.format_exc(),
    )
    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error="Internal Server Error",
        detail="An unexpected error occurred. Please try again later.",
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _status_to_error_name(status_code: int) -> str:
    _MAP = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        409: "Conflict",
        422: "Validation Error",
        429: "Too Many Requests",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
    }
    return _MAP.get(status_code, f"HTTP {status_code}")


# ---------------------------------------------------------------------------
# Registration helper — called from main.py
# ---------------------------------------------------------------------------

def register_error_handlers(app: FastAPI) -> None:
    """
    Attach all exception handlers to the FastAPI app.
    Call this in create_app() before mounting routers.
    """
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
