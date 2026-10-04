"""Shared fixtures. Database tests use a separate `imagerelevance_test` database in the compose
Postgres (created and migrated automatically), so they never touch the real data. If Postgres
isn't running, those tests are skipped instead of failing."""

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

TEST_DB = "imagerelevance_test"
ADMIN_URL = os.environ.get("TEST_ADMIN_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/postgres")
TEST_URL = os.environ.get("TEST_DATABASE_URL", f"postgresql://postgres:postgres@localhost:5432/{TEST_DB}")


def _clear_caches():
    from app.config import get_settings
    from app.db import session

    get_settings.cache_clear()
    session.get_engine.cache_clear()
    session._session_factory.cache_clear()


@pytest.fixture(scope="session")
def migrated_db():
    try:
        admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            if not conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": TEST_DB}):
                conn.execute(text(f'CREATE DATABASE "{TEST_DB}"'))
        admin.dispose()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres not reachable (start it with `docker compose up -d db`): {e}")

    from alembic import command
    from alembic.config import Config

    old_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = TEST_URL
    _clear_caches()
    command.upgrade(Config(str(Path(__file__).resolve().parent.parent / "alembic.ini")), "head")
    yield
    if old_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = old_url
    _clear_caches()


@pytest.fixture
def db(migrated_db):
    """Empty tables before each test."""
    from app.db.session import session_scope

    with session_scope() as s:
        s.execute(text("TRUNCATE ai_calls, image_tags, images, jobs RESTART IDENTITY CASCADE"))
    yield
