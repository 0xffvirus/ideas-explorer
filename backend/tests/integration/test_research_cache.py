"""Integration tests for the Postgres research cache (real database, respx HTTP)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings_as_test_overrides
from app.cost import CostMeter
from app.research import Evidence, ResearchCache, WebSearch
from app.research.adapters.tavily import TavilyProvider
from app.research.cache import cache_key

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "research"
TAVILY_JSON: dict[str, Any] = json.loads((FIXTURES / "tavily_search.json").read_text())


def _evidence() -> list[Evidence]:
    return [
        Evidence(
            source="web",
            url="https://example.com/a",
            title="A result",
            snippet="Some <b>snippet</b> text",
            published_at=datetime(2024, 1, 15, tzinfo=UTC),
            score=0.9,
        ),
        Evidence(
            source="web",
            url="https://example.com/b",
            title="Another result",
            snippet="More text",
            score=0.5,
        ),
    ]


async def test_cache_round_trip(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    cache = ResearchCache(db_session_factory)
    items = _evidence()
    key = cache_key("web", "Pet Care Market", 8)
    await cache.set(key, items, timedelta(hours=1))

    loaded = await cache.get(key)
    assert loaded == items
    assert loaded is not None
    assert loaded[0].url == items[0].url
    assert loaded[0].published_at == datetime(2024, 1, 15, tzinfo=UTC)


async def test_cache_overwrites_on_repeated_sets(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    cache = ResearchCache(db_session_factory)
    key = cache_key("web", "upsert me", 8)
    await cache.set(key, _evidence(), timedelta(hours=1))
    replacement = [_evidence()[1]]
    await cache.set(key, replacement, timedelta(hours=1))

    assert await cache.get(key) == replacement


async def test_cache_expiry_with_an_injected_clock(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    holder = [now]
    cache = ResearchCache(db_session_factory, clock=lambda: holder[0])
    key = cache_key("web", "expiring", 8)
    await cache.set(key, _evidence(), timedelta(hours=1))
    assert await cache.get(key) is not None

    holder[0] = now + timedelta(hours=2)
    assert await cache.get(key) is None


async def test_cache_key_normalizes_the_query(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    assert cache_key("web", "  Pet   CARE  Market ", 8) == "web:pet care market:limit=8"
    cache = ResearchCache(db_session_factory)
    await cache.set(cache_key("web", "  Pet   CARE  Market ", 8), _evidence(), timedelta(hours=1))
    assert await cache.get(cache_key("web", "pet care market", 8)) is not None
    assert await cache.get(cache_key("reddit", "pet care market", 8)) is None
    assert await cache.get(cache_key("web", "pet care market", 3)) is None


async def test_second_search_hits_the_cache_with_zero_extra_http_calls(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = settings_as_test_overrides(
        tavily_api_key="test-tavily-key",
        research_timeout_seconds=1.0,
    )
    meter = CostMeter()
    with respx.mock(assert_all_called=False) as router:
        route = router.post("https://api.tavily.com/search").mock(
            return_value=httpx.Response(200, json=TAVILY_JSON)
        )
        provider = TavilyProvider(settings, http_client=httpx.AsyncClient(), meter=meter)
        tool = WebSearch(
            provider,
            cache=ResearchCache(db_session_factory),
            ttl=timedelta(hours=1),
        )
        first = await tool.search("pet care market")
        second = await tool.search("  PET   care  MARKET ")

    assert route.call_count == 1
    assert first
    assert second == first
    assert meter.by_category["web"] == pytest.approx(settings.tavily_cost_per_search_usd)


async def test_different_limits_do_not_share_cache_entries(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = settings_as_test_overrides(
        tavily_api_key="test-tavily-key",
        research_timeout_seconds=1.0,
    )
    meter = CostMeter()
    with respx.mock(assert_all_called=False) as router:
        route = router.post("https://api.tavily.com/search").mock(
            return_value=httpx.Response(200, json=TAVILY_JSON)
        )
        provider = TavilyProvider(settings, http_client=httpx.AsyncClient(), meter=meter)
        tool = WebSearch(
            provider,
            cache=ResearchCache(db_session_factory),
            ttl=timedelta(hours=1),
        )
        narrow = await tool.search("pet care market", limit=3)
        repeated = await tool.search("pet care market", limit=3)
        wide = await tool.search("pet care market", limit=8)

    assert route.call_count == 2
    assert narrow
    assert repeated == narrow
    assert len(wide) >= len(narrow)
    assert meter.by_category["web"] == pytest.approx(2 * settings.tavily_cost_per_search_usd)
