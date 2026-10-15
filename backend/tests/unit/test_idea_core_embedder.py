"""Unit tests for the deterministic FakeEmbedder (no database, no network)."""

from __future__ import annotations

import math

import pytest

from app.ideas.testing import FakeEmbedder


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _norm(vector: list[float]) -> float:
    return math.sqrt(sum(component * component for component in vector))


async def test_same_text_same_vector() -> None:
    embedder = FakeEmbedder(dimensions=64)
    first, second = await embedder.embed(["dog walking app", "dog walking app"])
    assert first == second


async def test_different_texts_produce_different_vectors() -> None:
    embedder = FakeEmbedder(dimensions=64)
    first, second = await embedder.embed(["dog walking app", "quantum physics research"])
    assert first != second


async def test_vectors_are_unit_norm() -> None:
    embedder = FakeEmbedder(dimensions=128)
    (vector,) = await embedder.embed(["a marketplace for vintage bicycles"])
    assert _norm(vector) == pytest.approx(1.0, abs=1e-9)


async def test_empty_text_still_returns_a_unit_vector() -> None:
    embedder = FakeEmbedder(dimensions=32)
    (vector,) = await embedder.embed([""])
    assert len(vector) == 32
    assert _norm(vector) == pytest.approx(1.0, abs=1e-9)


async def test_dimensions_are_respected() -> None:
    embedder = FakeEmbedder(dimensions=17)
    (vector,) = await embedder.embed(["hello"])
    assert len(vector) == 17
    assert embedder.dimensions == 17


async def test_shared_tokens_increase_similarity() -> None:
    embedder = FakeEmbedder()
    idea, related, unrelated, query = await embedder.embed(
        [
            "dog walking app for pet owners",
            "dog grooming service for pets",
            "quantum physics research platform",
            "pets",
        ]
    )
    assert _cosine(idea, query) > _cosine(unrelated, query)
    assert _cosine(related, query) > _cosine(unrelated, query)


async def test_plurals_match_singulars() -> None:
    embedder = FakeEmbedder()
    singular, plural = await embedder.embed(["pet owner", "pets owners"])
    assert _cosine(singular, plural) > 0.99


async def test_openai_embedder_without_api_key_raises_only_on_use() -> None:
    from app.ideas import EmbeddingError, OpenAIEmbedder

    embedder = OpenAIEmbedder(api_key="", model="text-embedding-3-small", dimensions=1536)
    with pytest.raises(EmbeddingError, match="OPENAI_API_KEY"):
        await embedder.embed(["hello"])
