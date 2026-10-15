"""Integration tests for the Postgres job queue (SKIP LOCKED, backoff, stale)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ideas import IdeaCreate, IdeaService
from app.ideas.testing import FakeEmbedder
from app.pipeline.jobs import JobQueue
from app.pipeline.models import Job, JobStatus
from app.pipeline.worker import reindex_ideas

pytestmark = pytest.mark.integration


async def _load_job(session_factory: async_sessionmaker[AsyncSession], job_id: uuid.UUID) -> Job:
    async with session_factory() as session:
        row = await session.get(Job, job_id)
        assert row is not None
        return row


async def _backdate(
    session_factory: async_sessionmaker[AsyncSession], job_id: uuid.UUID, **values: object
) -> None:
    async with session_factory() as session:
        row = await session.get(Job, job_id)
        assert row is not None
        for key, value in values.items():
            setattr(row, key, value)
        await session.commit()


async def test_two_concurrent_claims_get_different_jobs(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    queue = JobQueue(db_session_factory)
    await queue.enqueue("kind_a", {"n": 1})
    await queue.enqueue("kind_b", {"n": 2})

    first, second = await asyncio.gather(queue.claim_next("w1"), queue.claim_next("w2"))
    assert first is not None
    assert second is not None
    assert first.id != second.id
    assert {first.payload["n"], second.payload["n"]} == {1, 2}

    async with db_session_factory() as session:
        rows = (await session.execute(select(Job))).scalars().all()
        assert all(row.status is JobStatus.running for row in rows)
        assert {row.locked_by for row in rows} == {"w1", "w2"}
        assert all(row.attempts == 1 for row in rows)


async def test_claim_next_returns_none_when_empty(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    assert await JobQueue(db_session_factory).claim_next("w1") is None


async def test_complete_marks_done_and_frees_the_lock(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    queue = JobQueue(db_session_factory)
    await queue.enqueue("kind", {})
    claimed = await queue.claim_next("w1")
    assert claimed is not None
    await queue.complete(claimed)

    stored = await _load_job(db_session_factory, claimed.id)
    assert stored.status is JobStatus.done
    assert stored.locked_by is None
    assert stored.locked_at is None
    assert await queue.claim_next("w2") is None


async def test_requeue_stale_returns_abandoned_jobs(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    queue = JobQueue(db_session_factory)
    await queue.enqueue("kind", {"run": "x"})
    claimed = await queue.claim_next("dead-worker")
    assert claimed is not None

    assert await queue.requeue_stale(3600) == 0
    await _backdate(
        db_session_factory,
        claimed.id,
        locked_at=datetime.now(UTC) - timedelta(seconds=120),
    )
    assert await queue.requeue_stale(30) == 1

    stored = await _load_job(db_session_factory, claimed.id)
    assert stored.status is JobStatus.queued
    assert stored.locked_by is None

    reclaimed = await queue.claim_next("w2")
    assert reclaimed is not None
    assert reclaimed.id == claimed.id
    assert reclaimed.attempts == 2


async def test_requeue_stale_does_not_clobber_a_freshly_heartbeated_job(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    queue = JobQueue(db_session_factory)
    await queue.enqueue("kind", {})
    claimed = await queue.claim_next("w1")
    assert claimed is not None
    await _backdate(
        db_session_factory,
        claimed.id,
        locked_at=datetime.now(UTC) - timedelta(seconds=120),
    )

    async with db_session_factory() as blocker:
        row = await blocker.get(Job, claimed.id, with_for_update=True)
        assert row is not None
        row.locked_at = datetime.now(UTC)
        requeue = asyncio.create_task(queue.requeue_stale(30))
        await asyncio.sleep(0.2)
        await blocker.commit()

    assert await requeue == 0
    stored = await _load_job(db_session_factory, claimed.id)
    assert stored.status is JobStatus.running
    assert stored.locked_by == "w1"


async def test_heartbeat_refreshes_locked_at_until_the_job_finishes(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    queue = JobQueue(db_session_factory)
    await queue.enqueue("kind", {})
    claimed = await queue.claim_next("w1")
    assert claimed is not None
    await _backdate(
        db_session_factory,
        claimed.id,
        locked_at=datetime.now(UTC) - timedelta(seconds=120),
    )

    heartbeat = asyncio.create_task(queue.heartbeat(claimed, interval_seconds=0.05))
    try:
        await asyncio.sleep(0.2)
        stored = await _load_job(db_session_factory, claimed.id)
        assert stored.locked_at is not None
        assert (datetime.now(UTC) - stored.locked_at).total_seconds() < 60
        assert not heartbeat.done()
    finally:
        await queue.complete(claimed)
        await asyncio.wait_for(heartbeat, timeout=2.0)


async def test_fail_requeues_with_backoff_then_fails_after_max_attempts(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    queue = JobQueue(db_session_factory)
    await queue.enqueue("kind", {})
    job_id: uuid.UUID | None = None

    for expected_attempt in (1, 2):
        claimed = await queue.claim_next("w1")
        assert claimed is not None
        job_id = claimed.id
        assert claimed.attempts == expected_attempt
        failed_at = datetime.now(UTC)
        await queue.fail(claimed, f"boom {expected_attempt}")

        stored = await _load_job(db_session_factory, claimed.id)
        assert stored.status is JobStatus.queued
        assert stored.last_error == f"boom {expected_attempt}"
        assert stored.run_after > failed_at
        await _backdate(
            db_session_factory, claimed.id, run_after=datetime.now(UTC) - timedelta(seconds=1)
        )

    claimed = await queue.claim_next("w1")
    assert claimed is not None
    assert claimed.id == job_id
    assert claimed.attempts == 3
    await queue.fail(claimed, "boom 3")

    stored = await _load_job(db_session_factory, claimed.id)
    assert stored.status is JobStatus.failed
    assert stored.attempts == 3
    assert stored.last_error == "boom 3"
    assert await queue.claim_next("w2") is None


async def test_enqueue_with_session_defers_the_commit(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    queue = JobQueue(db_session_factory)
    async with db_session_factory() as session:
        await queue.enqueue("kind", {"n": 1}, session=session)
        assert session.in_transaction()
        await session.rollback()

    async with db_session_factory() as session:
        assert (await session.execute(select(Job))).scalars().all() == []


class _BrokenEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding provider down")


async def test_reindex_sweep_refreshes_missing_embeddings(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        service = IdeaService(session, _BrokenEmbedder())
        detail = await service.create(IdeaCreate(raw_input="An idea about pets.", analyze=False))

    async with db_session_factory() as session:
        missing = await session.scalar(
            text("SELECT count(*) FROM idea_search WHERE idea_id = :idea AND embedding IS NULL"),
            {"idea": detail.id},
        )
        assert missing == 1

    refreshed = await reindex_ideas(session_factory=db_session_factory, embedder=FakeEmbedder())
    assert refreshed == 1

    async with db_session_factory() as session:
        embedded = await session.scalar(
            text("SELECT embedding IS NOT NULL FROM idea_search WHERE idea_id = :idea"),
            {"idea": detail.id},
        )
        assert embedded is True
