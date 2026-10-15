"""Live eval: 10 golden ideas through the real pipeline (LLMs, Jev, tools).

Not part of the default suite. Run manually, with real spend:

    RUN_EVALS=1 uv run pytest tests/eval/test_pipeline_live_eval.py -q -m eval

Checks the SPEC-agent-pipeline eval bar: schema-valid output for every run,
>= 90% of claims carrying at least one source URL, p50 wall time <= 5 min,
mean cost per run <= the configured cap ($0.75 by default).
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.ideas import IdeaCreate, IdeaService, OpenAIEmbedder
from app.pipeline import AnalysisResult, RunStatus, SqlAnalysisEnqueuer
from app.pipeline.models import AnalysisRun, RunStep
from app.pipeline.worker import run_once
from app.worker import build_worker_clients

pytestmark = pytest.mark.eval

_settings = get_settings()
if (
    os.environ.get("RUN_EVALS") != "1"
    or not _settings.openai_api_key
    or not _settings.typesafe_api_key
    or not _settings.tavily_api_key
):
    pytest.skip(
        "live eval; set RUN_EVALS=1 plus OPENAI_API_KEY, TYPESAFE_API_KEY and TAVILY_API_KEY",
        allow_module_level=True,
    )


GOLDEN_IDEAS: list[dict[str, str]] = [
    {
        "id": "dental-scheduling",
        "text": (
            "A scheduling and reminder tool for independent dental clinics that fills "
            "cancelled slots by texting the practice's waitlist."
        ),
    },
    {
        "id": "landlord-compliance",
        "text": (
            "Software for small landlords that tracks local rental regulations, generates "
            "compliant leases, and reminds them of inspection deadlines."
        ),
    },
    {
        "id": "dog-walking",
        "text": "An app that matches busy dog owners with vetted neighborhood dog walkers.",
    },
    {
        "id": "restaurant-surplus",
        "text": (
            "A marketplace where restaurants sell surplus food at a discount to nearby "
            "customers in the last hour before closing."
        ),
    },
    {
        "id": "freelancer-invoicing",
        "text": (
            "An invoicing and late-payment chasing tool for solo freelancers that "
            "auto-follows up and offers early-payout advances."
        ),
    },
    {
        "id": "elder-care-coordination",
        "text": (
            "A coordination hub for families managing care for an elderly relative: shared "
            "calendar, medication reminders, and caregiver handoff notes."
        ),
    },
    {
        "id": "sme-cyber-audit",
        "text": (
            "A self-serve security audit for small businesses that checks their public "
            "attack surface and produces a prioritized fix list."
        ),
    },
    {
        "id": "language-tutor",
        "text": (
            "A subscription service pairing language learners with native speakers for "
            "short daily conversation practice with AI-generated homework."
        ),
    },
    {
        "id": "wedding-vendors",
        "text": (
            "A marketplace for wedding vendors in mid-size cities with availability "
            "calendars, quotes, and contract templates."
        ),
    },
    {
        "id": "warehouse-returns",
        "text": (
            "A returns-management tool for small e-commerce warehouses: scan a return, "
            "grade the item, and route it to resale, refurb, or recycle."
        ),
    },
]

TOTAL_DEADLINE_SECONDS = 45 * 60
TERMINAL_STATUSES = {RunStatus.done, RunStatus.partial, RunStatus.failed}


async def _load_runs(session_factory: Any) -> list[AnalysisRun]:
    async with session_factory() as session:
        return list((await session.execute(select(AnalysisRun))).scalars().all())


async def _load_result(session_factory: Any, run_id: Any) -> AnalysisResult | None:
    async with session_factory() as session:
        step = await session.scalar(
            select(RunStep).where(RunStep.run_id == run_id, RunStep.step == "critic")
        )
    if step is None or not step.output:
        return None
    raw = step.output.get("result")
    if not isinstance(raw, dict):
        return None
    try:
        return AnalysisResult.model_validate(raw)
    except ValueError:
        return None


async def test_golden_ideas_through_the_live_pipeline(db_session_factory: Any) -> None:
    settings = _settings
    clients = build_worker_clients(settings, session_factory=db_session_factory)
    embedder = OpenAIEmbedder(
        api_key=settings.openai_api_key,
        model=settings.openai_embedding_model,
        dimensions=settings.embedding_dimensions,
    )
    enqueuer = SqlAnalysisEnqueuer(db_session_factory)
    started = time.monotonic()

    try:
        async with db_session_factory() as session:
            service = IdeaService(session, embedder, enqueuer)
            for idea in GOLDEN_IDEAS:
                await service.create(IdeaCreate(raw_input=idea["text"], analyze=True))
            await session.commit()

        deadline = started + TOTAL_DEADLINE_SECONDS
        worker_id = "live-eval-worker"
        while time.monotonic() < deadline:
            runs = await _load_runs(db_session_factory)
            if len(runs) >= len(GOLDEN_IDEAS) and all(
                run.status in TERMINAL_STATUSES for run in runs
            ):
                break
            processed = await run_once(
                worker_id,
                settings=settings,
                gate=clients.gate,
                tools=clients.tools_factory,
                gate_factory=clients.gate_factory,
                embedder=embedder,
                session_factory=db_session_factory,
                jev=clients.jev_client,
            )
            if not processed:
                await asyncio.sleep(2)
        else:
            pytest.fail(f"live eval exceeded {TOTAL_DEADLINE_SECONDS}s")

        runs = await _load_runs(db_session_factory)
        assert len(runs) == len(GOLDEN_IDEAS), f"expected {len(GOLDEN_IDEAS)} runs"

        durations: list[float] = []
        costs: list[float] = []
        claims_total = 0
        claims_with_url = 0
        summary: list[str] = []
        for run in runs:
            assert run.status in TERMINAL_STATUSES, f"run {run.id} ended {run.status}"
            durations.append((run.finished_at - run.started_at).total_seconds())
            costs.append(float(run.cost_usd))
            result = await _load_result(db_session_factory, run.id)
            if result is None:
                summary.append(f"{run.id}: no result (status={run.status.value})")
                continue
            run_claims = result.claims
            with_url = sum(1 for ref in run_claims if ref.claim.source_urls)
            claims_total += len(run_claims)
            claims_with_url += with_url
            scores = ", ".join(
                f"{d.dimension}={d.score if d.score is not None else 'n/a'}"
                for d in result.scorecard.dimensions
            )
            summary.append(
                f"{result.brief.title[:40]!r}: status={run.status.value} "
                f"cost=${float(run.cost_usd):.3f} claims={with_url}/{len(run_claims)} [{scores}]"
            )

        p50 = sorted(durations)[len(durations) // 2]
        mean_cost = sum(costs) / len(costs)
        coverage = claims_with_url / claims_total if claims_total else 0.0

        print("\n=== live pipeline eval ===")
        for line in summary:
            print(" -", line)
        print(
            f"p50={p50:.0f}s mean_cost=${mean_cost:.3f} "
            f"claims_with_url={claims_with_url}/{claims_total} ({coverage:.0%})"
        )

        assert p50 <= 300, f"p50 wall time {p50:.0f}s exceeds 5 minutes"
        assert mean_cost <= settings.run_cost_cap_usd, (
            f"mean cost ${mean_cost:.3f} exceeds cap ${settings.run_cost_cap_usd:.2f}"
        )
        assert coverage >= 0.90, f"only {coverage:.0%} of claims carry a source URL"
        assert all(run.status is not RunStatus.failed for run in runs), "a run failed"
    finally:
        await clients.aclose()
