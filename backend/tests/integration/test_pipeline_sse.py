"""Integration tests for SSE run-event streaming (httpx ASGITransport)."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import get_db_session
from app.ideas import IdeaCreate, IdeaService
from app.ideas.testing import FakeEmbedder
from app.pipeline.api import get_pipeline_session_factory, router
from app.pipeline.models import AnalysisRun, RunEvent, RunStatus

pytestmark = pytest.mark.integration


async def _seed_events(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    status: RunStatus = RunStatus.done,
    count: int = 3,
    names: list[str] | None = None,
) -> AnalysisRun:
    async with session_factory() as session:
        service = IdeaService(session, FakeEmbedder())
        detail = await service.create(IdeaCreate(raw_input="An idea about pets.", analyze=False))
        run = AnalysisRun(
            idea_id=detail.id,
            idea_version_id=detail.latest_version.id,
            status=status,
            step="critic",
            cost_cap_usd=Decimal("0.75"),
            started_at=datetime.now(UTC),
        )
        session.add(run)
        await session.flush()
        event_names = names or ["step_started", "step_completed", "run_done"]
        for index in range(count):
            session.add(
                RunEvent(
                    run_id=run.id,
                    seq=index + 1,
                    event=event_names[index % len(event_names)],
                    step="market" if index < count - 1 else None,
                    data={"index": index + 1},
                )
            )
        await session.commit()
        await session.refresh(run)
        return run


async def _parse_sse(response: Response) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    current: dict[str, str] = {}
    async for raw_line in response.aiter_lines():
        line = raw_line.rstrip("\r")
        if not line:
            if current:
                events.append(current)
                current = {}
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        current[field] = value.lstrip(" ")
    if current:
        events.append(current)
    return events


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


async def test_sse_replays_all_events_with_ascending_ids(
    api_client: AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    run = await _seed_events(db_session_factory)
    async with api_client.stream("GET", f"/runs/{run.id}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = await _parse_sse(response)

    assert [event["id"] for event in events] == ["1", "2", "3"]
    assert [event["event"] for event in events] == [
        "step_started",
        "step_completed",
        "run_done",
    ]
    assert events[0]["data"] == '{"index": 1}'


async def test_sse_last_event_id_replays_only_newer_events(
    api_client: AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    run = await _seed_events(db_session_factory)
    async with api_client.stream(
        "GET", f"/runs/{run.id}/events", headers={"Last-Event-ID": "2"}
    ) as response:
        assert response.status_code == 200
        events = await _parse_sse(response)

    assert [event["id"] for event in events] == ["3"]


async def test_sse_rejects_a_malformed_last_event_id_by_replaying_all(
    api_client: AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    run = await _seed_events(db_session_factory, count=1)
    async with api_client.stream(
        "GET", f"/runs/{run.id}/events", headers={"Last-Event-ID": "not-a-number"}
    ) as response:
        events = await _parse_sse(response)
    assert [event["id"] for event in events] == ["1"]


async def test_sse_returns_404_for_unknown_run(api_client: AsyncClient) -> None:
    response = await api_client.get(f"/runs/{uuid.uuid4()}/events")
    assert response.status_code == 404


async def test_event_generation_function_matches_stream(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    from app.pipeline.api import _events_after

    run = await _seed_events(db_session_factory, status=RunStatus.running, count=2)
    events, status = await _events_after(db_session_factory, run.id, 0)
    assert [event.seq for event in events] == [1, 2]
    assert status is RunStatus.running

    events, status = await _events_after(db_session_factory, run.id, 2)
    assert events == []
    assert status is RunStatus.running


async def test_sse_stream_ends_promptly_when_the_run_pauses(
    api_client: AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    run = await _seed_events(
        db_session_factory,
        status=RunStatus.awaiting_input,
        count=2,
        names=["step_started", "run_paused"],
    )
    async with api_client.stream("GET", f"/runs/{run.id}/events") as response:
        assert response.status_code == 200
        events = await asyncio.wait_for(_parse_sse(response), timeout=10)

    names = [event.get("event") for event in events]
    assert "run_paused" in names
    assert "step_started" in names
    assert {"retry": "30000"} in events


async def test_sse_pause_replay_with_last_event_id_still_ends(
    api_client: AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    run = await _seed_events(
        db_session_factory,
        status=RunStatus.awaiting_input,
        count=2,
        names=["step_started", "run_paused"],
    )
    async with api_client.stream(
        "GET", f"/runs/{run.id}/events", headers={"Last-Event-ID": "1"}
    ) as response:
        events = await asyncio.wait_for(_parse_sse(response), timeout=10)

    assert [event.get("event") for event in events if "event" in event] == ["run_paused"]
    assert {"retry": "30000"} in events
