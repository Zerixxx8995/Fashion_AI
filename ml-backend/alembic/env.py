"""
Alembic environment configuration.

This file connects Alembic to our SQLAlchemy metadata so that
`alembic revision --autogenerate` can detect model changes automatically.

DATABASE_URL is read from the environment variable at runtime — the
`sqlalchemy.url` in alembic.ini is overridden here and is never used.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# Ensure ml-backend/ is on sys.path so `app.*` imports resolve
# ---------------------------------------------------------------------------
ML_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if ML_BACKEND_DIR not in sys.path:
    sys.path.insert(0, ML_BACKEND_DIR)

# ---------------------------------------------------------------------------
# Import all models so Alembic can discover them via Base.metadata
# ---------------------------------------------------------------------------
from app.db.database import Base  # noqa: E402
import app.db.models  # noqa: E402 — imports all models, populates Base.metadata

# Alembic Config object (gives access to alembic.ini values)
config = context.config

# Override sqlalchemy.url with the DATABASE_URL environment variable.
# This keeps credentials out of alembic.ini and out of version control.
database_url = os.getenv("DATABASE_URL", "sqlite:///./dev.db")
config.set_main_option("sqlalchemy.url", database_url)

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Generates SQL scripts without connecting to the database.
    Useful for review, audit, or applying manually via psql.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    Connects to the database and applies migrations directly.
    Used in CI and deployment pipelines.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
