"""Postgres-backed job queue and the analysis enqueuer.

Jobs are claimed with ``SELECT ... FOR UPDATE SKIP LOCKED`` so concurrent
workers never take the same job. Failures requeue with exponential backoff
until ``MAX_JOB_ATTEMPTS`` attempts, then the job is marked failed. While a
claimed job runs, a heartbeat keeps ``locked_at`` fresh so the stale sweep
never steals it from a live worker.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, get_settings
from app.pipeline.models import AnalysisRun, Job, JobStatus, RunStatus

MAX_JOB_ATTEMPTS = 3
JOB_HEARTBEAT_SECONDS = 60.0
_BACKOFF_CAP_SECONDS = 60.0


def backoff_seconds(attempts: int) -> float:
    """Backoff before retrying a job that has failed ``attempts`` times."""
    return min(_BACKOFF_CAP_SECONDS, float(2 ** max(1, attempts)))


def _utcnow() -> datetime:
    return datetime.now(UTC)


class JobQueue:
    """Claim, complete, and fail jobs in the ``jobs`` table."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def enqueue(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        run_after: datetime | None = None,
        session: AsyncSession | None = None,
    ) -> Job:
        """Insert a queued job.

        With ``session`` the job is added to the caller's transaction and only
        flushed, so it commits atomically with the caller's work. Without it a
        short-lived session commits the insert immediately.
        """
        if session is not None:
            job = Job(kind=kind, payload=payload, run_after=run_after or _utcnow())
            session.add(job)
            await session.flush()
            return job
        async with self._session_factory() as own_session:
            job = Job(kind=kind, payload=payload, run_after=run_after or _utcnow())
            own_session.add(job)
            await own_session.commit()
            return job

    async def claim_next(self, worker_id: str) -> Job | None:
        """Lock and return the oldest due queued job, incrementing its attempts."""
        async with self._session_factory() as session:
            statement = (
                select(Job)
                .where(Job.status == JobStatus.queued, Job.run_after <= _utcnow())
                .order_by(Job.run_after, Job.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            job = (await session.execute(statement)).scalar_one_or_none()
            if job is None:
                return None
            job.status = JobStatus.running
            job.locked_by = worker_id
            job.locked_at = _utcnow()
            job.attempts += 1
            await session.commit()
            return job

    async def complete(self, job: Job) -> None:
        """Mark a job done and release its lock."""
        async with self._session_factory() as session:
            row = await session.get(Job, job.id)
            if row is None:
                return
            row.status = JobStatus.done
            row.locked_by = None
            row.locked_at = None
            row.updated_at = _utcnow()
            await session.commit()

    async def fail(self, job: Job, error: str, *, terminal: bool = False) -> bool:
        """Requeue with backoff, or mark failed once attempts are exhausted.

        Returns ``True`` when the job is terminally failed, so the caller can
        close out the run the job was backing. ``terminal=True`` fails at once.
        """
        async with self._session_factory() as session:
            row = await session.get(Job, job.id)
            if row is None:
                return True
            row.last_error = error
            row.locked_by = None
            row.locked_at = None
            row.updated_at = _utcnow()
            if terminal or row.attempts >= MAX_JOB_ATTEMPTS:
                row.status = JobStatus.failed
                await session.commit()
                return True
            row.status = JobStatus.queued
            row.run_after = _utcnow() + timedelta(seconds=backoff_seconds(row.attempts))
            await session.commit()
            return False

    async def heartbeat(self, job: Job, *, interval_seconds: float = JOB_HEARTBEAT_SECONDS) -> None:
        """Refresh ``locked_at`` while ``job`` runs, stopping once it is not ours.

        Cancelled by the caller when the job finishes. The conditional update
        means a job that was requeued and re-claimed elsewhere is never touched.
        """
        while True:
            await asyncio.sleep(interval_seconds)
            async with self._session_factory() as session:
                result = cast(
                    "CursorResult[Any]",
                    await session.execute(
                        update(Job)
                        .where(
                            Job.id == job.id,
                            Job.status == JobStatus.running,
                            Job.locked_by == job.locked_by,
                        )
                        .values(locked_at=_utcnow(), updated_at=_utcnow())
                    ),
                )
                await session.commit()
                if not result.rowcount:
                    return

    async def requeue_stale(self, stale_seconds: float) -> int:
        """Return jobs stuck in ``running`` (worker died) to the queue.

        A single conditional UPDATE re-checks ``locked_at`` when it runs, so a
        fresh heartbeat or a concurrent claim is never clobbered.
        """
        cutoff = _utcnow() - timedelta(seconds=stale_seconds)
        async with self._session_factory() as session:
            result = cast(
                "CursorResult[Any]",
                await session.execute(
                    update(Job)
                    .where(
                        Job.status == JobStatus.running,
                        Job.locked_at.is_not(None),
                        Job.locked_at < cutoff,
                    )
                    .values(
                        status=JobStatus.queued,
                        locked_by=None,
                        locked_at=None,
                        run_after=_utcnow(),
                        updated_at=_utcnow(),
                    )
                ),
            )
            await session.commit()
            return int(result.rowcount or 0)


class SqlAnalysisEnqueuer:
    """``AnalysisEnqueuer`` persisting the run and its job in the caller's session."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings | None = None,
    ) -> None:
        self._queue = JobQueue(session_factory)
        self._settings = settings if settings is not None else get_settings()

    async def enqueue_analysis(
        self,
        session: AsyncSession,
        idea_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> None:
        """Create the analysis run and add its job without committing.

        The run exists before any worker claims the job, so a retry or a
        requeue after a crash resumes the same run instead of paying for the
        pipeline again.
        """
        run = AnalysisRun(
            idea_id=idea_id,
            idea_version_id=version_id,
            status=RunStatus.pending,
            step="refine",
            cost_cap_usd=Decimal(str(self._settings.run_cost_cap_usd)),
            started_at=datetime.now(UTC),
        )
        session.add(run)
        await session.flush()
        await self._queue.enqueue(
            "analyze_idea",
            {"idea_id": str(idea_id), "version_id": str(version_id), "run_id": str(run.id)},
            session=session,
        )
