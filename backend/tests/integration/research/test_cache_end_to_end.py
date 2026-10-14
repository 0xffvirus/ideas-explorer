"""Integration tests: adapters + real Postgres cache, zero HTTP on cache hits."""

from __future__ import annotations

import httpx
import pytest
import respx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.research.adapters.hn import HN_SEARCH_URL
from app.research.adapters.web import TAVILY_ENDPOINT
from app.research.cache import PostgresCache
from tests.unit.research.helpers import load_fixture, make_hn, make_web

pytestmark = pytest.mark.integration


@respx.mock
async def test_second_identical_search_makes_zero_http_calls(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    route = respx.post(TAVILY_ENDPOINT).mock(
        return_value=httpx.Response(200, json=load_fixture("tavily_search.json"))
    )
    cache = PostgresCache(db_session_factory)
    async with httpx.AsyncClient() as client:
        tool = make_web(client, cache=cache)
        first = await tool.search("pet sitting market size")
        second = await tool.search("pet sitting market size")

    assert route.call_count == 1
    assert [str(item.url) for item in first] == [str(item.url) for item in second]
    assert len(second) == 2


@respx.mock
async def test_cache_survives_a_new_adapter_instance(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    route = respx.post(TAVILY_ENDPOINT).mock(
        return_value=httpx.Response(200, json=load_fixture("tavily_search.json"))
    )
    cache = PostgresCache(db_session_factory)
    async with httpx.AsyncClient() as client:
        first = await make_web(client, cache=cache).search("market evidence query")
        second = await make_web(client, cache=cache).search("market evidence query")

    assert route.call_count == 1
    assert [str(item.url) for item in first] == [str(item.url) for item in second]


@respx.mock
async def test_failed_search_is_not_cached(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    route = respx.post(TAVILY_ENDPOINT).mock(return_value=httpx.Response(429))
    cache = PostgresCache(db_session_factory)
    async with httpx.AsyncClient() as client:
        tool = make_web(client, cache=cache)
        assert await tool.search("uncached storm query") == []
        assert route.call_count == 3
        assert await cache.get("web:uncached storm query") is None


@respx.mock
async def test_community_adapter_caches_its_own_results(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    route = respx.get(HN_SEARCH_URL).mock(
        return_value=httpx.Response(200, json=load_fixture("hn_search.json"))
    )
    cache = PostgresCache(db_session_factory)
    async with httpx.AsyncClient() as client:
        tool = make_hn(client, cache=cache)
        first = await tool.search("community pain query")
        second = await tool.search("community pain query")

    assert route.call_count == 1
    assert len(first) == len(second) == 3


@respx.mock
async def test_adapters_do_not_share_cache_entries(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    web_route = respx.post(TAVILY_ENDPOINT).mock(
        return_value=httpx.Response(200, json=load_fixture("tavily_search.json"))
    )
    hn_route = respx.get(HN_SEARCH_URL).mock(
        return_value=httpx.Response(200, json=load_fixture("hn_search.json"))
    )
    cache = PostgresCache(db_session_factory)
    async with httpx.AsyncClient() as client:
        web_items = await make_web(client, cache=cache).search("shared query text")
        hn_items = await make_hn(client, cache=cache).search("shared query text")

    assert web_route.call_count == 1
    assert hn_route.call_count == 1
    assert {item.source for item in web_items} == {"web"}
    assert {item.source for item in hn_items} == {"hn"}
    assert await cache.get("web:shared query text") is not None
    assert await cache.get("hn:shared query text") is not None
