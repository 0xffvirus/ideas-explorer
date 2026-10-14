"""Integration tests for the Postgres-backed research cache."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.research.cache import PostgresCache
from app.research.contract import Evidence

pytestmark = pytest.mark.integration


def make_evidence(title: str = "t") -> Evidence:
    return Evidence(source="web", url="https://example.com/a", title=title, snippet="snippet")


async def test_roundtrip_preserves_items(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    cache = PostgresCache(db_session_factory)
    assert await cache.get("web:missing") is None

    items = [make_evidence("one"), make_evidence("two")]
    await cache.set("web:q", items, ttl_seconds=3600)
    got = await cache.get("web:q")

    assert got is not None
    assert [item.title for item in got] == ["one", "two"]
    assert got[0].url == items[0].url
    assert got[0].retrieved_at == items[0].retrieved_at
    assert got[0].source == "web"


async def test_expired_entry_is_dropped(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    cache = PostgresCache(db_session_factory)
    await cache.set("web:q", [make_evidence()], ttl_seconds=3600)

    past = datetime.now(UTC) - timedelta(minutes=1)
    async with db_session_factory() as session:
        await session.execute(
            text("UPDATE research_cache SET expires_at = :past WHERE key = :key"),
            {"past": past, "key": "web:q"},
        )
        await session.commit()

    assert await cache.get("web:q") is None
    async with db_session_factory() as session:
        count = await session.scalar(
            text("SELECT count(*) FROM research_cache WHERE key = 'web:q'")
        )
    assert count == 0


async def test_set_is_an_upsert(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    cache = PostgresCache(db_session_factory)
    await cache.set("web:q", [make_evidence("old")], ttl_seconds=60)
    await cache.set("web:q", [make_evidence("new")], ttl_seconds=60)

    async with db_session_factory() as session:
        count = await session.scalar(
            text("SELECT count(*) FROM research_cache WHERE key = 'web:q'")
        )
    assert count == 1
    got = await cache.get("web:q")
    assert got is not None
    assert [item.title for item in got] == ["new"]


async def test_upsert_refreshes_the_expiry(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    cache = PostgresCache(db_session_factory)
    await cache.set("web:refresh", [make_evidence()], ttl_seconds=60)
    past = datetime.now(UTC) - timedelta(days=1)
    async with db_session_factory() as session:
        await session.execute(
            text("UPDATE research_cache SET expires_at = :past WHERE key = 'web:refresh'"),
            {"past": past},
        )
        await session.commit()

    await cache.set("web:refresh", [make_evidence()], ttl_seconds=600)
    async with db_session_factory() as session:
        expires_at = await session.scalar(
            text("SELECT expires_at FROM research_cache WHERE key = 'web:refresh'")
        )
    assert expires_at is not None
    assert expires_at - datetime.now(UTC) > timedelta(minutes=9)


async def test_set_purges_expired_rows(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    expired = datetime.now(UTC) - timedelta(hours=1)
    async with db_session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO research_cache (key, payload, expires_at) "
                "VALUES ('web:stale', '[]'::jsonb, :expires_at)"
            ),
            {"expires_at": expired},
        )
        await session.commit()

    cache = PostgresCache(db_session_factory)
    await cache.set("web:fresh", [make_evidence()], ttl_seconds=60)
    async with db_session_factory() as session:
        remaining = await session.scalar(
            text("SELECT count(*) FROM research_cache WHERE key = 'web:stale'")
        )
    assert remaining == 0


async def test_database_errors_degrade_to_miss(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from sqlalchemy.exc import SQLAlchemyError

    class FailingFactory:
        def __call__(self) -> None:
            raise SQLAlchemyError("database is down")

    cache = PostgresCache(FailingFactory())  # type: ignore[arg-type]
    assert await cache.get("web:q") is None
    await cache.set("web:q", [make_evidence()], ttl_seconds=60)


async def test_invalid_cached_payload_is_treated_as_miss(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    async with db_session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO research_cache (key, payload, expires_at) "
                "VALUES ('web:bad', '[{\"bogus\": 1}]'::jsonb, :expires_at)"
            ),
            {"expires_at": expires_at},
        )
        await session.commit()

    cache = PostgresCache(db_session_factory)
    assert await cache.get("web:bad") is None


async def test_empty_items_are_not_stored(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    cache = PostgresCache(db_session_factory)
    await cache.set("web:empty", [], ttl_seconds=60)
    async with db_session_factory() as session:
        count = await session.scalar(
            text("SELECT count(*) FROM research_cache WHERE key = 'web:empty'")
        )
    assert count == 0


async def test_ttl_is_reflected_in_expiry(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    cache = PostgresCache(db_session_factory)
    await cache.set("reddit:ttl", [make_evidence()], ttl_seconds=3600)
    async with db_session_factory() as session:
        expires_at = await session.scalar(
            text("SELECT expires_at FROM research_cache WHERE key = 'reddit:ttl'")
        )
    assert expires_at is not None
    delta = expires_at - datetime.now(UTC)
    assert timedelta(minutes=55) < delta < timedelta(hours=1, minutes=5)
