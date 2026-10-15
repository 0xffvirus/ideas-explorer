"""Integration tests for apply_analysis_to_idea against real Postgres."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ideas import IdeaCreate, IdeaService, IdeaVerdict
from app.ideas.testing import FakeEmbedder
from app.jev import DimensionName, DimensionScore, Scorecard, Verdict
from app.pipeline.models import AnalysisRun, RunStatus, RunStep, StepStatus
from app.reports.apply import apply_analysis_to_idea
from tests.fixtures.reports.fixtures import make_result

pytestmark = pytest.mark.integration

RAW = "A smart collar for senior dogs."


async def _seed_idea_with_result(
    session_factory: async_sessionmaker[AsyncSession],
):
    async with session_factory() as session:
        service = IdeaService(session, FakeEmbedder())
        detail = await service.create(IdeaCreate(raw_input=RAW, analyze=False))
        run = AnalysisRun(
            idea_id=detail.id,
            idea_version_id=detail.latest_version.id,
            status=RunStatus.done,
            step="critic",
            cost_usd=Decimal("0.42"),
            cost_cap_usd=Decimal("0.75"),
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )
        session.add(run)
        await session.flush()
        result = make_result(
            idea_id=detail.id,
            version_id=detail.latest_version.id,
            run_id=run.id,
        )
        session.add(
            RunStep(
                run_id=run.id,
                step="critic",
                status=StepStatus.done,
                output={"critic": {}, "result": result.model_dump(mode="json")},
                attempts=1,
            )
        )
        await session.commit()
        return detail.id, result


async def test_apply_analysis_to_idea_sets_verdict_score_category_title(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    idea_id, result = await _seed_idea_with_result(db_session_factory)
    await apply_analysis_to_idea(result, db_session_factory)

    async with db_session_factory() as session:
        detail = await IdeaService(session, FakeEmbedder()).get(idea_id)
    assert detail.verdict is IdeaVerdict.refine
    assert detail.overall_score == pytest.approx(75.9)
    assert detail.category == "hardware"
    assert detail.title == "PetPulse"


async def test_apply_analysis_to_idea_writes_none_for_unavailable_signals(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    idea_id, result = await _seed_idea_with_result(db_session_factory)
    dims: list[DimensionName] = [
        "problem_severity",
        "market_evidence",
        "competition_intensity",
        "customer_reachability",
        "feasibility",
        "monetization_clarity",
    ]
    unavailable = result.model_copy(
        update={
            "classification": None,
            "verdict": Verdict(decision=None, confidence=None, needs_review=True),
            "scorecard": Scorecard(
                dimensions=[
                    DimensionScore(
                        dimension=dimension,
                        score=None,
                        confidence=None,
                        needs_review=True,
                        source="unavailable",
                    )
                    for dimension in dims
                ]
            ),
        }
    )
    await apply_analysis_to_idea(unavailable, db_session_factory)

    async with db_session_factory() as session:
        detail = await IdeaService(session, FakeEmbedder()).get(idea_id)
    assert detail.verdict is None
    assert detail.overall_score is None
    assert detail.category is None
    assert detail.title == "PetPulse"
