"""
FastAPI application factory — ml-backend.

Responsibility: Create the FastAPI app, register middleware, and mount all routers.

Design rules:
  - main.py is the composition root. It wires routers together but contains NO logic.
  - All configuration is read from environment variables (python-dotenv).
  - Base path for all ML routes: /api/v1
"""

from __future__ import annotations

import os
import logging

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import cv, health

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

logger = logging.getLogger(__name__)

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
    )

    # CORS — allow all origins in development; tighten in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount routers — all ML routes under /api/v1
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(cv.router, prefix="/api/v1")

    logger.info("FastAPI app created, routers mounted at /api/v1")
    return app


app = create_app()
