"""Integration tests for the pipeline FastAPI router."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import get_db_session
from app.ideas import IdeaCreate, IdeaService
from app.ideas.testing import FakeEmbedder
from app.pipeline.api import get_pipeline_session_factory, router
from app.pipeline.models import AnalysisRun, Job, RunStatus, RunStep, StepStatus

pytestmark = pytest.mark.integration

RAW = "A smart collar for senior dogs."


async def _create_run(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    status: RunStatus = RunStatus.done,
    questions: list[dict[str, str]] | None = None,
) -> tuple[AnalysisRun, uuid.UUID]:
    async with session_factory() as session:
        service = IdeaService(session, FakeEmbedder())
        detail = await service.create(IdeaCreate(raw_input=RAW, analyze=False))
        run = AnalysisRun(
            idea_id=detail.id,
            idea_version_id=detail.latest_version.id,
            status=status,
            step="critic" if status is RunStatus.done else "clarify",
            cost_usd=Decimal("0.1234"),
            cost_cap_usd=Decimal("0.75"),
            questions=questions,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC) if status is RunStatus.done else None,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run, detail.id


@pytest.fixture
async def api_client(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    app = FastAPI()
    app.include_router(router)

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_pipeline_session_factory] = lambda: db_session_factory
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def test_get_run_and_404(
    api_client: AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    run, idea_id = await _create_run(db_session_factory)
    async with db_session_factory() as session:
        session.add(
            RunStep(
                run_id=run.id,
                step="critic",
                status=StepStatus.done,
                output={"critic": {}, "result": {}},
                cost_usd=Decimal("0.02"),
                model="openai:gpt-4o",
                attempts=1,
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
            )
        )
        await session.commit()

    response = await api_client.get(f"/runs/{run.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(run.id)
    assert body["idea_id"] == str(idea_id)
    assert body["version_id"] == str(run.idea_version_id)
    assert body["status"] == "done"
    assert body["cost_usd"] == pytest.approx(0.1234)
    assert body["cost_cap_usd"] == pytest.approx(0.75)
    assert body["questions"] is None
    assert len(body["steps"]) == 1
    assert body["steps"][0]["step"] == "critic"
    assert body["steps"][0]["status"] == "done"

    missing = await api_client.get(f"/runs/{uuid.uuid4()}")
    assert missing.status_code == 404


async def test_list_runs_for_idea(
    api_client: AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    run, idea_id = await _create_run(db_session_factory)
    async with db_session_factory() as session:
        older = AnalysisRun(
            idea_id=idea_id,
            idea_version_id=run.idea_version_id,
            status=RunStatus.failed,
            step="market",
            cost_cap_usd=Decimal("0.75"),
            started_at=datetime.now(UTC) - timedelta(minutes=5),
        )
        session.add(older)
        await session.commit()

    response = await api_client.get(f"/ideas/{idea_id}/runs")
    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == [str(run.id), str(older.id)]
    assert body[1]["status"] == "failed"

    assert (await api_client.get(f"/ideas/{uuid.uuid4()}/runs")).status_code == 404


async def test_rerun_step_enqueues_only_for_terminal_runs(
    api_client: AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    run, _ = await _create_run(db_session_factory, status=RunStatus.done)
    response = await api_client.post(f"/runs/{run.id}/steps/market/rerun")
    assert response.status_code == 202
    body = response.json()
    assert body["id"] == str(run.id)
    assert body["status"] == "pending"
    assert body["step"] == "market"
    assert body["finished_at"] is None
    assert body["error"] is None

    async with db_session_factory() as session:
        stored = await session.get(AnalysisRun, run.id)
        assert stored is not None
        assert stored.status is RunStatus.pending
        assert stored.step == "market"
        job = (await session.execute(select(Job))).scalar_one()
        assert job.kind == "rerun_run"
        assert job.payload == {"run_id": str(run.id), "step": "market"}

    assert (await api_client.post(f"/runs/{run.id}/steps/nope/rerun")).status_code == 404
    assert (await api_client.post(f"/runs/{uuid.uuid4()}/steps/market/rerun")).status_code == 404

    running, _ = await _create_run(db_session_factory, status=RunStatus.running)
    assert (await api_client.post(f"/runs/{running.id}/steps/market/rerun")).status_code == 409


async def test_clarify_endpoint_validates_and_enqueues(
    api_client: AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    awaiting, _ = await _create_run(
        db_session_factory,
        status=RunStatus.awaiting_input,
        questions=[{"question": "Who?", "why": "Narrows research."}],
    )

    response = await api_client.post(
        f"/runs/{awaiting.id}/clarify",
        json={"answers": ["  Urban owners  ", "Vets"]},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "awaiting_input"
    assert response.json()["questions"][0]["question"] == "Who?"

    async with db_session_factory() as session:
        job = (await session.execute(select(Job))).scalar_one()
        assert job.kind == "resume_run"
        assert job.payload == {
            "run_id": str(awaiting.id),
            "answers": ["Urban owners", "Vets"],
            "skip": False,
        }

    assert (
        await api_client.post(f"/runs/{awaiting.id}/clarify", json={"answers": [], "skip": False})
    ).status_code == 422
    assert (
        await api_client.post(
            f"/runs/{awaiting.id}/clarify", json={"answers": ["a", "b", "c", "d"]}
        )
    ).status_code == 422
    assert (
        await api_client.post(f"/runs/{awaiting.id}/clarify", json={"answers": ["a"], "skip": True})
    ).status_code == 422
    assert (
        await api_client.post(f"/runs/{awaiting.id}/clarify", json={"answers": [""]})
    ).status_code == 422
    assert (await api_client.post(f"/runs/{awaiting.id}/clarify", json={})).status_code == 422

    skipped = await api_client.post(f"/runs/{awaiting.id}/clarify", json={"skip": True})
    assert skipped.status_code == 202

    done, _ = await _create_run(db_session_factory, status=RunStatus.done)
    assert (
        await api_client.post(f"/runs/{done.id}/clarify", json={"answers": ["x"]})
    ).status_code == 409
    assert (await api_client.post(f"/runs/{uuid.uuid4()}/clarify", json={})).status_code == 404
