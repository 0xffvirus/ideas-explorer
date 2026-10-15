"""Integration tests: cost-cap planning, partial stops, and rerun accounting."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import ModelPrice, settings_as_test_overrides
from app.ideas import Idea, IdeaCreate, IdeaService, IdeaStatus
from app.ideas.testing import FakeEmbedder
from app.jev import FakeJevClient, Gate
from app.pipeline.engine import STEP_ESTIMATES_USD
from app.pipeline.models import AnalysisRun, RunStatus, RunStep
from app.pipeline.orchestrator import Orchestrator
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
CAP = 0.05


async def _create_run(
    session_factory: async_sessionmaker[AsyncSession],
    cap: float = CAP,
) -> AnalysisRun:
    async with session_factory() as session:
        service = IdeaService(session, FakeEmbedder())
        detail = await service.create(IdeaCreate(raw_input=RAW, analyze=False))
        run = AnalysisRun(
            idea_id=detail.id,
            idea_version_id=detail.latest_version.id,
            status=RunStatus.running,
            step="refine",
            cost_cap_usd=Decimal(str(cap)),
            started_at=datetime.now(UTC),
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run


def _orchestrator(
    session_factory: async_sessionmaker[AsyncSession],
    settings: object,
    models: dict[str, object],
) -> Orchestrator:
    return Orchestrator(
        session_factory,
        settings,  # type: ignore[arg-type]
        gate=Gate(FakeJevClient()),
        tools=default_tools(),
        embedder=FakeEmbedder(),
        models=models,  # type: ignore[arg-type]
        jev=FakeJevClient(),
    )


async def test_cost_cap_stops_partially_with_sections_intact(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = settings_as_test_overrides(
        run_cost_cap_usd=CAP,
        model_pricing={"priced-model": ModelPrice(input=2.5, output=10.0)},
    )
    calls: list[str] = []
    models = default_models(
        market=output_model(
            market_args,
            label="market",
            calls=calls,
            input_tokens=24000,
            output_tokens=0,
            model_name="priced-model",
        )
    )
    run = await _create_run(db_session_factory)
    orchestrator = _orchestrator(db_session_factory, settings, models)
    result = await orchestrator.execute(run.id)
    assert result is None
    assert calls == ["market"]

    async with db_session_factory() as session:
        stored = await session.get(AnalysisRun, run.id)
        assert stored is not None
        assert stored.status is RunStatus.partial
        assert stored.error == "cost_cap"
        assert stored.step == "competitors"
        spend = float(stored.cost_usd)
        assert spend > CAP
        assert spend <= CAP + STEP_ESTIMATES_USD["market"]

        steps = (
            (await session.execute(select(RunStep).where(RunStep.run_id == run.id))).scalars().all()
        )
        by_step = {step.step: step for step in steps}
        assert by_step["market"].status.value == "done"
        assert by_step["market"].output is not None
        assert by_step["market"].output["tam"]["value"] == "$4.2B"
        assert "competitors" not in by_step
        assert "customers" not in by_step
        assert "feasibility" not in by_step
        assert "business_model" not in by_step
        assert "critic" not in by_step

        idea = await session.get(Idea, run.idea_id)
        assert idea is not None
        assert idea.status is IdeaStatus.failed


async def test_concurrent_research_reserves_estimates_in_order(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    cap = STEP_ESTIMATES_USD["market"] + STEP_ESTIMATES_USD["competitors"] + 0.001
    settings = settings_as_test_overrides(run_cost_cap_usd=cap)
    calls: list[str] = []
    models = default_models(
        market=output_model(market_args, label="market", calls=calls),
        competitors=output_model(competitors_args, label="competitors", calls=calls),
        customers=output_model(customers_args, label="customers", calls=calls),
    )
    run = await _create_run(db_session_factory, cap=cap)
    orchestrator = _orchestrator(db_session_factory, settings, models)
    result = await orchestrator.execute(run.id)
    assert result is None
    assert sorted(calls) == ["competitors", "market"]

    async with db_session_factory() as session:
        stored = await session.get(AnalysisRun, run.id)
        assert stored is not None
        assert stored.status is RunStatus.partial
        assert stored.error == "cost_cap"
        assert stored.step == "customers"
        assert float(stored.cost_usd) <= cap + STEP_ESTIMATES_USD["competitors"]

        steps = (
            (await session.execute(select(RunStep).where(RunStep.run_id == run.id))).scalars().all()
        )
        by_step = {step.step: step for step in steps}
        assert by_step["market"].status.value == "done"
        assert by_step["competitors"].status.value == "done"
        assert "customers" not in by_step


async def test_rerun_keeps_accumulated_cost_and_respects_the_same_cap(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = settings_as_test_overrides(
        run_cost_cap_usd=CAP,
        model_pricing={"priced-model": ModelPrice(input=2.5, output=10.0)},
    )
    first_calls: list[str] = []
    models = default_models(
        market=output_model(
            market_args,
            label="market",
            calls=first_calls,
            input_tokens=24000,
            output_tokens=0,
            model_name="priced-model",
        )
    )
    run = await _create_run(db_session_factory)
    orchestrator = _orchestrator(db_session_factory, settings, models)
    assert await orchestrator.execute(run.id) is None
    async with db_session_factory() as session:
        stored = await session.get(AnalysisRun, run.id)
        assert stored is not None
        assert stored.status is RunStatus.partial
        spend_before = float(stored.cost_usd)
    assert spend_before > CAP

    await orchestrator.reset_for_rerun(run.id, "market")
    async with db_session_factory() as session:
        reset_run = await session.get(AnalysisRun, run.id)
        assert reset_run is not None
        assert reset_run.status is RunStatus.pending
        assert float(reset_run.cost_usd) == pytest.approx(spend_before)

    second_calls: list[str] = []
    models = default_models(
        market=output_model(
            market_args,
            label="market",
            calls=second_calls,
            input_tokens=24000,
            output_tokens=0,
            model_name="priced-model",
        ),
        feasibility=output_model(feasibility_args, label="feasibility", calls=second_calls),
        business_model=output_model(business_args, label="business_model", calls=second_calls),
        critic=output_model(critic_args, label="critic", calls=second_calls),
    )
    fresh = _orchestrator(db_session_factory, settings, models)
    assert await fresh.execute(run.id) is None
    assert second_calls == []

    async with db_session_factory() as session:
        stored = await session.get(AnalysisRun, run.id)
        assert stored is not None
        assert stored.status is RunStatus.partial
        assert stored.error == "cost_cap"
        assert float(stored.cost_usd) == pytest.approx(spend_before)
