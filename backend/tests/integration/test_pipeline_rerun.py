"""Integration test: rerunning a step re-runs it and its dependents only."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings_as_test_overrides
from app.ideas import IdeaCreate, IdeaService
from app.ideas.testing import FakeEmbedder
from app.jev import FakeJevClient, Gate
from app.pipeline.jobs import JobQueue
from app.pipeline.models import AnalysisRun, RunStatus, RunStep
from app.pipeline.orchestrator import InvalidRunState, Orchestrator
from app.pipeline.worker import run_once
from tests.fixtures.pipeline.fakes import (
    business_args,
    competitors_args,
    critic_args,
    customers_args,
    default_models,
    default_tools,
    feasibility_args,
    market_args,
    output_model,
)

pytestmark = pytest.mark.integration

RAW = "A smart collar for senior dogs that warns owners about early illness."


async def _snapshot_steps(
    session_factory: async_sessionmaker[AsyncSession], run_id: uuid.UUID
) -> dict[str, tuple[str, object, object]]:
    async with session_factory() as session:
        steps = (
            (await session.execute(select(RunStep).where(RunStep.run_id == run_id))).scalars().all()
        )
    return {step.step: (step.status.value, step.started_at, step.output) for step in steps}


async def test_rerun_market_reruns_only_market_and_dependents(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = FakeJevClient()
    async with db_session_factory() as session:
        service = IdeaService(session, FakeEmbedder())
        detail = await service.create(IdeaCreate(raw_input=RAW, analyze=False))
        version_id = detail.latest_version.id
        run = AnalysisRun(
            idea_id=detail.id,
            idea_version_id=version_id,
            status=RunStatus.running,
            step="refine",
            cost_cap_usd=Decimal("0.75"),
            started_at=datetime.now(UTC),
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)

    first_calls: list[str] = []
    orchestrator = Orchestrator(
        db_session_factory,
        settings_as_test_overrides(),
        gate=Gate(client),
        tools=default_tools(),
        embedder=FakeEmbedder(),
        models=default_models(
            market=output_model(market_args, label="market", calls=first_calls),
        ),
        jev=client,
    )
    result = await orchestrator.execute(run.id)
    assert result is not None

    before = await _snapshot_steps(db_session_factory, run.id)

    second_calls: list[str] = []
    models = default_models(
        market=output_model(market_args, label="market", calls=second_calls),
        feasibility=output_model(feasibility_args, label="feasibility", calls=second_calls),
        business_model=output_model(business_args, label="business_model", calls=second_calls),
        competitors=output_model(competitors_args, label="competitors", calls=second_calls),
        customers=output_model(customers_args, label="customers", calls=second_calls),
        critic=output_model(critic_args, label="critic", calls=second_calls),
    )
    queue = JobQueue(db_session_factory)
    await queue.enqueue("rerun_run", {"run_id": str(run.id), "step": "market"})
    processed = await run_once(
        "worker-rerun",
        settings=settings_as_test_overrides(),
        gate=Gate(client),
        tools=default_tools(),
        embedder=FakeEmbedder(),
        session_factory=db_session_factory,
        jev=client,
        models=models,
    )
    assert processed is True

    assert sorted(second_calls) == [
        "business_model",
        "critic",
        "feasibility",
        "market",
    ]

    after = await _snapshot_steps(db_session_factory, run.id)
    for step in ("refine", "clarify", "competitors", "customers"):
        assert after[step][0] == before[step][0]
        assert after[step][1] == before[step][1]
    assert after["market"][1] != before["market"][1]
    assert after["feasibility"][1] != before["feasibility"][1]
    assert after["business_model"][1] != before["business_model"][1]
    assert after["critic"][1] != before["critic"][1]
    assert after["competitors"][2] == before["competitors"][2]
    assert after["customers"][2] == before["customers"][2]

    async with db_session_factory() as session:
        stored = await session.get(AnalysisRun, run.id)
        assert stored is not None
        assert stored.status is RunStatus.done
        assert float(stored.cost_usd) < 0.1


async def test_double_reset_raises_invalid_run_state(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = FakeJevClient()
    async with db_session_factory() as session:
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

    orchestrator = Orchestrator(
        db_session_factory,
        settings_as_test_overrides(),
        gate=Gate(client),
        tools=default_tools(),
        embedder=FakeEmbedder(),
        models=default_models(),
        jev=client,
    )
    assert await orchestrator.execute(run.id) is not None

    await orchestrator.reset_for_rerun(run.id, "market")
    async with db_session_factory() as session:
        stored = await session.get(AnalysisRun, run.id)
        assert stored is not None
        assert stored.status is RunStatus.pending
        assert stored.step == "market"

    with pytest.raises(InvalidRunState):
        await orchestrator.reset_for_rerun(run.id, "market")
