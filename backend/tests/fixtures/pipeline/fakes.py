"""Shared offline fakes for pipeline tests: tools, agent models, and payloads.

No network, no real APIs. Import via ``tests.fixtures.pipeline.fakes``; the
tests directory is a namespace package on the backend root path.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage

from app.ideas.testing import FakeEmbedder
from app.jev import FakeJevClient, Gate
from app.research import Evidence

DEFAULT_URL = "https://example.com/evidence"


def make_evidence(
    source: str = "web",
    url: str = DEFAULT_URL,
    title: str = "Example evidence",
    snippet: str = "A sourced snippet supporting the claim.",
) -> Evidence:
    return Evidence(source=source, url=url, title=title, snippet=snippet, score=0.9)


def make_claim_urls() -> list[str]:
    return [DEFAULT_URL]


class FakeResearchTool:
    """Returns fixed evidence for any query and records the queries."""

    def __init__(self, name: str, items: list[Evidence] | None = None) -> None:
        self.name = name
        self.items = (
            items
            if items is not None
            else [make_evidence(source=name, url=f"https://example.com/{name}")]
        )
        self.queries: list[str] = []

    async def search(self, query: str, *, limit: int = 8) -> list[Evidence]:
        self.queries.append(query)
        return self.items[:limit]


def default_tools() -> dict[str, FakeResearchTool]:
    return {name: FakeResearchTool(name) for name in ("web", "reddit", "hn", "leads")}


def fake_gate() -> tuple[FakeJevClient, Gate]:
    client = FakeJevClient()
    return client, Gate(client)


def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


def claim_args(text: str = "A sourced fact.", urls: list[str] | None = None) -> dict[str, Any]:
    return {"text": text, "source_urls": urls if urls is not None else make_claim_urls()}


def brief_args(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "title": "PetPulse",
        "one_liner": "Early illness detection for senior dogs",
        "problem": "Owners miss early signs of illness in senior dogs.",
        "solution": "A smart collar and app that track activity and vitals.",
        "target_users": "City owners of dogs aged eight and older.",
        "value_prop": "Peace of mind from earlier detection.",
        "key_assumptions": ["Owners will pay monthly", "Sensors are accurate enough"],
        "variants": ["Vet partnership channel"],
        "claims": [claim_args("Senior dogs need frequent health monitoring.")],
    }
    data.update(overrides)
    return data


def clarify_args() -> list[dict[str, Any]]:
    return [
        {"question": "Who is the first customer?", "why": "Narrows the research."},
        {"question": "What do they use today?", "why": "Defines the alternative."},
    ]


def market_args(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "tam": {
            "value": "$4.2B",
            "method": "Top-down from pet care spend",
            "sources": [DEFAULT_URL],
        },
        "sam": {"value": "$900M", "method": "Urban senior-dog owners", "sources": [DEFAULT_URL]},
        "som": {"value": "$20M", "method": "1 percent of SAM in year three", "sources": []},
        "trends": [claim_args("Pet health spending is growing.")],
        "timing_why_now": claim_args("Cheap sensors make this possible now."),
        "claims": [claim_args("The pet health market is growing.")],
    }
    data.update(overrides)
    return data


def competitors_args(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "competitors": [
            {
                "name": "VetTrack",
                "url": DEFAULT_URL,
                "positioning": "Vet-first monitoring",
                "pricing": "$40/month",
                "gap": "No consumer self-serve track",
            }
        ],
        "differentiation": claim_args("The consumer wedge is early alerts without a vet visit."),
        "claims": [claim_args("VetTrack charges 40 dollars per month.")],
    }
    data.update(overrides)
    return data


def customers_args(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "personas": [
            {
                "name": "Anxious owner",
                "description": "Urban professional with an aging dog.",
                "pains": ["Fear of missing symptoms"],
                "where_they_gather": ["r/dogs"],
            }
        ],
        "communities": [{"name": "r/dogs", "url": DEFAULT_URL, "why": "Active owner community"}],
        "pain_quotes": [
            {
                "quote": "I wish I had caught it earlier.",
                "url": DEFAULT_URL,
                "context": "Senior dog health thread",
            }
        ],
        "early_adopter_profile": "Tech-savvy owners of dogs over eight.",
        "leads": None,
        "claims": [claim_args("Owners discuss missed symptoms online.")],
    }
    data.update(overrides)
    return data


def feasibility_args(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "technical": "Sensor firmware plus a mobile app.",
        "operational": "Support and replacements.",
        "legal_regulatory": "Consumer device and privacy rules.",
        "mvp_cost_range": "$40k-$70k",
        "mvp_timeline": "4-6 months",
        "risks": [
            {
                "description": "Sensor accuracy",
                "likelihood": 3,
                "impact": 4,
                "mitigation": "Bench test against vet data",
            }
        ],
        "claims": [claim_args("Consumer health devices need privacy review.")],
    }
    data.update(overrides)
    return data


def business_args(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "lean_canvas": {"problem": "Missed symptoms", "solution": "Collar and app"},
        "revenue_streams": ["Hardware sale", "Monthly subscription"],
        "pricing_options": [
            {"name": "Plus", "price_point": "$19/month", "notes": "Matches comparables"}
        ],
        "unit_economics": {
            "cac_estimate": "$45",
            "ltv_estimate": "$240",
            "assumptions": ["12 month retention"],
        },
        "go_to_market": ["Vet partnerships", "Breeder referrals"],
        "claims": [claim_args("Comparable subscriptions cost about 20 dollars.")],
    }
    data.update(overrides)
    return data


def critic_args(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "next_steps": [
            {"assumption": "Owners pay monthly", "test": "Pre-sale page", "cost_hint": "$200"},
            {"assumption": "Sensors detect issues", "test": "Bench prototype", "cost_hint": "$2k"},
            {"assumption": "Vets refer", "test": "Ten vet interviews", "cost_hint": "1 week"},
        ],
        "summary": (
            "The evidence supports a growing market and a reachable niche, but retention "
            "and sensor accuracy remain unproven. Test willingness to pay first."
        ),
    }
    data.update(overrides)
    return data


def prompt_text(messages: list[ModelMessage]) -> str:
    """Join the user-prompt parts of a model request into one string."""
    parts: list[str] = []
    for message in messages:
        if not isinstance(message, ModelRequest):
            continue
        for part in message.parts:
            if isinstance(part, UserPromptPart):
                content = part.content
                parts.append(content if isinstance(content, str) else str(content))
    return "\n".join(parts)


def output_model(
    args_factory: Callable[[], Any],
    *,
    label: str = "model",
    delay: float = 0.0,
    input_tokens: int = 10,
    output_tokens: int = 5,
    error: BaseException | None = None,
    calls: list[str] | None = None,
    intervals: list[tuple[str, float, float]] | None = None,
    model_name: str | None = None,
    prompts: list[str] | None = None,
) -> FunctionModel:
    """Build a FunctionModel that returns ``args_factory()`` as the final output."""

    async def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if calls is not None:
            calls.append(label)
        if prompts is not None:
            prompts.append(prompt_text(messages))
        started = time.monotonic()
        if delay:
            await asyncio.sleep(delay)
        if intervals is not None:
            intervals.append((label, started, time.monotonic()))
        if error is not None:
            raise error
        args: Any = args_factory()
        schema = info.output_tools[0].parameters_json_schema
        properties = schema.get("properties", {})
        if set(properties) == {"response"}:
            args = {"response": args}
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, args)],
            usage=RequestUsage(input_tokens=input_tokens, output_tokens=output_tokens),
        )

    return FunctionModel(fn, model_name=model_name)


def default_models(**overrides: FunctionModel) -> dict[str, FunctionModel]:
    """One deterministic fake model per step, with per-step overrides."""
    models: dict[str, FunctionModel] = {
        "refine": output_model(brief_args, label="refine"),
        "clarify": output_model(clarify_args, label="clarify"),
        "market": output_model(market_args, label="market"),
        "competitors": output_model(competitors_args, label="competitors"),
        "customers": output_model(customers_args, label="customers"),
        "feasibility": output_model(feasibility_args, label="feasibility"),
        "business_model": output_model(business_args, label="business_model"),
        "critic": output_model(critic_args, label="critic"),
    }
    models.update(overrides)
    return models
