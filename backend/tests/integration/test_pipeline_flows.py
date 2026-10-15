"""Integration flows: end-to-end, concurrency, resume, and failure isolation."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import combinations, pairwise

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings_as_test_overrides
from app.ideas import Idea, IdeaCreate, IdeaService, IdeaStatus
from app.ideas.testing import FakeEmbedder
from app.jev import FakeJevClient, Gate
from app.pipeline.jobs import JobQueue, SqlAnalysisEnqueuer
from app.pipeline.models import AnalysisRun, Job, JobStatus, RunStatus, RunStep, StepStatus
from app.pipeline.orchestrator import Orchestrator
from app.pipeline.outputs import AnalysisResult
from app.pipeline.worker import run_once
from tests.fixtures.pipeline.fakes import (
    brief_args,
    competitors_args,
    critic_args,
    customers_args,
    default_models,
    default_tools,
    market_args,
    output_model,
)

pytestmark = pytest.mark.integration

RAW = "A smart collar for senior dogs that warns owners about early illness."


async def _create_idea(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    enqueuer: SqlAnalysisEnqueuer | None = None,
) -> uuid.UUID:
    async with session_factory() as session:
        service = IdeaService(session, FakeEmbedder(), enqueuer)
        detail = await service.create(IdeaCreate(raw_input=RAW, analyze=True))
        return detail.id


async def _create_run(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    cap: str = "0.75",
) -> tuple[AnalysisRun, uuid.UUID]:
    idea_id = await _create_idea(session_factory)
    async with session_factory() as session:
        idea = await session.get(Idea, idea_id)
        assert idea is not None
        detail = await IdeaService(session, FakeEmbedder()).get(idea_id)
        run = AnalysisRun(
            idea_id=idea_id,
            idea_version_id=detail.latest_version.id,
            status=RunStatus.running,
            step="refine",
            cost_cap_usd=Decimal(cap),
            started_at=datetime.now(UTC),
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run, idea_id


def _orchestrator(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    client: FakeJevClient,
    models: dict[str, object],
    settings: object | None = None,
) -> Orchestrator:
    overrides = settings or settings_as_test_overrides()
    return Orchestrator(
        session_factory,
        overrides,  # type: ignore[arg-type]
        gate=Gate(client),
        tools=default_tools(),
        embedder=FakeEmbedder(),
        models=models,  # type: ignore[arg-type]
        jev=client,
    )


async def test_end_to_end_enqueue_and_run_once(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    statuses: list[str] = []
    original = IdeaService.set_status

    async def spy(self: IdeaService, idea_id: uuid.UUID, status: IdeaStatus) -> None:
        statuses.append(status.value)
        await original(self, idea_id, status)

    monkeypatch.setattr(IdeaService, "set_status", spy)

    client = FakeJevClient()
    await _create_idea(db_session_factory, enqueuer=SqlAnalysisEnqueuer(db_session_factory))

    async with db_session_factory() as session:
        job = (await session.execute(select(Job))).scalar_one()
        assert job.kind == "analyze_idea"
        assert job.status is JobStatus.queued

    processed = await run_once(
        "worker-1",
        settings=settings_as_test_overrides(),
        gate=Gate(client),
        tools=default_tools(),
        embedder=FakeEmbedder(),
        session_factory=db_session_factory,
        jev=client,
        models=default_models(),
    )
    assert processed is True

    async with db_session_factory() as session:
        job = (await session.execute(select(Job))).scalar_one()
        assert job.status is JobStatus.done
        assert job.locked_by is None

        run = (await session.execute(select(AnalysisRun))).scalar_one()
        assert run.status is RunStatus.done
        assert run.finished_at is not None
        assert float(run.cost_usd) >= 0.0

        steps = (
            (await session.execute(select(RunStep).where(RunStep.run_id == run.id))).scalars().all()
        )
        by_step = {step.step: step for step in steps}
        assert set(by_step) == {
            "classify",
            "refine",
            "clarify",
            "market",
            "competitors",
            "customers",
            "feasibility",
            "business_model",
            "critic",
        }
        assert all(
            step.status is StepStatus.done for step in by_step.values() if step.step != "clarify"
        )
        assert by_step["clarify"].status is StepStatus.skipped
        assert by_step["clarify"].output == {"skipped": "brief_is_specific"}

        critic_output = by_step["critic"].output
        assert critic_output is not None
        result = AnalysisResult.model_validate(critic_output["result"])
        assert result.run_id == run.id
        assert result.brief.title
        assert result.market is not None
        assert result.verdict.source == "jev"
        assert result.claims
        assert all(claim.status == "verified" for claim in result.claims)

        idea = await session.get(Idea, run.idea_id)
        assert idea is not None
        assert idea.status is IdeaStatus.done

    async with db_session_factory() as session:
        detail = await IdeaService(session, FakeEmbedder()).get(
            (await session.execute(select(AnalysisRun))).scalar_one().idea_id
        )
    assert detail.latest_version.brief is not None
    assert detail.latest_version.brief["title"] == "PetPulse"
    assert statuses == ["analyzing", "done"]


async def test_research_trio_runs_concurrently(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    intervals: list[tuple[str, float, float]] = []
    settings = settings_as_test_overrides(max_parallel_research_agents=3)
    models = default_models(
        market=output_model(market_args, label="market", delay=0.3, intervals=intervals),
        competitors=output_model(
            competitors_args, label="competitors", delay=0.3, intervals=intervals
        ),
        customers=output_model(customers_args, label="customers", delay=0.3, intervals=intervals),
    )
    run, _ = await _create_run(db_session_factory)
    orchestrator = _orchestrator(
        db_session_factory, client=FakeJevClient(), models=models, settings=settings
    )
    result = await orchestrator.execute(run.id)
    assert result is not None

    trio = [
        interval for interval in intervals if interval[0] in {"market", "competitors", "customers"}
    ]
    assert len(trio) == 3
    for first, second in combinations(trio, 2):
        assert _overlaps(first, second), (first, second)
    span = max(end for _, _, end in trio) - min(start for _, start, _ in trio)
    assert span < 0.85


async def test_max_parallel_one_serializes_research(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    intervals: list[tuple[str, float, float]] = []
    settings = settings_as_test_overrides(max_parallel_research_agents=1)
    models = default_models(
        market=output_model(market_args, label="market", delay=0.15, intervals=intervals),
        competitors=output_model(
            competitors_args, label="competitors", delay=0.15, intervals=intervals
        ),
        customers=output_model(customers_args, label="customers", delay=0.15, intervals=intervals),
    )
    run, _ = await _create_run(db_session_factory)
    orchestrator = _orchestrator(
        db_session_factory, client=FakeJevClient(), models=models, settings=settings
    )
    result = await orchestrator.execute(run.id)
    assert result is not None

    trio = sorted(
        (
            interval
            for interval in intervals
            if interval[0] in {"market", "competitors", "customers"}
        ),
        key=lambda interval: interval[1],
    )
    assert len(trio) == 3
    for previous, following in pairwise(trio):
        assert following[1] >= previous[2]


async def test_resume_after_critic_failure_skips_completed_steps(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = FakeJevClient()
    first_calls: list[str] = []
    first_models = default_models(
        refine=output_model(brief_args, label="refine", calls=first_calls),
        market=output_model(market_args, label="market", calls=first_calls),
        competitors=output_model(competitors_args, label="competitors", calls=first_calls),
        customers=output_model(customers_args, label="customers", calls=first_calls),
        critic=output_model(
            critic_args, label="critic", calls=first_calls, error=RuntimeError("critic exploded")
        ),
    )
    run, _ = await _create_run(db_session_factory)
    orchestrator = _orchestrator(db_session_factory, client=client, models=first_models)
    result = await orchestrator.execute(run.id)
    assert result is None

    async with db_session_factory() as session:
        stored = await session.get(AnalysisRun, run.id)
        assert stored is not None
        assert stored.status is RunStatus.failed
        steps = (
            (await session.execute(select(RunStep).where(RunStep.run_id == run.id))).scalars().all()
        )
        attempts_before = {step.step: step.attempts for step in steps}
        statuses = {step.step: step.status for step in steps}
        assert statuses["refine"] is StepStatus.done
        assert statuses["market"] is StepStatus.done
        assert statuses["competitors"] is StepStatus.done
        assert statuses["customers"] is StepStatus.done
        assert statuses["feasibility"] is StepStatus.done
        assert statuses["business_model"] is StepStatus.done
        assert statuses["critic"] is StepStatus.failed

    assert sorted(first_calls) == ["competitors", "critic", "customers", "market", "refine"]

    second_calls: list[str] = []
    second_models = default_models(
        critic=output_model(critic_args, label="critic", calls=second_calls),
    )
    fresh = _orchestrator(db_session_factory, client=client, models=second_models)
    result = await fresh.execute(run.id)
    assert result is not None
    assert second_calls == ["critic"]

    async with db_session_factory() as session:
        steps = (
            (await session.execute(select(RunStep).where(RunStep.run_id == run.id))).scalars().all()
        )
        attempts_after = {step.step: step.attempts for step in steps}
        for step_name, attempts in attempts_before.items():
            if step_name == "critic":
                assert attempts_after[step_name] == attempts + 1
            else:
                assert attempts_after[step_name] == attempts


async def test_failed_section_isolated_and_run_reaches_critic(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = FakeJevClient()
    models = default_models(
        market=output_model(market_args, label="market", error=RuntimeError("market down")),
    )
    run, _ = await _create_run(db_session_factory)
    orchestrator = _orchestrator(db_session_factory, client=client, models=models)
    result = await orchestrator.execute(run.id)

    assert result is not None
    assert result.market is None
    assert result.competitors is not None
    assert result.customers is not None
    assert result.feasibility is not None
    assert result.business_model is not None
    assert result.sections_status["market"] == "failed"
    assert result.sections_status["critic"] == "done"

    async with db_session_factory() as session:
        stored = await session.get(AnalysisRun, run.id)
        assert stored is not None
        assert stored.status is RunStatus.partial
        market_step = (
            await session.execute(
                select(RunStep).where(RunStep.run_id == run.id, RunStep.step == "market")
            )
        ).scalar_one()
        assert market_step.status is StepStatus.failed
        assert "market down" in (market_step.error or "")
        idea = await session.get(Idea, run.idea_id)
        assert idea is not None
        assert idea.status is IdeaStatus.failed


def _overlaps(first: tuple[str, float, float], second: tuple[str, float, float]) -> bool:
    return first[1] < second[2] and second[1] < first[2]


async def test_worker_crash_mid_run_resumes_the_same_run_after_requeue(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_idea(db_session_factory, enqueuer=SqlAnalysisEnqueuer(db_session_factory))
    async with db_session_factory() as session:
        enqueued_run = (await session.execute(select(AnalysisRun))).scalar_one()
        enqueued_job = (await session.execute(select(Job))).scalar_one()
        assert enqueued_run.status is RunStatus.pending
        assert enqueued_job.payload["run_id"] == str(enqueued_run.id)
        run_id = enqueued_run.id
        job_id = enqueued_job.id

    critic_started = asyncio.Event()
    critic_release = asyncio.Event()

    async def hang_at_critic(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        critic_started.set()
        await critic_release.wait()
        raise RuntimeError("worker was killed")

    models = default_models(critic=FunctionModel(hang_at_critic))
    task = asyncio.create_task(
        run_once(
            "dead-worker",
            settings=settings_as_test_overrides(),
            gate=Gate(FakeJevClient()),
            tools=default_tools(),
            embedder=FakeEmbedder(),
            session_factory=db_session_factory,
            jev=FakeJevClient(),
            models=models,
        )
    )
    await asyncio.wait_for(critic_started.wait(), timeout=30)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    async with db_session_factory() as session:
        crashed_job = await session.get(Job, job_id)
        assert crashed_job is not None
        assert crashed_job.status is JobStatus.running
        assert crashed_job.attempts == 1
        crashed_run = await session.get(AnalysisRun, run_id)
        assert crashed_run is not None
        assert crashed_run.status is RunStatus.running
        steps_before = {
            step.step: (step.attempts, step.started_at, step.output)
            for step in (await session.execute(select(RunStep).where(RunStep.run_id == run_id)))
            .scalars()
            .all()
        }
        assert steps_before["refine"][0] == 1
        assert steps_before["critic"][0] == 1
        crashed_job.locked_at = datetime.now(UTC) - timedelta(seconds=7200)
        await session.commit()

    queue = JobQueue(db_session_factory)
    assert await queue.requeue_stale(900) == 1

    second_calls: list[str] = []
    models = default_models(critic=output_model(critic_args, label="critic", calls=second_calls))
    processed = await run_once(
        "worker-2",
        settings=settings_as_test_overrides(),
        gate=Gate(FakeJevClient()),
        tools=default_tools(),
        embedder=FakeEmbedder(),
        session_factory=db_session_factory,
        jev=FakeJevClient(),
        models=models,
    )
    assert processed is True
    assert second_calls == ["critic"]

    async with db_session_factory() as session:
        all_runs = (await session.execute(select(AnalysisRun))).scalars().all()
        assert len(all_runs) == 1
        resumed_run = all_runs[0]
        assert resumed_run.id == run_id
        assert resumed_run.status is RunStatus.done
        resumed_job = (await session.execute(select(Job))).scalar_one()
        assert resumed_job.status is JobStatus.done
        assert resumed_job.attempts == 2
        steps_after = {
            step.step: (step.attempts, step.started_at, step.output)
            for step in (await session.execute(select(RunStep).where(RunStep.run_id == run_id)))
            .scalars()
            .all()
        }
        for step_name, (attempts, started_at, output) in steps_before.items():
            if step_name == "critic":
                assert steps_after[step_name][0] == attempts + 1
                continue
            assert steps_after[step_name][0] == attempts
            assert steps_after[step_name][1] == started_at
            assert steps_after[step_name][2] == output
        detail = await IdeaService(session, FakeEmbedder()).get(resumed_run.idea_id)
        assert detail.latest_version.brief is not None
        assert detail.latest_version.brief["title"] == "PetPulse"


async def test_analyze_job_without_run_id_still_creates_a_run(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _create_idea(db_session_factory)
    async with db_session_factory() as session:
        idea = (await session.execute(select(Idea))).scalar_one()
        detail = await IdeaService(session, FakeEmbedder()).get(idea.id)
        await JobQueue(db_session_factory).enqueue(
            "analyze_idea",
            {"idea_id": str(idea.id), "version_id": str(detail.latest_version.id)},
            session=session,
        )
        await session.commit()

    processed = await run_once(
        "legacy-worker",
        settings=settings_as_test_overrides(),
        gate=Gate(FakeJevClient()),
        tools=default_tools(),
        embedder=FakeEmbedder(),
        session_factory=db_session_factory,
        jev=FakeJevClient(),
        models=default_models(),
    )
    assert processed is True
    async with db_session_factory() as session:
        run = (await session.execute(select(AnalysisRun))).scalar_one()
        assert run.status is RunStatus.done
        job = (await session.execute(select(Job))).scalar_one()
        assert job.status is JobStatus.done


async def test_terminal_job_failure_marks_the_run_failed(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _create_idea(db_session_factory, enqueuer=SqlAnalysisEnqueuer(db_session_factory))

    async def explode(self: Orchestrator, run_id: uuid.UUID, **kwargs: object) -> None:
        raise RuntimeError("orchestrator exploded")

    monkeypatch.setattr(Orchestrator, "execute", explode)

    for attempt in range(3):
        if attempt:
            async with db_session_factory() as session:
                job = (await session.execute(select(Job))).scalar_one()
                job.run_after = datetime.now(UTC) - timedelta(seconds=1)
                await session.commit()
        processed = await run_once(
            f"worker-{attempt}",
            settings=settings_as_test_overrides(),
            gate=Gate(FakeJevClient()),
            tools=default_tools(),
            embedder=FakeEmbedder(),
            session_factory=db_session_factory,
            jev=FakeJevClient(),
            models=default_models(),
        )
        assert processed is True

    async with db_session_factory() as session:
        job = (await session.execute(select(Job))).scalar_one()
        assert job.status is JobStatus.failed
        assert job.attempts == 3
        run = (await session.execute(select(AnalysisRun))).scalar_one()
        assert run.status is RunStatus.failed
        assert "orchestrator exploded" in (run.error or "")
        assert run.finished_at is not None


async def test_schema_failure_costs_exactly_two_model_calls(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    calls: list[str] = []

    async def invalid_brief(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append("refine")
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, {"not": "a brief"})],
            usage=RequestUsage(input_tokens=5, output_tokens=5),
        )

    models = default_models(refine=FunctionModel(invalid_brief))
    run, _ = await _create_run(db_session_factory)
    orchestrator = _orchestrator(db_session_factory, client=FakeJevClient(), models=models)
    result = await orchestrator.execute(run.id)
    assert result is None
    assert calls == ["refine", "refine"]

    async with db_session_factory() as session:
        stored = await session.get(AnalysisRun, run.id)
        assert stored is not None
        assert stored.status is RunStatus.failed
        assert "schema validation failed" in (stored.error or "")
        refine_step = (
            await session.execute(
                select(RunStep).where(RunStep.run_id == run.id, RunStep.step == "refine")
            )
        ).scalar_one()
        assert refine_step.status is StepStatus.failed
