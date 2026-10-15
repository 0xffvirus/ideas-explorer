"""Integration tests: the clarifier pause and resume with answers or skip."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings_as_test_overrides
from app.ideas import IdeaCreate, IdeaService
from app.ideas.testing import FakeEmbedder
from app.jev import FakeJevClient, Gate, NoulAnswer, ScoreAnswer
from app.pipeline.models import AnalysisRun, RunStatus, RunStep, StepStatus
from app.pipeline.orchestrator import InvalidRunState, Orchestrator
from tests.fixtures.pipeline.fakes import brief_args, default_models, default_tools, output_model

pytestmark = pytest.mark.integration

RAW = "An idea for pets."


async def _create_run(session_factory: async_sessionmaker[AsyncSession]) -> AnalysisRun:
    async with session_factory() as session:
        service = IdeaService(session, FakeEmbedder())
        detail = await service.create(IdeaCreate(raw_input=RAW, analyze=False))
        run = AnalysisRun(
            idea_id=detail.id,
            idea_version_id=detail.latest_version.id,
            status=RunStatus.running,
            step="refine",
            cost_cap_usd=Decimal("0.75"),
            started_at=datetime.now(UTC),
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run


def _orchestrator(
    session_factory: async_sessionmaker[AsyncSession],
    client: FakeJevClient,
    models: dict[str, object],
) -> Orchestrator:
    return Orchestrator(
        session_factory,
        settings_as_test_overrides(),
        gate=Gate(client),
        tools=default_tools(),
        embedder=FakeEmbedder(),
        models=models,  # type: ignore[arg-type]
        jev=client,
    )


async def test_awaiting_input_then_resume_with_answers(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = FakeJevClient()
    client.queue("brief_is_specific", NoulAnswer(noul=0.1))
    refine_calls: list[str] = []
    models = default_models(
        refine=output_model(brief_args, label="refine", calls=refine_calls),
    )
    run = await _create_run(db_session_factory)
    orchestrator = _orchestrator(db_session_factory, client, models)

    result = await orchestrator.execute(run.id)
    assert result is None

    async with db_session_factory() as session:
        stored = await session.get(AnalysisRun, run.id)
        assert stored is not None
        assert stored.status is RunStatus.awaiting_input
        assert stored.step == "clarify"
        assert stored.questions is not None
        assert 1 <= len(stored.questions) <= 3
        assert all("question" in item and "why" in item for item in stored.questions)
        assert stored.answers is None
        steps = (
            (await session.execute(select(RunStep).where(RunStep.run_id == run.id))).scalars().all()
        )
        by_step = {step.step: step for step in steps}
        assert set(by_step) == {"classify", "refine", "clarify"}
        assert by_step["refine"].status is StepStatus.done
        assert by_step["clarify"].output is not None
        assert len(by_step["clarify"].output["questions"]) == len(stored.questions)

    resumed = await orchestrator.resume_with_answers(
        run.id, ["Urban owners of senior dogs", "Vet visits and spreadsheets"], False
    )
    assert resumed is not None
    assert refine_calls == ["refine", "refine"]

    async with db_session_factory() as session:
        stored = await session.get(AnalysisRun, run.id)
        assert stored is not None
        assert stored.status is RunStatus.done
        assert stored.answers == ["Urban owners of senior dogs", "Vet visits and spreadsheets"]
        steps = (
            (await session.execute(select(RunStep).where(RunStep.run_id == run.id))).scalars().all()
        )
        by_step = {step.step: step for step in steps}
        assert by_step["clarify"].status is StepStatus.done
        assert by_step["clarify"].output["brief_updated"] is True
    assert resumed.sections_status["clarify"] == "done"


async def test_awaiting_input_then_skip(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = FakeJevClient()
    client.queue("brief_is_specific", NoulAnswer(noul=0.2))
    refine_calls: list[str] = []
    models = default_models(
        refine=output_model(brief_args, label="refine", calls=refine_calls),
    )
    run = await _create_run(db_session_factory)
    orchestrator = _orchestrator(db_session_factory, client, models)

    assert await orchestrator.execute(run.id) is None
    resumed = await orchestrator.resume_with_answers(run.id, None, True)
    assert resumed is not None
    assert refine_calls == ["refine"]

    async with db_session_factory() as session:
        stored = await session.get(AnalysisRun, run.id)
        assert stored is not None
        assert stored.status is RunStatus.done
        assert stored.answers == ["skip"]
        clarify = (
            await session.execute(
                select(RunStep).where(RunStep.run_id == run.id, RunStep.step == "clarify")
            )
        ).scalar_one()
        assert clarify.status is StepStatus.skipped
        assert clarify.output == {"skipped": True}


async def test_resume_requires_awaiting_input(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = FakeJevClient()
    models = default_models()
    run = await _create_run(db_session_factory)
    orchestrator = _orchestrator(db_session_factory, client, models)
    assert await orchestrator.execute(run.id) is not None
    with pytest.raises(InvalidRunState):
        await orchestrator.resume_with_answers(run.id, ["a"], False)


async def test_refine_reresearch_keeps_clarifying_answers(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = FakeJevClient()
    client.queue("brief_is_specific", NoulAnswer(noul=0.1))
    client.queue("problem_severity", ScoreAnswer(score=1.0, confidence=0.2))
    prompts: list[str] = []
    models = default_models(
        refine=output_model(brief_args, label="refine", prompts=prompts),
    )
    run = await _create_run(db_session_factory)
    orchestrator = _orchestrator(db_session_factory, client, models)

    assert await orchestrator.execute(run.id) is None
    resumed = await orchestrator.resume_with_answers(
        run.id, ["Urban owners of senior dogs", "Vet visits and spreadsheets"], False
    )
    assert resumed is not None

    assert len(prompts) == 3
    assert "Clarifying answers" not in prompts[0]
    assert "Clarifying answers" in prompts[1]
    assert "Urban owners of senior dogs" in prompts[1]
    assert "Clarifying answers" in prompts[2]
    assert "Urban owners of senior dogs" in prompts[2]
    assert "Vet visits and spreadsheets" in prompts[2]
    assert "Q: " in prompts[2]
