"""Integration tests for IdeaService against a real Postgres.

These are auto-skipped by ``tests/conftest.py`` when Postgres is unreachable.
"""

from __future__ import annotations

import math
import time
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ideas import AnalysisEnqueuer, Embedder
from app.ideas.models import IdeaSearch, IdeaStatus, IdeaVerdict
from app.ideas.schemas import (
    IdeaCreate,
    IdeaUpdate,
    IdeaVersionCreate,
    SearchMode,
)
from app.ideas.service import IdeaNotFound, IdeaService
from app.ideas.testing import FakeEmbedder

pytestmark = pytest.mark.integration


class FailingEmbedder:
    """Embedder that always fails, to prove embedding errors never break writes."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding backend down")


class RecordingEnqueuer:
    """AnalysisEnqueuer test double that records the calls it receives."""

    def __init__(self) -> None:
        self.calls: list[tuple[AsyncSession, uuid.UUID, uuid.UUID]] = []

    async def enqueue_analysis(
        self, session: AsyncSession, idea_id: uuid.UUID, version_id: uuid.UUID
    ) -> None:
        self.calls.append((session, idea_id, version_id))


def _service(
    session: AsyncSession,
    *,
    embedder: Embedder | None = None,
    enqueuer: AnalysisEnqueuer | None = None,
) -> IdeaService:
    active = embedder if embedder is not None else FakeEmbedder()
    return IdeaService(session, active, enqueuer)


async def test_create_with_only_raw_input(db_session: AsyncSession) -> None:
    service = _service(db_session)
    detail = await service.create(IdeaCreate(raw_input="  A dog walking app for pet owners  "))
    assert detail.title == "A dog walking app for pet owners"
    assert detail.status is IdeaStatus.queued
    assert detail.latest_version.number == 1
    assert len(detail.versions) == 1
    assert detail.latest_version.raw_input == "  A dog walking app for pet owners  "
    assert detail.tags == []


async def test_create_without_analyze_is_draft(db_session: AsyncSession) -> None:
    service = _service(db_session)
    detail = await service.create(IdeaCreate(raw_input="quiet idea", analyze=False))
    assert detail.status is IdeaStatus.draft


async def test_empty_and_oversize_raw_input_are_rejected(db_session: AsyncSession) -> None:
    with pytest.raises(ValidationError):
        IdeaCreate(raw_input="")
    with pytest.raises(ValidationError):
        IdeaCreate(raw_input="x" * 5001)


async def test_enqueuer_runs_in_the_same_session(db_session: AsyncSession) -> None:
    enqueuer = RecordingEnqueuer()
    service = _service(db_session, enqueuer=enqueuer)
    detail = await service.create(IdeaCreate(raw_input="queued idea"))
    assert len(enqueuer.calls) == 1
    session, idea_id, version_id = enqueuer.calls[0]
    assert session is db_session
    assert idea_id == detail.id
    assert version_id == detail.latest_version.id

    await service.add_version(detail.id, IdeaVersionCreate(raw_input="second draft"))
    assert len(enqueuer.calls) == 2
    assert enqueuer.calls[1][1] == detail.id


async def test_versions_are_gapless_and_old_versions_readable(
    db_session: AsyncSession,
) -> None:
    service = _service(db_session)
    created = await service.create(IdeaCreate(raw_input="v1 raw", analyze=False))
    await service.add_version(created.id, IdeaVersionCreate(raw_input="v2 raw", context={"x": 1}))
    detail = await service.add_version(created.id, IdeaVersionCreate(raw_input="v3 raw"))
    assert [version.number for version in detail.versions] == [1, 2, 3]
    assert [version.raw_input for version in detail.versions] == ["v1 raw", "v2 raw", "v3 raw"]
    assert detail.versions[1].context == {"x": 1}
    assert detail.latest_version.number == 3


async def test_keyword_search_finds_exact_term(db_session: AsyncSession) -> None:
    service = _service(db_session)
    await service.create(
        IdeaCreate(raw_input="A marketplace for vintage bicycles in Berlin", analyze=False)
    )
    await service.create(
        IdeaCreate(raw_input="An AI assistant that files your taxes", analyze=False)
    )
    result = await service.search(q="bicycles", mode=SearchMode.keyword, limit=10)
    assert len(result.items) == 1
    assert result.items[0].title.startswith("A marketplace")


async def test_semantic_search_finds_dog_walking_for_pets(db_session: AsyncSession) -> None:
    service = _service(db_session)
    target = await service.create(
        IdeaCreate(raw_input="A dog walking app for pet owners", analyze=False)
    )
    await service.create(
        IdeaCreate(raw_input="B2B payroll automation for enterprises", analyze=False)
    )
    result = await service.search(q="pets", mode=SearchMode.semantic, limit=10)
    assert result.items
    assert result.items[0].id == target.id


async def test_hybrid_search_ranks_keyword_and_semantic_matches(
    db_session: AsyncSession,
) -> None:
    service = _service(db_session)
    aquaponics = await service.create(
        IdeaCreate(raw_input="Indoor aquaponics kits for schools", analyze=False)
    )
    await service.create(IdeaCreate(raw_input="Hydroponic garden starter kit", analyze=False))
    await service.create(IdeaCreate(raw_input="Mobile game for cats", analyze=False))
    result = await service.search(q="aquaponics kits", mode=SearchMode.hybrid, limit=10)
    assert result.items
    assert result.items[0].id == aquaponics.id


async def test_semantic_search_falls_back_to_keyword_with_failing_embedder(
    db_session: AsyncSession,
) -> None:
    service = IdeaService(db_session, FailingEmbedder())
    await service.create(IdeaCreate(raw_input="Aquaponics kits for schools", analyze=False))
    result = await service.search(q="aquaponics", mode=SearchMode.semantic, limit=10)
    assert len(result.items) == 1


class CountingQueryEmbedder:
    """Wraps FakeEmbedder and records the texts of every embed call."""

    def __init__(self) -> None:
        self._inner = FakeEmbedder()
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return await self._inner.embed(texts)

    @property
    def query_calls(self) -> list[list[str]]:
        return [call for call in self.calls if call == ["pet care market"]]


async def test_repeated_searches_embed_the_query_once(db_session: AsyncSession) -> None:
    embedder = CountingQueryEmbedder()
    service = IdeaService(db_session, embedder)
    await service.create(IdeaCreate(raw_input="pet care marketplace", analyze=False))

    first = await service.search(q="pet care market", mode=SearchMode.hybrid, limit=10)
    second = await service.search(q="pet care market", mode=SearchMode.hybrid, limit=10)

    assert first.items and second.items
    assert len(embedder.query_calls) == 1


async def test_different_queries_each_embed(db_session: AsyncSession) -> None:
    embedder = CountingQueryEmbedder()
    service = IdeaService(db_session, embedder)
    await service.create(IdeaCreate(raw_input="pet care marketplace", analyze=False))

    await service.search(q="pet care market", mode=SearchMode.hybrid, limit=10)
    await service.search(q="veterinary software", mode=SearchMode.hybrid, limit=10)

    assert embedder.query_calls == [["pet care market"]]
    assert ["veterinary software"] in embedder.calls


async def test_archived_hidden_by_default(db_session: AsyncSession) -> None:
    service = _service(db_session)
    keep = await service.create(IdeaCreate(raw_input="visible idea", analyze=False))
    gone = await service.create(IdeaCreate(raw_input="archived idea", analyze=False))
    archived = await service.archive(gone.id)
    assert archived.archived_at is not None
    default = await service.search()
    assert {item.id for item in default.items} == {keep.id}
    only_archived = await service.search(archived=True)
    assert {item.id for item in only_archived.items} == {gone.id}
    restored = await service.archive(gone.id, archived=False)
    assert restored.archived_at is None


async def test_embedding_failure_does_not_fail_create_and_can_be_retried(
    db_session: AsyncSession,
) -> None:
    failing = IdeaService(db_session, FailingEmbedder())
    detail = await failing.create(IdeaCreate(raw_input="fragile idea", analyze=False))
    row = await db_session.get(IdeaSearch, detail.id)
    assert row is not None
    assert row.tsv is not None
    assert row.embedding is None

    assert await failing.refresh_search_index(detail.id) is False

    working = _service(db_session)
    assert await working.refresh_search_index(detail.id) is True
    await db_session.refresh(row)
    assert row.embedding is not None


async def test_cursor_pagination_is_stable_under_inserts(db_session: AsyncSession) -> None:
    service = _service(db_session)
    created = [
        await service.create(IdeaCreate(raw_input=f"paged idea {index}", analyze=False))
        for index in range(12)
    ]
    first_page = await service.search(limit=5)
    assert len(first_page.items) == 5
    assert first_page.next_cursor is not None

    inserted = await service.create(IdeaCreate(raw_input="inserted mid pagination", analyze=False))

    seen = [item.id for item in first_page.items]
    cursor = first_page.next_cursor
    while cursor is not None:
        page = await service.search(limit=5, cursor=cursor)
        seen.extend(item.id for item in page.items)
        cursor = page.next_cursor

    assert len(seen) == len(set(seen)) == 12
    assert set(seen) == {idea.id for idea in created}
    assert inserted.id not in seen


async def test_ranked_search_cursor_pagination(db_session: AsyncSession) -> None:
    service = _service(db_session)
    for index in range(9):
        await service.create(IdeaCreate(raw_input=f"widget idea number {index}", analyze=False))
    first = await service.search(q="widget", mode=SearchMode.hybrid, limit=4)
    assert len(first.items) == 4
    assert first.next_cursor is not None
    seen = [item.id for item in first.items]
    cursor = first.next_cursor
    while cursor is not None:
        page = await service.search(q="widget", mode=SearchMode.hybrid, limit=4, cursor=cursor)
        seen.extend(item.id for item in page.items)
        cursor = page.next_cursor
    assert len(seen) == len(set(seen)) == 9


async def test_tags_with_counts_and_full_replace(db_session: AsyncSession) -> None:
    service = _service(db_session)
    first = await service.create(IdeaCreate(raw_input="idea a", tags=["ai", "ml"], analyze=False))
    second = await service.create(IdeaCreate(raw_input="idea b", tags=["ai", "ml"], analyze=False))
    await service.create(IdeaCreate(raw_input="idea c", tags=["ai"], analyze=False))

    counts = {tag.name: tag.count for tag in await service.list_tags()}
    assert counts == {"ai": 3, "ml": 2}

    updated = await service.update(second.id, IdeaUpdate(tags=["finance"]))
    assert updated.tags == ["finance"]
    counts = {tag.name: tag.count for tag in await service.list_tags()}
    assert counts == {"ai": 2, "ml": 1, "finance": 1}

    cleared = await service.update(first.id, IdeaUpdate(tags=[]))
    assert cleared.tags == []


async def test_update_pinned_title_and_search_refresh(db_session: AsyncSession) -> None:
    service = _service(db_session)
    idea = await service.create(
        IdeaCreate(raw_input="Tiny farm robots", tags=["hardware"], analyze=False)
    )
    updated = await service.update(idea.id, IdeaUpdate(pinned=True, title="Farm robots"))
    assert updated.pinned is True
    assert updated.title == "Farm robots"
    assert updated.tags == ["hardware"]

    hits = await service.search(q="Farm robots", mode=SearchMode.keyword)
    assert [item.id for item in hits.items] == [idea.id]


async def test_analysis_fields_status_and_brief(db_session: AsyncSession) -> None:
    service = _service(db_session)
    idea = await service.create(IdeaCreate(raw_input="Tiny farm robots", analyze=False))

    await service.set_analysis_fields(
        idea.id,
        verdict=IdeaVerdict.pursue,
        overall_score=77.5,
        category="hardware",
        title="Farm robots",
    )
    detail = await service.get(idea.id)
    assert detail.verdict is IdeaVerdict.pursue
    assert detail.overall_score == 77.5
    assert detail.category == "hardware"
    assert detail.title == "Farm robots"

    keyword = await service.search(q="Farm robots", mode=SearchMode.keyword)
    assert [item.id for item in keyword.items] == [idea.id]

    await service.set_version_brief(idea.id, 1, {"problem": "zebra labour shortage"})
    zebra = await service.search(q="zebra", mode=SearchMode.keyword)
    assert [item.id for item in zebra.items] == [idea.id]

    await service.set_status(idea.id, IdeaStatus.analyzing)
    assert (await service.get(idea.id)).status is IdeaStatus.analyzing


async def test_filters_apply_to_plain_list(db_session: AsyncSession) -> None:
    service = _service(db_session)
    first = await service.create(IdeaCreate(raw_input="plain one", tags=["ai"], analyze=False))
    second = await service.create(IdeaCreate(raw_input="plain two", analyze=False))
    await service.set_analysis_fields(
        second.id,
        verdict=IdeaVerdict.park,
        overall_score=20.0,
        category="consumer",
    )
    await service.update(second.id, IdeaUpdate(pinned=True))

    by_tag = await service.search(tag="ai")
    assert {item.id for item in by_tag.items} == {first.id}
    by_pinned = await service.search(pinned=True)
    assert {item.id for item in by_pinned.items} == {second.id}
    by_verdict = await service.search(verdict=IdeaVerdict.park)
    assert {item.id for item in by_verdict.items} == {second.id}
    by_score = await service.search(score_min=50.0)
    assert by_score.items == []
    by_score_max = await service.search(score_max=50.0, category="consumer")
    assert {item.id for item in by_score_max.items} == {second.id}


async def test_similar_returns_nearest_excluding_self(db_session: AsyncSession) -> None:
    service = _service(db_session)
    target = await service.create(
        IdeaCreate(raw_input="A dog walking app for pet owners", analyze=False)
    )
    related = await service.create(
        IdeaCreate(raw_input="Dog grooming service for pets", analyze=False)
    )
    await service.create(IdeaCreate(raw_input="Quantum computing research platform", analyze=False))

    results = await service.similar(target.id, limit=5)
    assert results
    assert all(result.id != target.id for result in results)
    assert results[0].id == related.id
    assert 0.0 <= results[0].distance <= 2.0


async def test_similar_without_embedding_returns_empty(db_session: AsyncSession) -> None:
    failing = IdeaService(db_session, FailingEmbedder())
    idea = await failing.create(IdeaCreate(raw_input="no vector here", analyze=False))
    assert await failing.similar(idea.id) == []


async def test_missing_idea_raises_not_found(db_session: AsyncSession) -> None:
    service = _service(db_session)
    with pytest.raises(IdeaNotFound):
        await service.get(uuid.uuid4())
    with pytest.raises(IdeaNotFound):
        await service.update(uuid.uuid4(), IdeaUpdate(pinned=True))


async def test_hybrid_search_over_two_hundred_ideas_completes(db_session: AsyncSession) -> None:
    """Modest smoke benchmark: 200 seeded ideas, completion and timing reported."""
    service = _service(db_session)
    for index in range(200):
        await service.create(
            IdeaCreate(raw_input=f"seed idea {index} about topic {index % 10}", analyze=False)
        )
    started = time.perf_counter()
    result = await service.search(q="idea 42", mode=SearchMode.hybrid, limit=30)
    elapsed = time.perf_counter() - started
    assert result.items
    assert result.items[0].title == "seed idea 42 about topic 2"
    print(f"\n[benchmark] hybrid search over 200 ideas: {elapsed * 1000:.1f} ms")


def _p95(timings: list[float]) -> float:
    """Nearest-rank 95th percentile of the measured latencies in milliseconds."""
    ordered = sorted(timings)
    rank = math.ceil(0.95 * len(ordered))
    return ordered[max(0, rank - 1)]


async def test_hybrid_search_p95_under_300ms_across_one_thousand_ideas(
    db_session: AsyncSession,
) -> None:
    """Spec criterion: hybrid search p95 < 300 ms over 1,000 seeded ideas.

    Seeds through ``IdeaService`` with the ``FakeEmbedder``, then times 20
    hybrid queries and adds keyword, semantic, and filtered queries. Latency
    budgets are asserted, not printed: p95 must stay under the 300 ms bound.
    """
    service = _service(db_session)
    topics = (
        "pets",
        "finance",
        "health",
        "education",
        "logistics",
        "retail",
        "energy",
        "travel",
        "agriculture",
        "security",
    )
    for index in range(1000):
        await service.create(
            IdeaCreate(
                raw_input=f"seed idea {index} about {topics[index % len(topics)]}",
                analyze=False,
            )
        )

    hybrid_timings: list[float] = []
    for index in range(20):
        started = time.perf_counter()
        result = await service.search(q=f"idea {index}", mode=SearchMode.hybrid, limit=30)
        hybrid_timings.append((time.perf_counter() - started) * 1000)
        assert result.items

    keyword = await service.search(q="idea 42", mode=SearchMode.keyword, limit=10)
    semantic = await service.search(q="pets", mode=SearchMode.semantic, limit=10)
    filtered = await service.search(
        q="seed idea", mode=SearchMode.hybrid, status=IdeaStatus.draft, limit=10
    )
    assert keyword.items
    assert keyword.items[0].title == "seed idea 42 about health"
    assert semantic.items
    assert filtered.items

    p95 = _p95(hybrid_timings)
    print(
        f"\n[benchmark] 1000 ideas hybrid search: p95={p95:.1f} ms "
        f"(min={min(hybrid_timings):.1f} ms, max={max(hybrid_timings):.1f} ms)"
    )
    assert p95 < 300.0
