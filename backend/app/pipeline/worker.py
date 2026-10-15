"""The pipeline worker: claim one job, dispatch it, and keep the loop honest.

``run_once`` claims and processes a single job. ``run_forever`` polls, requeues
stale jobs, and periodically re-embeds ideas whose search rows are missing an
embedding.

``tools`` may be a mapping of ready tools (used by tests and simple callers) or
a callable ``meter -> tools`` (used by ``app.worker``) so research-tool spend is
metered into the same per-run :class:`~app.cost.CostMeter` the orchestrator
uses for LLM spend. ``gate_factory`` optionally builds the per-run gate from
that meter (production wires Jev pricing there); without it the shared
``Gate`` is used. Jobs that terminally fail mark their run ``failed`` with the
error; ``InvalidRunState`` is non-retryable and fails the job at once.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable, Mapping
from contextlib import suppress
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from pydantic_ai.models import Model
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.cost import CostMeter
from app.ideas import Embedder, IdeaNotFound, IdeaService
from app.jev import Gate
from app.obs import get_logger
from app.pipeline.jobs import JobQueue
from app.pipeline.models import TERMINAL_RUN_STATUSES, AnalysisRun, Job, RunStatus
from app.pipeline.orchestrator import InvalidRunState, JevAsker, Orchestrator, ToolsLike

logger = get_logger(__name__)

REINDEX_BATCH_SIZE = 20
REINDEX_INTERVAL_SECONDS = 300.0


async def run_once(
    worker_id: str,
    *,
    settings: Settings,
    gate: Gate,
    tools: ToolsLike,
    embedder: Embedder | None,
    session_factory: async_sessionmaker[AsyncSession],
    jev: JevAsker | None = None,
    models: Mapping[str, Model | str | None] | None = None,
    gate_factory: Callable[[CostMeter], Gate] | None = None,
) -> bool:
    """Claim and process one job; returns ``False`` when the queue is empty.

    ``models`` overrides the per-step agents (tests inject fakes; production
    leaves it ``None`` and agents use the ``provider:model`` strings from
    settings). While the job executes, a background heartbeat keeps its lock
    fresh; it is cancelled and awaited before the job is completed or failed.
    """
    queue = JobQueue(session_factory)
    job = await queue.claim_next(worker_id)
    if job is None:
        return False
    logger.info("claimed job %s kind=%s attempts=%s", job.id, job.kind, job.attempts)
    heartbeat = asyncio.create_task(queue.heartbeat(job))
    try:
        try:
            await _dispatch(
                job,
                settings=settings,
                gate=gate,
                tools=tools,
                embedder=embedder,
                session_factory=session_factory,
                jev=jev,
                models=models,
                gate_factory=gate_factory,
            )
        except InvalidRunState as exc:
            logger.error("job %s is not runnable: %s", job.id, exc)
            await queue.fail(job, f"{type(exc).__name__}: {exc}", terminal=True)
            return True
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            logger.error("job %s failed: %s", job.id, exc, exc_info=True)
            if await queue.fail(job, error):
                await _fail_run_for_job(job, error, session_factory)
            return True
        await queue.complete(job)
        return True
    finally:
        heartbeat.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat


async def _fail_run_for_job(
    job: Job,
    error: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Mark the run of a terminally failed job as failed; terminal runs stay as-is."""
    raw = job.payload.get("run_id")
    if raw is None:
        return
    async with session_factory() as session:
        run = await session.get(AnalysisRun, uuid.UUID(str(raw)))
        if run is None or run.status in TERMINAL_RUN_STATUSES:
            return
        run.status = RunStatus.failed
        run.error = error
        run.finished_at = datetime.now(UTC)
        await session.commit()
        logger.info("run %s marked failed after job %s exhausted retries", run.id, job.id)


async def _dispatch(
    job: Job,
    *,
    settings: Settings,
    gate: Gate,
    tools: ToolsLike,
    embedder: Embedder | None,
    session_factory: async_sessionmaker[AsyncSession],
    jev: JevAsker | None,
    models: Mapping[str, Model | str | None] | None,
    gate_factory: Callable[[CostMeter], Gate] | None,
) -> None:
    if job.kind == "analyze_idea":
        await _analyze_idea(
            job,
            settings=settings,
            gate=gate,
            tools=tools,
            embedder=embedder,
            session_factory=session_factory,
            jev=jev,
            models=models,
            gate_factory=gate_factory,
        )
    elif job.kind == "rerun_run":
        await _rerun_run(
            job,
            settings=settings,
            gate=gate,
            tools=tools,
            embedder=embedder,
            session_factory=session_factory,
            jev=jev,
            models=models,
            gate_factory=gate_factory,
        )
    elif job.kind == "resume_run":
        await _resume_run(
            job,
            settings=settings,
            gate=gate,
            tools=tools,
            embedder=embedder,
            session_factory=session_factory,
            jev=jev,
            models=models,
            gate_factory=gate_factory,
        )
    elif job.kind == "reindex_ideas":
        await reindex_ideas(session_factory=session_factory, embedder=embedder)
    else:
        raise ValueError(f"unknown job kind {job.kind!r}")


async def _create_run(
    idea_id: uuid.UUID,
    version_id: uuid.UUID,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> AnalysisRun:
    async with session_factory() as session:
        run = AnalysisRun(
            idea_id=idea_id,
            idea_version_id=version_id,
            status=RunStatus.running,
            step="refine",
            cost_cap_usd=Decimal(str(settings.run_cost_cap_usd)),
            started_at=datetime.now(UTC),
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run


async def _analyze_idea(
    job: Job,
    *,
    settings: Settings,
    gate: Gate,
    tools: ToolsLike,
    embedder: Embedder | None,
    session_factory: async_sessionmaker[AsyncSession],
    jev: JevAsker | None,
    models: Mapping[str, Model | str | None] | None,
    gate_factory: Callable[[CostMeter], Gate] | None,
) -> None:
    idea_id = uuid.UUID(str(job.payload["idea_id"]))
    version_id = uuid.UUID(str(job.payload["version_id"]))
    raw_run_id = job.payload.get("run_id")
    run_id: uuid.UUID
    if raw_run_id is None:
        run = await _create_run(idea_id, version_id, settings, session_factory)
        run_id = run.id
    else:
        run_id = uuid.UUID(str(raw_run_id))
    orchestrator = Orchestrator(
        session_factory,
        settings,
        gate=gate,
        tools=tools,
        embedder=embedder,
        jev=jev,
        models=models,
        gate_factory=gate_factory,
    )
    result = await orchestrator.execute(run_id)
    if result is not None:
        try:
            from app.reports import apply_analysis_to_idea

            await apply_analysis_to_idea(result, session_factory)
        except Exception:
            logger.warning("applying analysis to idea failed", exc_info=True)


async def _rerun_run(
    job: Job,
    *,
    settings: Settings,
    gate: Gate,
    tools: ToolsLike,
    embedder: Embedder | None,
    session_factory: async_sessionmaker[AsyncSession],
    jev: JevAsker | None,
    models: Mapping[str, Model | str | None] | None,
    gate_factory: Callable[[CostMeter], Gate] | None,
) -> None:
    run_id = uuid.UUID(str(job.payload["run_id"]))
    step = str(job.payload["step"])
    orchestrator = Orchestrator(
        session_factory,
        settings,
        gate=gate,
        tools=tools,
        embedder=embedder,
        jev=jev,
        models=models,
        gate_factory=gate_factory,
    )
    await orchestrator.rerun(run_id, step)


async def _resume_run(
    job: Job,
    *,
    settings: Settings,
    gate: Gate,
    tools: ToolsLike,
    embedder: Embedder | None,
    session_factory: async_sessionmaker[AsyncSession],
    jev: JevAsker | None,
    models: Mapping[str, Model | str | None] | None,
    gate_factory: Callable[[CostMeter], Gate] | None,
) -> None:
    run_id = uuid.UUID(str(job.payload["run_id"]))
    raw_answers = job.payload.get("answers")
    answers: list[str] | None = None
    if isinstance(raw_answers, list):
        answers = [str(item) for item in cast("list[object]", raw_answers)]
    skip = bool(job.payload.get("skip", False))
    orchestrator = Orchestrator(
        session_factory,
        settings,
        gate=gate,
        tools=tools,
        embedder=embedder,
        jev=jev,
        models=models,
        gate_factory=gate_factory,
    )
    await orchestrator.resume_with_answers(run_id, answers, skip)


async def reindex_ideas(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    embedder: Embedder | None,
    limit: int = REINDEX_BATCH_SIZE,
) -> int:
    """Re-embed ideas whose search rows have a NULL embedding; returns the count.

    The embedding column of ``idea_search`` belongs to idea-core, which exposes
    no "missing embeddings" query; the worker reads the ids directly and then
    writes exclusively through :class:`IdeaService`.
    """
    if embedder is None:
        return 0
    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT idea_id FROM idea_search WHERE embedding IS NULL "
                        "ORDER BY idea_id LIMIT :batch"
                    ),
                    {"batch": limit},
                )
            )
            .scalars()
            .all()
        )
        service = IdeaService(session, embedder)
        refreshed = 0
        for idea_id in rows:
            try:
                await service.refresh_search_index(idea_id)
                refreshed += 1
            except IdeaNotFound:
                continue
            except Exception:
                logger.warning("reindex of idea %s failed", idea_id, exc_info=True)
        return refreshed


async def run_forever(
    worker_id: str,
    *,
    settings: Settings,
    gate: Gate,
    tools: ToolsLike,
    embedder: Embedder | None,
    session_factory: async_sessionmaker[AsyncSession],
    jev: JevAsker | None = None,
    models: Mapping[str, Model | str | None] | None = None,
    gate_factory: Callable[[CostMeter], Gate] | None = None,
) -> None:
    """Poll for jobs until cancelled; requeue stale ones and sweep embeddings."""
    poll_seconds = max(0.05, settings.worker_poll_interval_seconds)
    stale_every = max(30.0, settings.worker_job_stale_seconds / 10.0)
    logger.info("worker %s started (poll %.2fs)", worker_id, poll_seconds)
    queue = JobQueue(session_factory)
    loop = asyncio.get_running_loop()
    next_stale = loop.time() + stale_every
    next_reindex = loop.time() + REINDEX_INTERVAL_SECONDS
    while True:
        processed = False
        try:
            processed = await run_once(
                worker_id,
                settings=settings,
                gate=gate,
                tools=tools,
                embedder=embedder,
                session_factory=session_factory,
                jev=jev,
                models=models,
                gate_factory=gate_factory,
            )
        except asyncio.CancelledError:
            logger.info("worker %s stopped", worker_id)
            raise
        except Exception:
            logger.exception("worker loop error")
        now = loop.time()
        if now >= next_stale:
            try:
                requeued = await queue.requeue_stale(settings.worker_job_stale_seconds)
                if requeued:
                    logger.info("requeued %s stale jobs", requeued)
            except Exception:
                logger.exception("stale requeue sweep failed")
            next_stale = now + stale_every
        if now >= next_reindex:
            try:
                refreshed = await reindex_ideas(session_factory=session_factory, embedder=embedder)
                if refreshed:
                    logger.info("refreshed %s idea embeddings", refreshed)
            except Exception:
                logger.exception("reindex sweep failed")
            next_reindex = now + REINDEX_INTERVAL_SECONDS
        if not processed:
            await asyncio.sleep(poll_seconds)
