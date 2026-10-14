"""Shared test fixtures.

Integration tests need a real Postgres (``docker compose up -d db``). When the
database is unreachable, integration-marked tests are skipped with a loud
reason instead of failing. Unit tests never touch the DB.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from functools import lru_cache
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import get_settings
from app.db import Database

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _base_url() -> str:
    return get_settings().database_url


def _test_database_url() -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    base = _base_url()
    head, _, tail = base.rpartition("/")
    db_name, separator, query = tail.partition("?")
    return f"{head}/{db_name}_test{separator}{query}"


def _maintenance_url(url: str) -> tuple[str, str]:
    """Return (maintenance_url, database_name) for the given async URL."""
    prefix, _, tail = url.rpartition("/")
    db_name, _, _ = tail.partition("?")
    return f"{prefix}/postgres", db_name


async def _ensure_database(url: str) -> None:
    import asyncpg

    maintenance_url, db_name = _maintenance_url(url)
    dsn = maintenance_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn=dsn, timeout=5)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await conn.close()


async def _probe_database(url: str) -> bool:
    import asyncpg

    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    try:
        conn = await asyncpg.connect(dsn=dsn, timeout=3)
    except Exception:
        return False
    await conn.close()
    return True


@lru_cache(maxsize=1)
def database_is_available() -> bool:
    url = _test_database_url()
    try:
        return asyncio.run(_probe_database(_maintenance_url(url)[0]))
    except Exception:
        return False


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if database_is_available():
        return
    skip = pytest.mark.skip(
        reason="Postgres not available; run `docker compose up -d db` to enable integration tests"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


def run_migrations(url: str) -> None:
    cfg = AlembicConfig(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def test_url() -> str:
    return _test_database_url()


@pytest.fixture(scope="session")
def migrated_database(test_url: str) -> Iterator[str]:
    if not database_is_available():
        pytest.skip("Postgres not available")
    asyncio.run(_ensure_database(test_url))
    asyncio.run(asyncio.to_thread(run_migrations, test_url))
    yield test_url


@pytest.fixture(scope="session")
async def db_engine(migrated_database: str) -> AsyncIterator[AsyncEngine]:
    database = Database(migrated_database)
    yield database.engine
    await database.dispose()


@pytest.fixture
async def db_session_factory(
    db_engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    yield async_sessionmaker(db_engine, expire_on_commit=False, autoflush=False)


async def _truncate_all(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        rows = await conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
            )
        )
        tables = [row[0] for row in rows]
        if tables:
            joined = ", ".join(f'"{t}"' for t in tables)
            await conn.execute(text(f"TRUNCATE {joined} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def db_session(
    db_engine: AsyncEngine, db_session_factory: async_sessionmaker[AsyncSession]
) -> AsyncIterator[AsyncSession]:
    await _truncate_all(db_engine)
    async with db_session_factory() as session:
        yield session
