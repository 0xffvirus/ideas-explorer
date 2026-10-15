"""Agent tool-call wiring: real agents, gated research tools, offline models.

Every other pipeline flow test returns final output from a ``FunctionModel``
without ever emitting a research ``ToolCallPart``. These tests exercise the
full loop: the model calls ``web_search``, the tool runs,
``Gate.filter_evidence`` filters the results, the payload is wrapped in
``<untrusted_evidence>`` tags, and only that gate output reaches the model
before it produces a schema-valid ``MarketSection``.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage

from app.jev import FakeJevClient, Gate
from app.pipeline.agents.base import (
    UNTRUSTED_EVIDENCE_CLOSE,
    UNTRUSTED_EVIDENCE_OPEN,
    PipelineDeps,
)
from app.pipeline.agents.market import build_market_agent
from app.pipeline.outputs import MarketSection
from app.research import Evidence
from tests.fixtures.pipeline.fakes import FakeResearchTool, make_evidence, market_args


class RecordingGate(Gate):
    """Gate whose evidence filter is scripted and recorded (no Jev calls)."""

    def __init__(self, transform: Callable[[list[Evidence]], list[Evidence]] | None = None) -> None:
        super().__init__(FakeJevClient())
        self.calls: list[tuple[str, list[Evidence]]] = []
        self._transform = transform

    async def filter_evidence(
        self,
        query: str,
        items: Sequence[Evidence],  # type: ignore[override]
    ) -> list[Evidence]:
        evidence = list(items)
        self.calls.append((query, evidence))
        if self._transform is not None:
            return self._transform(evidence)
        return evidence


def _tool_then_output_model(
    *,
    tool_name: str,
    tool_args: dict[str, Any],
    args_factory: Callable[[], Any],
    seen: list[list[ModelMessage]],
) -> FunctionModel:
    """A model that calls ``tool_name`` once, then returns the final output."""

    async def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen.append(list(messages))
        already_called = any(
            isinstance(part, ToolReturnPart)
            for message in messages
            if isinstance(message, ModelRequest)
            for part in message.parts
        )
        if not already_called:
            return ModelResponse(
                parts=[ToolCallPart(tool_name, tool_args)],
                usage=RequestUsage(input_tokens=10, output_tokens=5),
            )
        args: Any = args_factory()
        properties = info.output_tools[0].parameters_json_schema.get("properties", {})
        if set(properties) == {"response"}:
            args = {"response": args}
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, args)],
            usage=RequestUsage(input_tokens=20, output_tokens=10),
        )

    return FunctionModel(fn)


def _tool_payloads(messages: list[ModelMessage]) -> list[Any]:
    return [
        part.content
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    ]


def _unwrap(content: Any) -> Any:
    assert isinstance(content, str)
    body = content.removeprefix(UNTRUSTED_EVIDENCE_OPEN).removesuffix(UNTRUSTED_EVIDENCE_CLOSE)
    return json.loads(body.strip("\n"))


async def test_market_agent_searches_through_the_gate() -> None:
    raw = make_evidence(
        url="https://example.com/raw", title="RAW result", snippet="raw tool snippet"
    )
    gated = make_evidence(
        url="https://example.com/gated", title="GATED result", snippet="gate-filtered snippet"
    )
    tool = FakeResearchTool("web", items=[raw])
    gate = RecordingGate(transform=lambda items: [gated])
    seen: list[list[ModelMessage]] = []
    model = _tool_then_output_model(
        tool_name="web_search",
        tool_args={"query": "senior dog collar market", "limit": 3},
        args_factory=market_args,
        seen=seen,
    )
    agent = build_market_agent(model=model)
    deps = PipelineDeps(tools={"web": tool}, gate=gate)

    result = await agent.run("Analyze the market for a senior dog health collar.", deps=deps)

    assert tool.queries == ["senior dog collar market"]
    assert len(gate.calls) == 1
    query, items = gate.calls[0]
    assert query == "senior dog collar market"
    assert items == [raw]

    payloads = _tool_payloads(seen[-1])
    assert len(payloads) == 1
    assert isinstance(payloads[0], str)
    assert payloads[0].startswith(UNTRUSTED_EVIDENCE_OPEN)
    assert payloads[0].endswith(UNTRUSTED_EVIDENCE_CLOSE)
    assert payloads[0].count(UNTRUSTED_EVIDENCE_OPEN) == 1
    assert payloads[0].count(UNTRUSTED_EVIDENCE_CLOSE) == 1
    assert _unwrap(payloads[0]) == [gated.model_dump(mode="json")]
    serialized = json.dumps(payloads)
    assert "GATED result" in serialized
    assert "RAW result" not in serialized

    assert isinstance(result.output, MarketSection)
    assert result.output.tam.value == "$4.2B"


async def test_dropped_evidence_never_reaches_the_model() -> None:
    kept = make_evidence(url="https://example.com/kept", title="Kept result")
    dropped = make_evidence(url="https://example.com/dropped", title="Dropped result")
    tool = FakeResearchTool("web", items=[kept, dropped])

    def keep_relevant(items: list[Evidence]) -> list[Evidence]:
        return [item for item in items if str(item.url) != "https://example.com/dropped"]

    gate = RecordingGate(transform=keep_relevant)
    seen: list[list[ModelMessage]] = []
    model = _tool_then_output_model(
        tool_name="web_search",
        tool_args={"query": "senior dog collar market"},
        args_factory=market_args,
        seen=seen,
    )
    agent = build_market_agent(model=model)
    deps = PipelineDeps(tools={"web": tool}, gate=gate)

    await agent.run("Analyze the market for a senior dog health collar.", deps=deps)

    assert gate.calls[0][1] == [kept, dropped]
    payloads = _tool_payloads(seen[-1])
    assert len(payloads) == 1
    assert _unwrap(payloads[0]) == [kept.model_dump(mode="json")]
    serialized = json.dumps(payloads)
    assert "https://example.com/kept" in serialized
    assert "https://example.com/dropped" not in serialized
    assert "Dropped result" not in serialized
