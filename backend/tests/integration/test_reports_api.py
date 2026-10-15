"""Integration tests for the reports router against real Postgres (no network)."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ideas import IdeaCreate, IdeaService
from app.ideas.testing import FakeEmbedder
from app.pipeline.models import AnalysisRun, RunStatus, RunStep, StepStatus
from app.reports.api import get_reports_session_factory, router
from app.reports.apply import apply_analysis_to_idea
from tests.fixtures.reports.fixtures import (
    URL_MARKET,
    URL_PRICING,
    make_result,
)

pytestmark = pytest.mark.integration

RAW = "A smart collar for senior dogs that warns owners about early illness."


async def _seed_report(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    raw: str = RAW,
    status: RunStatus = RunStatus.done,
    drop_sections: tuple[str, ...] = (),
) -> tuple[uuid.UUID, uuid.UUID]:
    async with session_factory() as session:
        service = IdeaService(session, FakeEmbedder())
        detail = await service.create(IdeaCreate(raw_input=raw, analyze=False))
        run = AnalysisRun(
            idea_id=detail.id,
            idea_version_id=detail.latest_version.id,
            status=status,
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
            drop_sections=drop_sections,
        )
        session.add(
            RunStep(
                run_id=run.id,
                step="critic",
                status=StepStatus.done,
                output={"critic": {}, "result": result.model_dump(mode="json")},
                cost_usd=Decimal("0.02"),
                model="openai:gpt-4o",
                attempts=1,
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
            )
        )
        await session.commit()
    await apply_analysis_to_idea(result, session_factory)
    return detail.id, run.id


async def _seed_empty_idea(session_factory: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    async with session_factory() as session:
        service = IdeaService(session, FakeEmbedder())
        detail = await service.create(IdeaCreate(raw_input=RAW, analyze=False))
        return detail.id


@pytest.fixture
async def api_client(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_reports_session_factory] = lambda: db_session_factory
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def test_report_json_shape(
    api_client: AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    idea_id, run_id = await _seed_report(db_session_factory)
    response = await api_client.get(f"/ideas/{idea_id}/report")
    assert response.status_code == 200
    body = response.json()
    assert body["idea_id"] == str(idea_id)
    assert body["run_id"] == str(run_id)
    assert body["header"]["title"] == "PetPulse"
    assert body["header"]["verdict"] == "refine"
    assert body["header"]["overall_score"] == pytest.approx(75.9)
    assert body["header"]["score_basis"] == "partial"
    assert body["cost_usd"] == pytest.approx(0.42)
    assert body["is_partial"] is False
    assert len(body["scorecard"]) == 6
    feasibility = next(item for item in body["scorecard"] if item["dimension"] == "feasibility")
    assert feasibility["score"] is None
    assert feasibility["source"] == "unavailable"
    assert [section["name"] for section in body["sections"]] == [
        "market",
        "competitors",
        "customers",
        "feasibility",
        "business_model",
    ]
    assert all(section["status"] == "complete" for section in body["sections"])
    assert [source["number"] for source in body["sources"]] == [1, 2, 3]
    assert body["sources"][0]["url"] == URL_MARKET
    assert body["brief"]["claims"][0]["citation_numbers"] == [1]
    assert len(body["next_steps"]) == 3

    version_response = await api_client.get(f"/ideas/{idea_id}/report?version=1")
    assert version_response.status_code == 200
    assert version_response.json()["run_id"] == str(run_id)
    assert (await api_client.get(f"/ideas/{idea_id}/report?version=99")).status_code == 422


async def test_report_not_found_cases(
    api_client: AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    empty_id = await _seed_empty_idea(db_session_factory)
    assert (await api_client.get(f"/ideas/{empty_id}/report")).status_code == 404
    assert (await api_client.get(f"/ideas/{uuid.uuid4()}/report")).status_code == 404
    assert (await api_client.get(f"/ideas/{empty_id}/report.md")).status_code == 404
    assert (await api_client.get(f"/ideas/{empty_id}/report.pdf")).status_code == 404


async def test_report_markdown_download(
    api_client: AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    idea_id, _ = await _seed_report(db_session_factory)
    response = await api_client.get(f"/ideas/{idea_id}/report.md")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in response.headers["content-disposition"]
    body = response.text
    assert "# PetPulse" in body
    assert f"1. {URL_MARKET}" in body
    assert f"2. {URL_PRICING}" in body
    assert "_(unverified)_" in body
    assert "## Sources" in body


async def test_report_pdf_download(
    api_client: AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    idea_id, _ = await _seed_report(db_session_factory)
    started = time.monotonic()
    response = await api_client.get(f"/ideas/{idea_id}/report.pdf")
    elapsed = time.monotonic() - started
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF-")
    assert len(response.content) > 1000
    assert elapsed < 5.0


async def test_report_pdf_returns_503_when_rendering_fails(
    api_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def explode(*args: object, **kwargs: object) -> bytes:
        raise RuntimeError("weasyprint exploded")

    monkeypatch.setattr("app.reports.api.render_pdf", explode)
    idea_id, _ = await _seed_report(db_session_factory)
    response = await api_client.get(f"/ideas/{idea_id}/report.pdf")
    assert response.status_code == 503
    assert "PDF rendering failed" in response.json()["detail"]


async def test_partial_run_renders_placeholders(
    api_client: AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    idea_id, _ = await _seed_report(
        db_session_factory, status=RunStatus.partial, drop_sections=("market",)
    )
    response = await api_client.get(f"/ideas/{idea_id}/report")
    assert response.status_code == 200
    body = response.json()
    assert body["is_partial"] is True
    market = next(section for section in body["sections"] if section["name"] == "market")
    assert market["status"] == "not_completed"
    assert market["json_payload"] == {}
    assert market["claims"] == []
    markdown = await api_client.get(f"/ideas/{idea_id}/report.md")
    assert markdown.status_code == 200
    assert "_Not completed._" in markdown.text


async def test_compare_two_ideas_aligned_by_dimension(
    api_client: AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    first, run_id = await _seed_report(db_session_factory, raw="First idea about dog collars.")
    second, _ = await _seed_report(db_session_factory, raw="Second idea about cat trackers.")
    response = await api_client.get(f"/compare?ids={first},{second}")
    assert response.status_code == 200
    body = response.json()
    assert body["dimensions"] == [
        "problem_severity",
        "market_evidence",
        "competition_intensity",
        "customer_reachability",
        "feasibility",
        "monetization_clarity",
    ]
    assert [entry["idea_id"] for entry in body["entries"]] == [str(first), str(second)]
    for entry in body["entries"]:
        assert entry["title"] == "PetPulse"
        assert entry["report"] is not None
        assert entry["reason"] is None
        assert entry["verdict"] == "refine"
        assert entry["overall_score"] == pytest.approx(75.9)
        dimensions = [row["dimension"] for row in entry["report"]["scorecard"]]
        assert dimensions == body["dimensions"]
    assert body["entries"][0]["report"]["header"]["score_basis"] == "partial"
    report_response = await api_client.get(f"/ideas/{first}/report")
    assert report_response.json()["run_id"] == str(run_id)


async def test_compare_three_ideas_returns_200(
    api_client: AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    first, _ = await _seed_report(db_session_factory, raw="First idea about dog collars.")
    second, _ = await _seed_report(db_session_factory, raw="Second idea about cat trackers.")
    third, _ = await _seed_report(db_session_factory, raw="Third idea about bird feeders.")
    response = await api_client.get(f"/compare?ids={first},{second},{third}")
    assert response.status_code == 200
    body = response.json()
    assert [entry["idea_id"] for entry in body["entries"]] == [
        str(first),
        str(second),
        str(third),
    ]
    assert body["dimensions"] == [
        "problem_severity",
        "market_evidence",
        "competition_intensity",
        "customer_reachability",
        "feasibility",
        "monetization_clarity",
    ]
    assert all(entry["report"] is not None for entry in body["entries"])
    assert all(entry["reason"] is None for entry in body["entries"])


async def test_compare_skips_idea_without_report(
    api_client: AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    with_report, _ = await _seed_report(db_session_factory)
    without_report = await _seed_empty_idea(db_session_factory)
    response = await api_client.get(f"/compare?ids={with_report},{without_report}")
    assert response.status_code == 200
    entries = response.json()["entries"]
    assert entries[1]["idea_id"] == str(without_report)
    assert entries[1]["report"] is None
    assert entries[1]["reason"]
    assert entries[1]["title"] is not None


async def test_compare_rejects_bad_id_lists(api_client: AsyncClient) -> None:
    first = str(uuid.uuid4())
    second = str(uuid.uuid4())
    third = str(uuid.uuid4())
    fourth = str(uuid.uuid4())
    assert (await api_client.get(f"/compare?ids={first}")).status_code == 422
    four = f"/compare?ids={first},{second},{third},{fourth}"
    assert (await api_client.get(four)).status_code == 422
    assert (await api_client.get(f"/compare?ids={first},{first}")).status_code == 422
    assert (await api_client.get(f"/compare?ids={first},not-a-uuid")).status_code == 422
    assert (await api_client.get("/compare")).status_code == 422
