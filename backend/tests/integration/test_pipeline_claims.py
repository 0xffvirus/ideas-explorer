"""Integration tests: claim verification and one re-research pass for flags."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings_as_test_overrides
from app.ideas import IdeaCreate, IdeaService
from app.ideas.testing import FakeEmbedder
from app.jev import FakeJevClient, Gate, JevUnavailableError, NoulAnswer, ScoreAnswer
from app.pipeline.models import AnalysisRun, RunStatus, RunStep
from app.pipeline.orchestrator import Orchestrator
from tests.fixtures.pipeline.fakes import (
    default_models,
    default_tools,
    market_args,
    output_model,
)

pytestmark = pytest.mark.integration

RAW = "A smart collar for senior dogs that warns owners about early illness."


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


async def test_unsupported_claim_is_unverified(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = FakeJevClient()
    client.queue("claim_000", NoulAnswer(noul=0.1))
    run = await _create_run(db_session_factory)
    orchestrator = _orchestrator(db_session_factory, client, default_models())
    result = await orchestrator.execute(run.id)

    assert result is not None
    assert result.claims
    first = result.claims[0]
    assert first.section == "brief"
    assert first.status == "unverified"
    assert first.confidence == pytest.approx(0.1)
    assert any(claim.status == "verified" for claim in result.claims[1:])

    async with db_session_factory() as session:
        stored = await session.get(AnalysisRun, run.id)
        assert stored is not None
        assert stored.status is RunStatus.done


async def test_flagged_dimension_triggers_one_reresearch_and_keeps_confidence(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = FakeJevClient()
    client.queue("market_evidence", ScoreAnswer(score=1.0, confidence=0.2))
    client.queue("market_evidence", ScoreAnswer(score=3.0, confidence=0.85))
    calls: list[str] = []
    models = default_models(
        market=output_model(market_args, label="market", calls=calls),
    )
    run = await _create_run(db_session_factory)
    orchestrator = _orchestrator(db_session_factory, client, models)
    result = await orchestrator.execute(run.id)

    assert result is not None
    assert calls == ["market", "market"]
    by_dimension = {score.dimension: score for score in result.scorecard.dimensions}
    assert by_dimension["market_evidence"].confidence == pytest.approx(0.85)
    assert by_dimension["market_evidence"].score == pytest.approx(4.0)
    assert by_dimension["market_evidence"].source == "jev"

    async with db_session_factory() as session:
        market_step = (
            await session.execute(
                select(RunStep).where(RunStep.run_id == run.id, RunStep.step == "market")
            )
        ).scalar_one()
        assert market_step.attempts == 2
        assert market_step.status.value == "done"


async def test_healthy_scorecard_does_not_reresearch(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = FakeJevClient()
    calls: list[str] = []
    models = default_models(
        market=output_model(market_args, label="market", calls=calls),
    )
    run = await _create_run(db_session_factory)
    orchestrator = _orchestrator(db_session_factory, client, models)
    result = await orchestrator.execute(run.id)

    assert result is not None
    assert calls == ["market"]
    by_dimension = {score.dimension: score for score in result.scorecard.dimensions}
    assert by_dimension["market_evidence"].confidence == pytest.approx(0.9)


async def test_jev_outage_marks_scores_and_claims_unavailable(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = FakeJevClient()
    for _ in range(7):
        client.fail_next(JevUnavailableError("jev is down"))
    calls: list[str] = []
    models = default_models(
        market=output_model(market_args, label="market", calls=calls),
    )
    run = await _create_run(db_session_factory)
    orchestrator = _orchestrator(db_session_factory, client, models)
    result = await orchestrator.execute(run.id)

    assert result is not None
    assert calls == ["market"]
    assert all(score.source == "unavailable" for score in result.scorecard.dimensions)
    assert all(score.needs_review for score in result.scorecard.dimensions)
    assert all(claim.status == "unavailable" for claim in result.claims)
    assert result.verdict.source == "jev"
