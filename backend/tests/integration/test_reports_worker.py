"""Integration tests for the worker's report integration point."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings_as_test_overrides
from app.ideas import Idea, IdeaCreate, IdeaService, IdeaStatus, IdeaVerdict
from app.ideas.testing import FakeEmbedder
from app.jev import FakeJevClient, Gate
from app.pipeline.jobs import SqlAnalysisEnqueuer
from app.pipeline.models import AnalysisRun, Job, JobStatus, RunStatus, RunStep
from app.pipeline.worker import run_once
from tests.fixtures.pipeline.fakes import default_models, default_tools

pytestmark = pytest.mark.integration

RAW = "A smart collar for senior dogs that warns owners about early illness."


async def _enqueue_idea(
    session_factory: async_sessionmaker[AsyncSession],
) -> uuid.UUID:
    async with session_factory() as session:
        service = IdeaService(session, FakeEmbedder(), SqlAnalysisEnqueuer(session_factory))
        detail = await service.create(IdeaCreate(raw_input=RAW, analyze=True))
        return detail.id


async def _run_one(db_session_factory: async_sessionmaker[AsyncSession]) -> None:
    client = FakeJevClient()
    processed = await run_once(
        "worker-reports",
        settings=settings_as_test_overrides(),
        gate=Gate(client),
        tools=default_tools(),
        embedder=FakeEmbedder(),
        session_factory=db_session_factory,
        jev=client,
        models=default_models(),
    )
    assert processed is True


async def test_worker_applies_analysis_fields_to_idea(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    idea_id = await _enqueue_idea(db_session_factory)
    await _run_one(db_session_factory)

    async with db_session_factory() as session:
        job = (await session.execute(select(Job))).scalar_one()
        assert job.status is JobStatus.done
        run = (await session.execute(select(AnalysisRun))).scalar_one()
        assert run.status is RunStatus.done
        steps = (
            (await session.execute(select(RunStep).where(RunStep.run_id == run.id))).scalars().all()
        )
        assert any(step.step == "critic" for step in steps)
        idea = await session.get(Idea, idea_id)
        assert idea is not None
        assert idea.status is IdeaStatus.done
        assert idea.verdict is IdeaVerdict.pursue
        assert idea.overall_score is not None
        assert float(idea.overall_score) == pytest.approx(60.0)
        assert idea.category == "b2b_saas"
        assert idea.title == "PetPulse"


async def test_worker_survives_report_side_failure(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("report side exploded")

    monkeypatch.setattr("app.reports.apply_analysis_to_idea", explode)
    idea_id = await _enqueue_idea(db_session_factory)
    await _run_one(db_session_factory)

    async with db_session_factory() as session:
        job = (await session.execute(select(Job))).scalar_one()
        assert job.status is JobStatus.done
        idea = await session.get(Idea, idea_id)
        assert idea is not None
        assert idea.status is IdeaStatus.done
        assert idea.verdict is None
