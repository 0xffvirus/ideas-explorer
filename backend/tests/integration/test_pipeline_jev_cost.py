"""Integration test: Jev spend reaches the run's CostMeter through the gate factory."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import ModelPrice, settings_as_test_overrides
from app.cost import CostMeter
from app.ideas import IdeaCreate, IdeaService
from app.ideas.testing import FakeEmbedder
from app.jev import FakeJevClient, Gate, JevClient
from app.pipeline.models import AnalysisRun, RunStatus
from app.pipeline.orchestrator import Orchestrator
from tests.fixtures.pipeline.fakes import default_models, default_tools

pytestmark = pytest.mark.integration

RAW = "A smart collar for senior dogs that warns owners about early illness."
JEV_MODEL = "jev-latest"
INPUT_TOKENS = 1000
OUTPUT_TOKENS = 500
PRICE = ModelPrice(input=2.0, output=2.0)
PER_CALL_USD = INPUT_TOKENS / 1_000_000 * PRICE.input + OUTPUT_TOKENS / 1_000_000 * PRICE.output


def _jev_response(payload: dict[str, Any]) -> httpx.Response:
    answers: dict[str, Any] = {}
    for question_id, question in payload["questions"].items():
        kind = question["type"]
        if kind == "choice":
            choice = next(iter(question["criteria"]), "other")
            answers[question_id] = {"type": "choice", "choice": choice, "confidence": 0.9}
        elif kind == "score":
            levels = len(question["criteria"])
            answers[question_id] = {
                "type": "score",
                "score": max(0.0, (levels - 1) / 2),
                "confidence": 0.9,
            }
        else:
            answers[question_id] = {"type": "noul", "noul": 0.9}
    return httpx.Response(
        200,
        json={
            "model": JEV_MODEL,
            "answers": answers,
            "usage": {"input_tokens": INPUT_TOKENS, "output_tokens": OUTPUT_TOKENS},
        },
    )


async def _create_run(session_factory: async_sessionmaker[AsyncSession]) -> AnalysisRun:
    async with session_factory() as session:
        service = IdeaService(session, FakeEmbedder())
        detail = await service.create(IdeaCreate(raw_input=RAW, analyze=False))
        run = AnalysisRun(
            idea_id=detail.id,
            idea_version_id=detail.latest_version.id,
            status=RunStatus.running,
            step="refine",
            cost_cap_usd=Decimal("0"),
            started_at=datetime.now(UTC),
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run


async def test_gate_factory_meters_jev_usage_into_the_run_cost(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        return _jev_response(payload)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    fallback = FakeJevClient()
    meters: list[CostMeter] = []

    def gate_factory(meter: CostMeter) -> Gate:
        meters.append(meter)
        return Gate(
            JevClient(
                api_key="test-key",
                base_url="https://jev.test/v1",
                model=JEV_MODEL,
                timeout_seconds=5.0,
                http_client=http,
                meter=meter,
                pricing={JEV_MODEL: PRICE},
            )
        )

    run = await _create_run(db_session_factory)
    try:
        orchestrator = Orchestrator(
            db_session_factory,
            settings_as_test_overrides(run_cost_cap_usd=0.0),
            gate=Gate(fallback),
            tools=default_tools(),
            embedder=FakeEmbedder(),
            models=default_models(),  # type: ignore[arg-type]
            jev=None,
            gate_factory=gate_factory,
        )
        result = await orchestrator.execute(run.id)
    finally:
        await http.aclose()

    assert result is not None
    assert fallback.calls == []
    assert len(meters) == 1
    assert requests
    assert meters[0].by_category["jev"] == pytest.approx(len(requests) * PER_CALL_USD)
    assert result.cost_usd == pytest.approx(meters[0].spent_usd, abs=1e-6)
    assert result.cost_usd >= meters[0].by_category["jev"]

    async with db_session_factory() as session:
        stored = await session.get(AnalysisRun, run.id)
        assert stored is not None
        assert stored.status is RunStatus.done
        assert float(stored.cost_usd) == pytest.approx(result.cost_usd, abs=1e-6)
