"""Unit tests for the in-memory and null caches."""

from __future__ import annotations

from app.research.cache import InMemoryCache, NullCache
from app.research.contract import Evidence


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def make_evidence(title: str = "t") -> Evidence:
    return Evidence(source="web", url="https://example.com/x", title=title, snippet="s")


async def test_roundtrip() -> None:
    cache = InMemoryCache()
    items = [make_evidence("one"), make_evidence("two")]
    await cache.set("web:q", items, ttl_seconds=60)
    got = await cache.get("web:q")
    assert got is not None
    assert [item.title for item in got] == ["one", "two"]


async def test_miss_returns_none() -> None:
    assert await InMemoryCache().get("web:missing") is None


async def test_entry_expires() -> None:
    clock = FakeClock()
    cache = InMemoryCache(clock=clock)
    await cache.set("web:q", [make_evidence()], ttl_seconds=10)
    clock.now += 11
    assert await cache.get("web:q") is None


async def test_entry_expires_exactly_at_ttl_boundary() -> None:
    clock = FakeClock()
    cache = InMemoryCache(clock=clock)
    await cache.set("web:q", [make_evidence()], ttl_seconds=10)
    clock.now += 10
    assert await cache.get("web:q") is None


async def test_returned_list_is_a_copy() -> None:
    cache = InMemoryCache()
    await cache.set("web:q", [make_evidence()], ttl_seconds=10)
    first = await cache.get("web:q")
    assert first is not None
    first.clear()
    second = await cache.get("web:q")
    assert second is not None
    assert len(second) == 1


async def test_null_cache_never_stores() -> None:
    cache = NullCache()
    await cache.set("web:q", [make_evidence()], ttl_seconds=10)
    assert await cache.get("web:q") is None
