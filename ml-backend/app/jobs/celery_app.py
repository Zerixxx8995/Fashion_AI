"""
Celery app factory — ml-backend.

Responsibility: Create and configure the single shared Celery application
instance that all job modules import.

Design decisions:
  - REDIS_URL env var is the broker AND backend. Upstash provides a
    standard `rediss://` URL — set this in .env.
  - Tasks are discovered via autodiscover_tasks from the jobs package.
  - Task result expiry: 24 hours (results only needed for status polling).
  - All CV jobs are defined in jobs/cv_jobs.py.
  - All scraping jobs are defined in jobs/scraping_jobs.py.
  - All alert jobs are defined in jobs/alert_jobs.py.

Environment variables required:
  REDIS_URL  — e.g. rediss://:<password>@<host>:<port>
"""

from __future__ import annotations

import os

from celery import Celery

# ---------------------------------------------------------------------------
# Redis URL
# ---------------------------------------------------------------------------

REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ---------------------------------------------------------------------------
# Celery application
# ---------------------------------------------------------------------------

celery_app = Celery(
    "fashion_ai",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Result expiry — CV job results only need to live long enough for
    # the frontend to poll them (24 hours is generous).
    result_expires=86_400,

    # Retry policy for transient broker failures
    broker_connection_retry_on_startup=True,

    # In local development without a separate Celery worker, task_always_eager runs tasks synchronously.
    task_always_eager=os.getenv("CELERY_ALWAYS_EAGER", "true").lower() == "true",
    task_store_eager_result=True,
    task_eager_propagates=True,
    result_backend="cache+memory://",

    # Task routing (explicit queues keep CV jobs and scraping jobs separate)
    task_routes={
        "app.jobs.cv_jobs.*": {"queue": "cv"},
        "app.jobs.scraping_jobs.*": {"queue": "scraping"},
        "app.jobs.alert_jobs.*": {"queue": "alerts"},
    },

    # Beat schedule placeholder — alert check runs every 5 minutes
    beat_schedule={},
)

# Auto-discover all tasks in the jobs package
celery_app.autodiscover_tasks(["app.jobs"])
