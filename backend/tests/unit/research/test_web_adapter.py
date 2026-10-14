"""Unit tests for the Tavily web search adapter."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.cost import CostMeter
from app.research.adapters.web import TAVILY_ENDPOINT
from app.research.cache import InMemoryCache
from tests.unit.research.helpers import load_fixture, make_web


@respx.mock
async def test_maps_tavily_fixture_to_evidence(http_client: httpx.AsyncClient) -> None:
    respx.post(TAVILY_ENDPOINT).mock(
        return_value=httpx.Response(200, json=load_fixture("tavily_search.json"))
    )
    tool = make_web(http_client)
    items = await tool.search("pet sitting marketplace")

    assert len(items) == 2
    first, second = items
    assert first.source == "web"
    assert str(first.url) == "https://example.com/pet-sitting-market"
    assert first.title == "Pet Sitting Market Size & Growth Report"
    assert "valued at $2.4 billion" in first.snippet
    assert "<strong>" not in first.snippet
    assert first.score == pytest.approx(0.94)
    assert first.published_at == datetime(2024, 6, 1, tzinfo=UTC)

    assert second.title == "example.org"
    assert second.score == 1.0
    assert second.published_at is None


@respx.mock
async def test_repeated_query_hits_cache_without_http(http_client: httpx.AsyncClient) -> None:
    route = respx.post(TAVILY_ENDPOINT).mock(
        return_value=httpx.Response(200, json=load_fixture("tavily_search.json"))
    )
    cache = InMemoryCache()
    tool = make_web(http_client, cache=cache)
    first = await tool.search("Pet  Sitting")
    second = await tool.search("pet sitting")

    assert route.call_count == 1
    assert [str(item.url) for item in first] == [str(item.url) for item in second]
    assert await cache.get("web:pet sitting") is not None
    assert await cache.get("hn:pet sitting") is None


@respx.mock
async def test_distinct_queries_are_not_conflated(http_client: httpx.AsyncClient) -> None:
    route = respx.post(TAVILY_ENDPOINT).mock(
        return_value=httpx.Response(200, json=load_fixture("tavily_search.json"))
    )
    tool = make_web(http_client, cache=InMemoryCache())
    await tool.search("pet-sitting")
    await tool.search("pet sitting")

    assert route.call_count == 2


@respx.mock
async def test_cached_results_are_sliced_by_later_limit(http_client: httpx.AsyncClient) -> None:
    route = respx.post(TAVILY_ENDPOINT).mock(
        return_value=httpx.Response(200, json=load_fixture("tavily_search.json"))
    )
    tool = make_web(http_client, cache=InMemoryCache())
    full = await tool.search("pet sitting")
    limited = await tool.search("pet sitting", limit=1)

    assert len(full) == 2
    assert len(limited) == 1
    assert route.call_count == 1


@respx.mock
async def test_cost_is_charged_once_per_provider_call(http_client: httpx.AsyncClient) -> None:
    respx.post(TAVILY_ENDPOINT).mock(
        return_value=httpx.Response(200, json=load_fixture("tavily_search.json"))
    )
    meter = CostMeter()
    tool = make_web(http_client, meter=meter)
    await tool.search("market size")
    await tool.search("market size")

    assert meter.spent_usd == pytest.approx(0.008)
    assert meter.by_category["research:web"] == pytest.approx(0.008)


@respx.mock
async def test_failed_calls_are_not_charged(http_client: httpx.AsyncClient) -> None:
    route = respx.post(TAVILY_ENDPOINT).mock(return_value=httpx.Response(429))
    meter = CostMeter()
    tool = make_web(http_client, meter=meter)

    assert await tool.search("storm") == []
    assert route.call_count == 3
    assert meter.spent_usd == 0.0


@respx.mock
async def test_missing_api_key_returns_empty_without_http(http_client: httpx.AsyncClient) -> None:
    route = respx.post(TAVILY_ENDPOINT).mock(return_value=httpx.Response(200, json={}))
    tool = make_web(http_client, api_key="")
    assert await tool.search("anything") == []
    assert route.call_count == 0


@respx.mock
async def test_provider_storm_returns_empty_and_caches_nothing(
    http_client: httpx.AsyncClient,
) -> None:
    route = respx.post(TAVILY_ENDPOINT).mock(return_value=httpx.Response(429))
    cache = InMemoryCache()
    tool = make_web(http_client, cache=cache)

    assert await tool.search("storm") == []
    assert route.call_count == 3
    assert await cache.get("web:storm") is None


@respx.mock
async def test_malformed_payload_returns_empty(http_client: httpx.AsyncClient) -> None:
    respx.post(TAVILY_ENDPOINT).mock(return_value=httpx.Response(200, json={"results": "nope"}))
    tool = make_web(http_client)
    assert await tool._fetch("surprise", 8) == []
    assert await tool.search("surprise") == []


@respx.mock
async def test_blank_query_returns_empty_without_http(http_client: httpx.AsyncClient) -> None:
    route = respx.post(TAVILY_ENDPOINT).mock(return_value=httpx.Response(200, json={}))
    tool = make_web(http_client)
    assert await tool.search("   ") == []
    assert route.call_count == 0


@respx.mock
async def test_non_positive_limit_returns_empty_without_http(
    http_client: httpx.AsyncClient,
) -> None:
    route = respx.post(TAVILY_ENDPOINT).mock(return_value=httpx.Response(200, json={}))
    tool = make_web(http_client)
    assert await tool.search("pet sitting", limit=0) == []
    assert await tool.search("pet sitting", limit=-3) == []
    assert route.call_count == 0


@respx.mock
async def test_limit_is_forwarded_and_enforced(http_client: httpx.AsyncClient) -> None:
    route = respx.post(TAVILY_ENDPOINT).mock(
        return_value=httpx.Response(200, json=load_fixture("tavily_search.json"))
    )
    tool = make_web(http_client)
    items = await tool.search("pet sitting", limit=1)

    assert len(items) == 1
    body = json.loads(route.calls[0].request.content)
    assert body["max_results"] == 1
    assert body["query"] == "pet sitting"
    assert route.calls[0].request.headers["Authorization"] == "Bearer test-key"


@respx.mock
async def test_limit_is_clamped_to_provider_max(http_client: httpx.AsyncClient) -> None:
    route = respx.post(TAVILY_ENDPOINT).mock(
        return_value=httpx.Response(200, json=load_fixture("tavily_search.json"))
    )
    tool = make_web(http_client)
    await tool.search("pet sitting", limit=100)

    body = json.loads(route.calls[0].request.content)
    assert body["max_results"] == 20


@respx.mock
async def test_long_query_is_capped_before_cache_and_http(http_client: httpx.AsyncClient) -> None:
    route = respx.post(TAVILY_ENDPOINT).mock(
        return_value=httpx.Response(200, json=load_fixture("tavily_search.json"))
    )
    cache = InMemoryCache()
    tool = make_web(http_client, cache=cache)
    long_query = "pet sitting " * 100
    await tool.search(long_query)

    body = json.loads(route.calls[0].request.content)
    assert len(body["query"]) == 500
    assert await cache.get(f"web:{body['query']}") is not None
