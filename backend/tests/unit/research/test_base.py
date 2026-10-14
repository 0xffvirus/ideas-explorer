"""Unit tests for the shared HttpAdapter behaviour."""

from __future__ import annotations

import dataclasses

import httpx
import respx

from app.research.adapters.base import AdapterDeps, HttpAdapter
from app.research.cache import InMemoryCache
from app.research.contract import Evidence
from tests.unit.research.helpers import fast_deps


class RecordingLimiter:
    def __init__(self) -> None:
        self.acquires = 0

    async def acquire(self, tokens: float = 1.0) -> None:
        self.acquires += 1


def make_evidence(title: str) -> Evidence:
    return Evidence(source="web", url=f"https://example.com/{title}", title=title, snippet="s")


class StubAdapter(HttpAdapter):
    name = "stub"

    def __init__(
        self,
        *,
        deps: AdapterDeps,
        items: list[Evidence] | None = None,
        error: Exception | None = None,
        use_http: bool = False,
    ) -> None:
        super().__init__(deps=deps)
        self.calls: list[tuple[str, int]] = []
        self._items = items or []
        self._error = error
        self._use_http = use_http

    async def _fetch(self, query: str, limit: int) -> list[Evidence]:
        self.calls.append((query, limit))
        if self._error is not None:
            raise self._error
        if self._use_http:
            payload = await self._fetch_json("GET", "https://example.com/api")
            if payload is None:
                return []
        return self._items[:limit]


async def test_unexpected_fetch_error_returns_no_results(http_client: httpx.AsyncClient) -> None:
    tool = StubAdapter(deps=fast_deps(http_client), error=RuntimeError("provider exploded"))
    assert await tool.search("query") == []


async def test_non_positive_limit_skips_fetch(http_client: httpx.AsyncClient) -> None:
    tool = StubAdapter(deps=fast_deps(http_client), items=[make_evidence("one")])
    assert await tool.search("query", limit=0) == []
    assert await tool.search("query", limit=-1) == []
    assert tool.calls == []


async def test_blank_query_skips_fetch(http_client: httpx.AsyncClient) -> None:
    tool = StubAdapter(deps=fast_deps(http_client), items=[make_evidence("one")])
    assert await tool.search("   ") == []
    assert tool.calls == []


async def test_limit_is_clamped_to_max_results(http_client: httpx.AsyncClient) -> None:
    tool = StubAdapter(deps=fast_deps(http_client), items=[make_evidence("one")])
    await tool.search("query", limit=100)
    assert tool.calls == [("query", tool.max_results)]


async def test_cache_hit_skips_fetch_and_slices(http_client: httpx.AsyncClient) -> None:
    items = [make_evidence("one"), make_evidence("two"), make_evidence("three")]
    tool = StubAdapter(deps=fast_deps(http_client, cache=InMemoryCache()), items=items)

    full = await tool.search("query")
    limited = await tool.search("query", limit=1)

    assert len(full) == 3
    assert len(limited) == 1
    assert tool.calls == [("query", 8)]


async def test_more_than_max_results_are_truncated(http_client: httpx.AsyncClient) -> None:
    items = [make_evidence(f"item-{index}") for index in range(25)]
    tool = StubAdapter(deps=fast_deps(http_client, cache=InMemoryCache()), items=items)

    results = await tool.search("query", limit=20)
    assert len(results) == tool.max_results


@respx.mock
async def test_rate_limiter_is_acquired_per_http_attempt(http_client: httpx.AsyncClient) -> None:
    route = respx.get("https://example.com/api").mock(return_value=httpx.Response(429))
    limiter = RecordingLimiter()
    deps = dataclasses.replace(fast_deps(http_client), rate_limiter=limiter)
    tool = StubAdapter(deps=deps, use_http=True, items=[make_evidence("one")])

    assert await tool.search("storm") == []
    assert route.call_count == 3
    assert limiter.acquires == 3


@respx.mock
async def test_rate_limiter_is_not_acquired_on_cache_hits(http_client: httpx.AsyncClient) -> None:
    respx.get("https://example.com/api").mock(return_value=httpx.Response(200, json={"ok": 1}))
    limiter = RecordingLimiter()
    deps = dataclasses.replace(fast_deps(http_client, cache=InMemoryCache()), rate_limiter=limiter)
    tool = StubAdapter(deps=deps, use_http=True, items=[make_evidence("one")])

    await tool.search("query")
    await tool.search("query")
    assert limiter.acquires == 1
