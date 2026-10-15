"""Shared test fixtures.

Integration tests need a real Postgres (``docker compose up -d db``). When the
database is unreachable, integration-marked tests are skipped with a loud
reason instead of failing. Unit tests never touch the DB.
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
from collections.abc import AsyncIterator, Iterator
from functools import lru_cache
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.ideas import service as idea_service

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def clear_query_embedding_cache() -> Iterator[None]:
    """Keep the in-process query-embedding cache from leaking across tests."""
    idea_service._QUERY_EMBEDDING_CACHE.clear()
    yield
    idea_service._QUERY_EMBEDDING_CACHE.clear()


class OutboundNetworkBlocked(RuntimeError):
    """Raised when a test tries to open a socket to a non-loopback address."""


def _is_loopback_address(address: object) -> bool:
    """True for AF_UNIX paths, loopback IPs, and the ``localhost`` name."""
    if isinstance(address, (str, bytes)):
        return True
    if not isinstance(address, tuple) or not address:
        return False
    host = address[0]
    if not isinstance(host, str):
        return False
    if host == "localhost" or host == "":
        return True
    try:
        parsed = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return False
    if parsed.version == 6 and parsed.ipv4_mapped is not None:
        parsed = parsed.ipv4_mapped
    return parsed.is_loopback


@pytest.fixture(autouse=True)
def block_outbound_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Refuse TCP connections to anything but loopback; evals opt out.

    The default suite must never reach a paid or external API. ``respx``,
    ``httpx.MockTransport`` and ASGI transports bypass ``socket.connect`` and
    are unaffected, as are Postgres and alembic over localhost. Tests marked
    ``eval`` run against real APIs and skip the enforcement.
    """
    if request.node.get_closest_marker("eval") is not None:
        return
    real_connect = socket.socket.connect

    def guarded_connect(self: socket.socket, address: object) -> None:
        if not _is_loopback_address(address):
            raise OutboundNetworkBlocked(f"outbound network is blocked in tests: {address!r}")
        real_connect(self, address)  # type: ignore[arg-type]

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)


def _base_url() -> str:
    return get_settings().database_url


def _test_database_url() -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    base = _base_url()
    head, _, _ = base.rpartition("/")
    return f"{head}/idea_forge_test"


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


async def _reset_schema(url: str) -> None:
    """Drop and recreate the public schema so migrations always start clean."""
    import asyncpg

    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn=dsn, timeout=5)
    try:
        await conn.execute("DROP SCHEMA public CASCADE")
        await conn.execute("CREATE SCHEMA public")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    finally:
        await conn.close()


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
    asyncio.run(_reset_schema(test_url))
    asyncio.run(asyncio.to_thread(run_migrations, test_url))
    yield test_url


@pytest.fixture(scope="session")
def db_engine(migrated_database: str) -> Iterator[AsyncEngine]:
    engine = create_async_engine(migrated_database, poolclass=NullPool)
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture(scope="session")
def db_session_factory(
    db_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False, autoflush=False)


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
