"""
FastAPI application factory — ml-backend.

Responsibility: Create the FastAPI app, register middleware, and mount all routers.

Design rules:
  - main.py is the composition root. It wires routers and middleware together
    but contains NO logic.
  - Middleware registration order matters (Starlette executes outermost first):
      1. CORS           — must be outermost to handle preflight OPTIONS
      2. RequestLogger  — log every request before it hits business logic
      3. RateLimiter    — check quota after logging (so rate-limited requests are logged)
      4. AuthMiddleware — verify JWT (innermost middleware)
      5. ErrorHandlers  — registered as exception handlers (not middleware),
                          so they wrap the entire ASGI app
  - All configuration is read from environment variables (python-dotenv).
  - Base path for all ML routes: /api/v1
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from app.middleware.cors import register_cors
from app.middleware.error_handler import register_error_handlers
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.request_logger import RequestLoggerMiddleware
from app.middleware.auth_middleware import ClerkAuthMiddleware
from app.routers import cv, health, trends, wardrobe, budget, recommendations
from app.db.database import Base, engine
import app.db.models  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

logger = logging.getLogger(__name__)


from contextlib import asynccontextmanager
from fastapi.concurrency import run_in_threadpool


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables asynchronously on startup without blocking module import
    try:
        await run_in_threadpool(Base.metadata.create_all, bind=engine)
        logger.info("Database tables initialized successfully")
    except Exception as exc:
        logger.error(f"Failed to initialize database tables: {exc}")
    yield


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title="Fashion AI — ML Backend",
        description=(
            "CV/ML API powering the Indian Fashion App. "
            "Provides confidence scoring, fake review detection, "
            "and visual similarity search."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # 1. Register exception handlers (wrap entire ASGI stack)
    register_error_handlers(app)

    # 2. CORS — outermost middleware (handles preflight OPTIONS before auth)
    register_cors(app)

    # 3. Request logger — log inbound/outbound for every request
    app.add_middleware(RequestLoggerMiddleware)

    # 4. Rate limiter — enforce per-IP request quota
    app.add_middleware(RateLimiterMiddleware)

    # 5. Auth middleware — verify Clerk JWT (skip in TEST env)
    if os.getenv("TESTING") != "1":
        app.add_middleware(ClerkAuthMiddleware)

    # Mount routers — all ML routes under /api/v1
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(cv.router, prefix="/api/v1")
    app.include_router(trends.router, prefix="/api/v1")
    app.include_router(wardrobe.router, prefix="/api/v1")
    app.include_router(budget.router, prefix="/api/v1")
    app.include_router(recommendations.router, prefix="/api/v1")

    logger.info("FastAPI app created with all middleware registered")
    return app


app = create_app()
