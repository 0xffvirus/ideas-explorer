"""Contract and transport tests for JevClient against recorded fixtures."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from tenacity import wait_none

import app.jev.client as client_module
from app.config import ModelPrice
from app.cost import CostMeter
from app.jev import (
    ChoiceAnswer,
    ChoiceQuestion,
    Claim,
    Gate,
    JevClient,
    JevProtocolError,
    JevUnavailableError,
    NoulAnswer,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "jev"

QUESTIONS: dict[str, Any] = {
    "department": ChoiceQuestion(
        instructions="Which department?",
        criteria={"billing": "Payment issues.", "technical": "Technical issues."},
    ),
    "frustration": ScoreQuestion(
        instructions="How frustrated is the customer?",
        criteria=["calm", "annoyed", "furious"],
    ),
    "is_urgent": NoulQuestion(
        instructions="Is this urgent?",
        criteria={"true": "Urgent.", "false": "Not urgent."},
    ),
}


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text())


def make_client(
    responder: Callable[[httpx.Request], httpx.Response | Awaitable[httpx.Response]],
    **kwargs: Any,
) -> tuple[JevClient, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        response = responder(request)
        if isinstance(response, Awaitable):
            response = await response
        return response

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = JevClient(
        "test-key",
        base_url="https://jev.test/v1",
        model="jev-latest",
        timeout_seconds=1.0,
        http_client=http_client,
        **kwargs,
    )
    return client, requests


def noul_response(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    answers = {qid: {"type": "noul", "noul": 0.9} for qid in body["questions"]}
    return httpx.Response(
        200,
        json={
            "model": "jev-test",
            "answers": answers,
            "usage": {"input_tokens": 2, "output_tokens": 1},
        },
    )


async def test_ask_maps_recorded_response_into_typed_answers() -> None:
    client, requests = make_client(
        lambda request: httpx.Response(200, json=load_fixture("valid_response.json"))
    )
    result = await client.ask("A customer cannot log in.", QUESTIONS)

    assert isinstance(result.answers["department"], ChoiceAnswer)
    assert result.answers["department"].choice == "technical"
    assert result.answers["department"].confidence == 1.0
    assert result.answers["department"].probabilities == {"technical": 1.0, "billing": 0.0}
    assert isinstance(result.answers["frustration"], ScoreAnswer)
    assert result.answers["frustration"].score == 0.67
    assert result.answers["frustration"].legend == {"0": "calm", "1": "annoyed", "2": "furious"}
    assert isinstance(result.answers["is_urgent"], NoulAnswer)
    assert result.answers["is_urgent"].noul == 0.99
    assert result.usage.input_tokens == 428
    assert result.usage.output_tokens == 73
    assert result.raw_model == "jev-1.13.0"
    assert len(requests) == 1


async def test_request_uses_the_documented_wire_format() -> None:
    client, requests = make_client(
        lambda request: httpx.Response(200, json=load_fixture("valid_response.json"))
    )
    client_questions = {
        "department": ChoiceQuestion(
            instructions="Which department?",
            criteria={"billing": "Payment issues.", "technical": None},
        ),
        "is_urgent": NoulQuestion(instructions="Is this urgent?"),
    }
    await client.ask("state text", client_questions)

    request = requests[0]
    assert str(request.url) == "https://jev.test/v1/systemone"
    assert request.headers["authorization"] == "Bearer test-key"
    body = json.loads(request.content)
    assert body["state"] == "state text"
    assert body["model"] == "jev-latest"
    assert body["questions"]["department"]["type"] == "choice"
    assert body["questions"]["department"]["criteria"]["technical"] is None
    assert "criteria" not in body["questions"]["is_urgent"]


async def test_unknown_answer_type_raises_protocol_error() -> None:
    client, _ = make_client(
        lambda request: httpx.Response(200, json=load_fixture("unknown_type_response.json"))
    )
    with pytest.raises(JevProtocolError, match="invalid answer"):
        await client.ask("state", QUESTIONS)


async def test_missing_answer_raises_protocol_error() -> None:
    client, _ = make_client(
        lambda request: httpx.Response(200, json=load_fixture("missing_answer_response.json"))
    )
    with pytest.raises(JevProtocolError, match="no answer"):
        await client.ask("state", QUESTIONS)


async def test_http_4xx_raises_protocol_error_without_retry() -> None:
    client, requests = make_client(
        lambda request: httpx.Response(422, json={"detail": "invalid request"})
    )
    with pytest.raises(JevProtocolError, match="422"):
        await client.ask("state", QUESTIONS)
    assert len(requests) == 1


async def test_retryable_status_retries_twice_then_raises_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module, "_RETRY_WAIT", wait_none())
    client, requests = make_client(lambda request: httpx.Response(500, text="boom"))
    with pytest.raises(JevUnavailableError):
        await client.ask("state", QUESTIONS)
    assert len(requests) == 3


async def test_429_is_retried_and_then_raises_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module, "_RETRY_WAIT", wait_none())
    client, requests = make_client(lambda request: httpx.Response(429, text="slow down"))
    with pytest.raises(JevUnavailableError):
        await client.ask("state", QUESTIONS)
    assert len(requests) == 3


async def test_connect_error_retries_twice_then_raises_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module, "_RETRY_WAIT", wait_none())

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client, requests = make_client(refuse)
    with pytest.raises(JevUnavailableError):
        await client.ask("state", QUESTIONS)
    assert len(requests) == 3


async def test_ask_chunks_45_questions_into_3_concurrent_calls() -> None:
    requests: list[httpx.Request] = []
    active = 0
    max_active = 0
    all_started = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, max_active
        requests.append(request)
        active += 1
        max_active = max(max_active, active)
        if active == 3:
            all_started.set()
        await asyncio.wait_for(all_started.wait(), timeout=2.0)
        active -= 1
        return noul_response(request)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = JevClient(
        "test-key",
        base_url="https://jev.test/v1",
        model="jev-latest",
        timeout_seconds=1.0,
        http_client=http_client,
    )
    questions = {
        f"q{index:02d}": NoulQuestion(instructions=f"Question {index}") for index in range(45)
    }
    result = await client.ask("state", questions)

    assert len(requests) == 3
    assert max_active == 3
    assert sorted(len(json.loads(request.content)["questions"]) for request in requests) == [
        5,
        20,
        20,
    ]
    assert len(result.answers) == 45
    assert result.usage.input_tokens == 6
    assert result.usage.output_tokens == 3


async def test_ask_without_questions_makes_no_call() -> None:
    client, requests = make_client(noul_response)
    result = await client.ask("state", {})
    assert result.answers == {}
    assert requests == []


async def test_usage_is_charged_to_the_meter_with_pricing() -> None:
    meter = CostMeter()
    pricing = {"jev-latest": ModelPrice(input=1.0, output=2.0)}
    client, _ = make_client(
        lambda request: httpx.Response(200, json=load_fixture("valid_response.json")),
        meter=meter,
        pricing=pricing,
    )
    await client.ask("state", QUESTIONS)

    expected = 428 / 1_000_000 * 1.0 + 73 / 1_000_000 * 2.0
    assert meter.by_category["jev"] == pytest.approx(expected)
    assert meter.spent_usd == pytest.approx(expected)


async def test_usage_is_not_charged_without_pricing() -> None:
    meter = CostMeter()
    client, _ = make_client(
        lambda request: httpx.Response(200, json=load_fixture("valid_response.json")),
        meter=meter,
    )
    await client.ask("state", QUESTIONS)
    assert meter.by_category == {}
    assert meter.spent_usd == 0.0


async def test_gate_verify_claims_40_claims_uses_two_http_calls() -> None:
    client, requests = make_client(noul_response)
    gate = Gate(client)
    claims = [Claim(text=f"claim number {index}", source_urls=[]) for index in range(40)]
    verified = await gate.verify_claims(claims)

    assert len(requests) == 2
    assert sorted(len(json.loads(request.content)["questions"]) for request in requests) == [20, 20]
    assert len(verified) == 40
    assert all(item.verified for item in verified)
    assert all(item.confidence == 0.9 for item in verified)


async def test_gate_methods_return_unavailable_when_the_transport_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client_module, "_RETRY_WAIT", wait_none())

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client, _ = make_client(refuse)
    gate = Gate(client)

    classification = await gate.classify("a brief")
    assert classification.source == "unavailable"
    assert classification.category is None
    assert classification.needs_review is True

    scorecard = await gate.scorecard(
        {
            "problem": "p",
            "market": "m",
            "competitors": "c",
            "customers": "u",
            "feasibility": "f",
            "business_model": "b",
        }
    )
    assert all(item.source == "unavailable" for item in scorecard.dimensions)
    assert all(item.score is None for item in scorecard.dimensions)

    verified = await gate.verify_claims([Claim(text="a claim")])
    assert verified[0].status == "unavailable"

    verdict = await gate.verdict("a summary")
    assert verdict.source == "unavailable"
    assert verdict.decision is None
