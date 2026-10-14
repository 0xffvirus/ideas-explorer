"""Unit tests for the Reddit signals adapter."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.research.adapters.reddit import REDDIT_API_BASE, REDDIT_TOKEN_URL
from app.research.cache import InMemoryCache
from tests.unit.research.helpers import load_fixture, make_reddit

SEARCH_URL = f"{REDDIT_API_BASE}/search"
COMMENTS_URL = f"{REDDIT_API_BASE}/comments/abc123"
POST_URL = "https://www.reddit.com/r/pets/comments/abc123/anyone_else_struggle/"


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def mock_token() -> respx.Route:
    return respx.post(REDDIT_TOKEN_URL).mock(
        return_value=httpx.Response(200, json=load_fixture("reddit_token.json"))
    )


def mock_search() -> respx.Route:
    return respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json=load_fixture("reddit_search.json"))
    )


@respx.mock
async def test_maps_posts_fixture_to_evidence(http_client: httpx.AsyncClient) -> None:
    mock_token()
    route = mock_search()
    tool = make_reddit(http_client)
    items = await tool.search("pet sitter pain points")

    assert len(items) == 2
    first, second = items
    assert first.source == "reddit"
    assert str(first.url) == POST_URL
    assert first.title == "Anyone else struggle to find a reliable pet sitter?"
    assert "I travel for work & finding someone" in first.snippet
    assert "&amp;" not in first.snippet
    assert first.score == pytest.approx(87 / 137)
    assert first.published_at == datetime.fromtimestamp(1717000000.0, tz=UTC)

    assert second.title == "Rover vs Wag comparison"
    assert second.snippet == "Rover vs Wag comparison"

    request = route.calls[0].request
    assert request.headers["Authorization"] == "bearer fake-token-abc"
    assert request.headers["User-Agent"] == "idea-forge-test/0.1"
    assert request.url.params["type"] == "link"
    assert request.url.params["q"] == "pet sitter pain points"


@respx.mock
async def test_token_request_uses_basic_auth(http_client: httpx.AsyncClient) -> None:
    token_route = mock_token()
    mock_search()
    tool = make_reddit(http_client)
    await tool.search("pet sitter")

    auth_header = token_route.calls[0].request.headers["Authorization"]
    assert auth_header.startswith("Basic ")
    assert token_route.calls[0].request.headers["User-Agent"] == "idea-forge-test/0.1"


@respx.mock
async def test_token_is_reused_across_searches(http_client: httpx.AsyncClient) -> None:
    token_route = mock_token()
    search_route = mock_search()
    tool = make_reddit(http_client, cache=InMemoryCache())
    await tool.search("query one")
    await tool.search("query two")

    assert token_route.call_count == 1
    assert search_route.call_count == 2


@respx.mock
async def test_token_is_refreshed_after_expiry(http_client: httpx.AsyncClient) -> None:
    token_route = mock_token()
    mock_search()
    clock = FakeClock()
    tool = make_reddit(http_client, cache=InMemoryCache(), clock=clock)

    await tool.search("query one")
    clock.now += 3569.0
    await tool.search("query two")
    assert token_route.call_count == 1

    clock.now += 2.0
    await tool.search("query three")
    assert token_route.call_count == 2


@respx.mock
async def test_concurrent_searches_fetch_one_token(http_client: httpx.AsyncClient) -> None:
    token_route = mock_token()
    mock_search()
    tool = make_reddit(http_client, cache=InMemoryCache())

    await asyncio.gather(tool.search("query one"), tool.search("query two"))
    assert token_route.call_count == 1


@respx.mock
async def test_comments_for_maps_top_comments(http_client: httpx.AsyncClient) -> None:
    mock_token()
    route = respx.get(COMMENTS_URL).mock(
        return_value=httpx.Response(200, json=load_fixture("reddit_comments.json"))
    )
    tool = make_reddit(http_client)
    items = await tool.comments_for(POST_URL)

    assert len(items) == 1
    item = items[0]
    assert item.source == "reddit"
    assert str(item.url) == "https://www.reddit.com/r/pets/comments/abc123/x/ghi789/"
    assert item.title == "Anyone else struggle to find a reliable pet sitter?"
    assert item.snippet == "I pay $30/visit and still can't get anyone consistent in my area."
    assert item.score == pytest.approx(45 / 95)

    request = route.calls[0].request
    assert request.url.params["sort"] == "top"
    assert request.url.params["limit"] == "5"


@respx.mock
async def test_comments_for_accepts_evidence_items(http_client: httpx.AsyncClient) -> None:
    mock_token()
    mock_search()
    respx.get(COMMENTS_URL).mock(
        return_value=httpx.Response(200, json=load_fixture("reddit_comments.json"))
    )
    tool = make_reddit(http_client)
    posts = await tool.search("pet sitter")
    post_evidence = next(item for item in posts if "abc123" in str(item.url))
    items = await tool.comments_for(post_evidence)
    assert len(items) == 1


@respx.mock
async def test_comments_for_is_cached(http_client: httpx.AsyncClient) -> None:
    mock_token()
    route = respx.get(COMMENTS_URL).mock(
        return_value=httpx.Response(200, json=load_fixture("reddit_comments.json"))
    )
    tool = make_reddit(http_client, cache=InMemoryCache())
    first = await tool.comments_for(POST_URL)
    second = await tool.comments_for(POST_URL)

    assert route.call_count == 1
    assert [str(item.url) for item in first] == [str(item.url) for item in second]


@respx.mock
async def test_comments_for_rejects_non_reddit_urls_without_http(
    http_client: httpx.AsyncClient,
) -> None:
    token_route = mock_token()
    comments_route = respx.get(COMMENTS_URL).mock(
        return_value=httpx.Response(200, json=load_fixture("reddit_comments.json"))
    )
    tool = make_reddit(http_client)

    assert await tool.comments_for("https://evil.example.com/r/x/comments/abc123/") == []
    assert await tool.comments_for("https://notreddit.com/r/x/comments/abc123/") == []
    assert await tool.comments_for("not a url") == []
    assert token_route.call_count == 0
    assert comments_route.call_count == 0


@respx.mock
async def test_malformed_comments_payload_returns_empty(http_client: httpx.AsyncClient) -> None:
    mock_token()
    respx.get(COMMENTS_URL).mock(
        return_value=httpx.Response(200, json={"data": {"children": "nope"}})
    )
    tool = make_reddit(http_client)
    assert await tool._comments(POST_URL, limit=5) == []
    assert await tool.comments_for(POST_URL) == []


@respx.mock
async def test_malformed_token_payload_returns_empty(http_client: httpx.AsyncClient) -> None:
    respx.post(REDDIT_TOKEN_URL).mock(return_value=httpx.Response(200, json={"nope": 1}))
    search_route = mock_search()
    tool = make_reddit(http_client)
    assert await tool.search("no token") == []
    assert search_route.call_count == 0


@respx.mock
async def test_malformed_search_payload_returns_empty(http_client: httpx.AsyncClient) -> None:
    mock_token()
    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"data": {"children": "nope"}})
    )
    tool = make_reddit(http_client)
    assert await tool._fetch("query", 8) == []


@respx.mock
async def test_search_storm_returns_empty(http_client: httpx.AsyncClient) -> None:
    mock_token()
    route = respx.get(SEARCH_URL).mock(return_value=httpx.Response(429))
    tool = make_reddit(http_client)
    assert await tool.search("storm") == []
    assert route.call_count == 3


@respx.mock
async def test_token_failure_returns_empty_without_search(http_client: httpx.AsyncClient) -> None:
    respx.post(REDDIT_TOKEN_URL).mock(return_value=httpx.Response(500))
    search_route = respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json={}))
    tool = make_reddit(http_client)
    assert await tool.search("no token") == []
    assert search_route.call_count == 0


@respx.mock
async def test_missing_credentials_returns_empty_without_http(
    http_client: httpx.AsyncClient,
) -> None:
    token_route = mock_token()
    search_route = mock_search()
    tool = make_reddit(http_client, client_id="", client_secret="")
    assert await tool.search("anything") == []
    assert token_route.call_count == 0
    assert search_route.call_count == 0
