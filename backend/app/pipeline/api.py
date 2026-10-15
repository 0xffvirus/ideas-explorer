"""FastAPI router for the pipeline: runs, reruns, clarification, and SSE.

The router is dependency-light: reads use the request-scoped session and the
enqueue endpoints use :class:`~app.pipeline.jobs.JobQueue`. The worker rebuilds
per-run tools with the run's cost meter, so the API never needs to build an
orchestrator or any provider clients.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sse_starlette.sse import EventSourceResponse

from app.db import get_database, get_db_session
from app.ideas import Idea
from app.pipeline.engine import STEP_ORDER
from app.pipeline.jobs import JobQueue
from app.pipeline.models import (
    TERMINAL_RUN_STATUSES,
    AnalysisRun,
    RunEvent,
    RunStatus,
    RunStep,
    run_event_to_sse,
)
from app.pipeline.outputs import ClarifyingQuestion

router = APIRouter()

SSE_POLL_SECONDS = 0.5
SSE_PING_SECONDS = 15
SSE_RETRY_AFTER_PAUSE_MILLISECONDS = 30000


class RunStepRead(BaseModel):
    """One step of a run, including its persisted output."""

    id: uuid.UUID
    step: str
    status: str
    output: dict[str, Any] | None
    cost_usd: float
    model: str | None
    attempts: int
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_step(cls, step: RunStep) -> RunStepRead:
        return cls(
            id=step.id,
            step=step.step,
            status=step.status.value,
            output=step.output,
            cost_usd=float(step.cost_usd),
            model=step.model,
            attempts=step.attempts,
            error=step.error,
            started_at=step.started_at,
            finished_at=step.finished_at,
        )


class RunRead(BaseModel):
    """Public view of one analysis run."""

    id: uuid.UUID
    idea_id: uuid.UUID
    version_id: uuid.UUID
    status: str
    step: str
    cost_usd: float
    cost_cap_usd: float
    error: str | None
    questions: list[ClarifyingQuestion] | None
    started_at: datetime
    finished_at: datetime | None
    steps: list[RunStepRead] = Field(default_factory=list[RunStepRead])

    @classmethod
    def from_run(cls, run: AnalysisRun, steps: Sequence[RunStep]) -> RunRead:
        questions: list[ClarifyingQuestion] | None = None
        if run.questions is not None:
            questions = [ClarifyingQuestion.model_validate(item) for item in run.questions]
        return cls(
            id=run.id,
            idea_id=run.idea_id,
            version_id=run.idea_version_id,
            status=run.status.value,
            step=run.step,
            cost_usd=float(run.cost_usd),
            cost_cap_usd=float(run.cost_cap_usd),
            error=run.error,
            questions=questions,
            started_at=run.started_at,
            finished_at=run.finished_at,
            steps=[RunStepRead.from_step(step) for step in steps],
        )


class ClarifyRequest(BaseModel):
    """Answers to the clarifier's questions, or an explicit skip."""

    answers: list[str] | None = None
    skip: bool = False


def get_pipeline_session_factory() -> async_sessionmaker[AsyncSession]:
    """Session factory for streaming and queue dependencies."""
    return get_database().session_factory


def get_job_queue(
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_pipeline_session_factory)
    ],
) -> JobQueue:
    """Build the Postgres job queue."""
    return JobQueue(session_factory)


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
QueueDep = Annotated[JobQueue, Depends(get_job_queue)]
SessionFactoryDep = Annotated[
    async_sessionmaker[AsyncSession], Depends(get_pipeline_session_factory)
]


async def _load_steps(
    session: AsyncSession, run_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[RunStep]]:
    if not run_ids:
        return {}
    rows = (
        (
            await session.execute(
                select(RunStep)
                .where(RunStep.run_id.in_(run_ids))
                .order_by(RunStep.started_at, RunStep.step)
            )
        )
        .scalars()
        .all()
    )
    grouped: dict[uuid.UUID, list[RunStep]] = {run_id: [] for run_id in run_ids}
    for row in rows:
        grouped.setdefault(row.run_id, []).append(row)
    return grouped


async def _read_run(session: AsyncSession, run_id: uuid.UUID) -> RunRead:
    run = await session.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    steps = (await _load_steps(session, [run_id])).get(run_id, [])
    return RunRead.from_run(run, steps)


@router.get("/runs/{run_id}")
async def get_run(run_id: uuid.UUID, session: SessionDep) -> RunRead:
    """Fetch one run with its steps and persisted outputs."""
    return await _read_run(session, run_id)


@router.get("/ideas/{idea_id}/runs")
async def list_runs(idea_id: uuid.UUID, session: SessionDep) -> list[RunRead]:
    """List an idea's runs, newest first."""
    idea = await session.get(Idea, idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail=f"idea {idea_id} not found")
    runs = (
        (
            await session.execute(
                select(AnalysisRun)
                .where(AnalysisRun.idea_id == idea_id)
                .order_by(AnalysisRun.started_at.desc())
            )
        )
        .scalars()
        .all()
    )
    grouped = await _load_steps(session, [run.id for run in runs])
    return [RunRead.from_run(run, grouped.get(run.id, [])) for run in runs]


@router.post("/runs/{run_id}/steps/{step}/rerun", status_code=status.HTTP_202_ACCEPTED)
async def rerun_step(run_id: uuid.UUID, step: str, session: SessionDep, queue: QueueDep) -> RunRead:
    """Re-run one step and everything downstream of it.

    The run is switched to ``pending`` on the target step in the same
    transaction that enqueues the job, so clients see the rerun immediately
    instead of a stale terminal status.
    """
    if step not in STEP_ORDER:
        raise HTTPException(status_code=404, detail=f"unknown step {step!r}")
    run = (
        await session.execute(select(AnalysisRun).where(AnalysisRun.id == run_id).with_for_update())
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    if run.status not in TERMINAL_RUN_STATUSES:
        raise HTTPException(status_code=409, detail=f"run is {run.status.value}; cannot rerun")
    run.status = RunStatus.pending
    run.step = step
    run.error = None
    run.finished_at = None
    await queue.enqueue("rerun_run", {"run_id": str(run_id), "step": step}, session=session)
    await session.commit()
    return await _read_run(session, run_id)


@router.post("/runs/{run_id}/clarify", status_code=status.HTTP_202_ACCEPTED)
async def clarify_run(
    run_id: uuid.UUID, data: ClarifyRequest, session: SessionDep, queue: QueueDep
) -> RunRead:
    """Answer the clarifier's questions, or skip them, and resume the run."""
    run = await session.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    if run.status is not RunStatus.awaiting_input:
        raise HTTPException(status_code=409, detail=f"run is {run.status.value}; cannot clarify")
    answers = data.answers
    if data.skip and answers:
        raise HTTPException(status_code=422, detail="provide answers or skip, not both")
    if not data.skip:
        if not answers:
            raise HTTPException(status_code=422, detail="answers are required unless skipping")
        if len(answers) > 3:
            raise HTTPException(status_code=422, detail="at most 3 answers are allowed")
        if any(not answer.strip() for answer in answers):
            raise HTTPException(status_code=422, detail="answers must be non-empty strings")
    payload: dict[str, Any] = {
        "run_id": str(run_id),
        "answers": [answer.strip() for answer in answers] if answers else None,
        "skip": data.skip,
    }
    await queue.enqueue("resume_run", payload, session=session)
    await session.commit()
    return await _read_run(session, run_id)


async def _events_after(
    session_factory: async_sessionmaker[AsyncSession],
    run_id: uuid.UUID,
    after_seq: int,
) -> tuple[list[RunEvent], RunStatus | None]:
    async with session_factory() as session:
        events = (
            (
                await session.execute(
                    select(RunEvent)
                    .where(RunEvent.run_id == run_id, RunEvent.seq > after_seq)
                    .order_by(RunEvent.seq)
                )
            )
            .scalars()
            .all()
        )
        run_status = await session.scalar(
            select(AnalysisRun.status).where(AnalysisRun.id == run_id)
        )
    return list(events), run_status


@router.get("/runs/{run_id}/events")
async def stream_run_events(
    run_id: uuid.UUID,
    request: Request,
    session_factory: SessionFactoryDep,
) -> EventSourceResponse:
    """Stream run events as SSE, replaying after ``Last-Event-ID`` when given."""
    async with session_factory() as session:
        if await session.get(AnalysisRun, run_id) is None:
            raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    header = request.headers.get("last-event-id")
    try:
        last_seq = int(header) if header else 0
    except ValueError:
        last_seq = 0

    async def event_generator() -> AsyncIterator[dict[str, Any]]:
        nonlocal last_seq
        saw_pause = False
        while True:
            events, run_status = await _events_after(session_factory, run_id, last_seq)
            for event in events:
                last_seq = event.seq
                if event.event == "run_paused":
                    saw_pause = True
                yield run_event_to_sse(event)
            if run_status is None or (run_status in TERMINAL_RUN_STATUSES and not events):
                break
            if run_status is RunStatus.awaiting_input and (saw_pause or not events):
                yield {"retry": SSE_RETRY_AFTER_PAUSE_MILLISECONDS}
                break
            if await request.is_disconnected():
                break
            await asyncio.sleep(SSE_POLL_SECONDS)

    return EventSourceResponse(event_generator(), ping=SSE_PING_SECONDS)
