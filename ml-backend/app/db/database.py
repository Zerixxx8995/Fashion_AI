"""
Database engine and session factory — ml-backend.

Responsibility: Provide a SQLAlchemy engine and a reusable session factory
that all db/models and service-layer code imports. Nothing else lives here.

Rules:
  - One engine per process (module-level singleton).
  - Async sessions via asyncpg in production; sync sessions for Alembic + tests.
  - DATABASE_URL is read from environment — never hardcoded.
  - In tests, swap DATABASE_URL to an in-memory SQLite URL for isolation.
"""

from __future__ import annotations

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

# ---------------------------------------------------------------------------
# Database URL
# ---------------------------------------------------------------------------

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///:memory:")

# SQLite compatibility shim: SQLite does not support ARRAY or UUID types natively.
# In production this URL will be postgresql+psycopg2://...
_IS_SQLITE = DATABASE_URL.startswith("sqlite")


# ---------------------------------------------------------------------------
# SQLAlchemy engine
# ---------------------------------------------------------------------------

_connect_args: dict = {}
if _IS_SQLITE:
    # SQLite requires check_same_thread=False when used across threads in tests
    _connect_args = {"check_same_thread": False}
else:
    _connect_args = {"connect_timeout": 10}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    echo=False,           # Set True to log all SQL (useful for debugging)
    pool_pre_ping=True,   # Verify connections before use — prevents stale sockets
    pool_recycle=300,     # Recycle connections every 5 mins to handle Neon idle disconnects
)

# Enable WAL mode for SQLite (better concurrent read performance in tests)
if _IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


# ---------------------------------------------------------------------------
# Declarative base — all ORM models inherit from this
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """
    Shared declarative base for all SQLAlchemy ORM models.

    Import this in each model file:
        from app.db.database import Base
    """
    pass


# ---------------------------------------------------------------------------
# Dependency helper (used by FastAPI routes via Depends)
# ---------------------------------------------------------------------------

def get_db():
    """
    FastAPI dependency that yields a database session and ensures cleanup.

    Usage in a route:
        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
