"""Unit tests for the Hacker News adapter."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.research.adapters.hn import HN_SEARCH_URL
from tests.unit.research.helpers import load_fixture, make_hn


@respx.mock
async def test_maps_hits_fixture_to_evidence(http_client: httpx.AsyncClient) -> None:
    route = respx.get(HN_SEARCH_URL).mock(
        return_value=httpx.Response(200, json=load_fixture("hn_search.json"))
    )
    tool = make_hn(http_client)
    items = await tool.search("pet sitting")

    assert len(items) == 3
    first, second, third = items
    assert first.source == "hn"
    assert str(first.url) == "https://news.ycombinator.com/item?id=40123456"
    assert first.snippet == (
        "I've tried Rover & local Facebook groups, but consistency is the problem."
    )
    assert first.score == pytest.approx(120 / 170)
    assert first.published_at == datetime(2024, 5, 20, 14, 0, tzinfo=UTC)

    assert str(second.url) == "https://rover.com/jobs"
    assert second.score == pytest.approx(3 / 53)

    assert str(third.url) == "https://news.ycombinator.com/item?id=40123458"
    assert third.title == "Sitters keep cancelling on me & I can't find backups."
    assert third.score == 0.0
    assert third.published_at is None

    request = route.calls[0].request
    assert request.url.params["query"] == "pet sitting"
    assert request.url.params["tags"] == "story"
    assert request.url.params["hitsPerPage"] == "8"


@respx.mock
async def test_malformed_payload_returns_empty(http_client: httpx.AsyncClient) -> None:
    respx.get(HN_SEARCH_URL).mock(return_value=httpx.Response(200, json={"hits": "nope"}))
    tool = make_hn(http_client)
    assert await tool._fetch("query", 8) == []
    assert await tool.search("query") == []


@respx.mock
async def test_storm_returns_empty(http_client: httpx.AsyncClient) -> None:
    route = respx.get(HN_SEARCH_URL).mock(return_value=httpx.Response(503))
    tool = make_hn(http_client)
    assert await tool.search("storm") == []
    assert route.call_count == 3


@respx.mock
async def test_unexpected_payload_returns_empty(http_client: httpx.AsyncClient) -> None:
    respx.get(HN_SEARCH_URL).mock(return_value=httpx.Response(200, json={"nope": 1}))
    tool = make_hn(http_client)
    assert await tool.search("surprise") == []
