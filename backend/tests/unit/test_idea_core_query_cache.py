"""Unit tests for the bounded query-embedding cache (no DB, no network)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.ideas import service as idea_service
from app.ideas.service import QUERY_EMBEDDING_CACHE_SIZE, cached_query_embedding


class CountingEmbedder:
    """Records every embed call and returns deterministic unit vectors."""

    def __init__(self, dimensions: int = 4) -> None:
        self.calls: list[list[str]] = []
        self._dimensions = dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[1.0] + [0.0] * (self._dimensions - 1) for _ in texts]


class FailingEmbedder:
    """Always raises, to prove failures are never cached."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding backend down")


@pytest.fixture(autouse=True)
def _clean_cache() -> Iterator[None]:
    idea_service._QUERY_EMBEDDING_CACHE.clear()
    yield
    idea_service._QUERY_EMBEDDING_CACHE.clear()


async def test_repeated_queries_embed_once() -> None:
    embedder = CountingEmbedder()
    first = await cached_query_embedding(embedder, "pet care market")
    second = await cached_query_embedding(embedder, "  PET  care  MARKET ")
    twice = await cached_query_embedding(embedder, "pet care market")

    assert first == second == twice
    assert embedder.calls == [["pet care market"]]


async def test_different_queries_miss_the_cache() -> None:
    embedder = CountingEmbedder()
    await cached_query_embedding(embedder, "pets")
    await cached_query_embedding(embedder, "dogs")

    assert embedder.calls == [["pets"], ["dogs"]]


async def test_failures_are_not_cached() -> None:
    failing = FailingEmbedder()
    assert await cached_query_embedding(failing, "pets") is None

    working = CountingEmbedder()
    assert await cached_query_embedding(working, "pets") is not None
    assert working.calls == [["pets"]]


async def test_cache_is_bounded_and_evicts_in_insertion_order() -> None:
    embedder = CountingEmbedder()
    for index in range(QUERY_EMBEDDING_CACHE_SIZE + 5):
        await cached_query_embedding(embedder, f"query {index}")

    assert len(idea_service._QUERY_EMBEDDING_CACHE) == QUERY_EMBEDDING_CACHE_SIZE
    calls_before = len(embedder.calls)

    await cached_query_embedding(embedder, "query 0")
    await cached_query_embedding(embedder, f"query {QUERY_EMBEDDING_CACHE_SIZE + 4}")

    assert len(embedder.calls) == calls_before + 1
