"""Shared agent wiring: pipeline dependencies and the gated search tools.

Research tools are exposed to agents as Pydantic AI tools. Each tool call goes
through ``Gate.filter_evidence`` before anything is returned, so agents only
ever see evidence Jev judged relevant. Tool results are JSON-serializable
``Evidence`` dumps carrying real source URLs, wrapped in
``<untrusted_evidence>`` tags so the model treats them as data, never
instructions.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from app.jev import Gate
from app.research import Evidence, ResearchError, ResearchTool

UNTRUSTED_EVIDENCE_OPEN = "<untrusted_evidence>"
UNTRUSTED_EVIDENCE_CLOSE = "</untrusted_evidence>"


def wrap_untrusted_evidence(payload: Any) -> str:
    """Frame a tool result as untrusted third-party data for the model."""
    body = json.dumps(payload, ensure_ascii=False, default=str)
    return f"{UNTRUSTED_EVIDENCE_OPEN}\n{body}\n{UNTRUSTED_EVIDENCE_CLOSE}"


@dataclass
class PipelineDeps:
    """Run-time dependencies every pipeline agent receives."""

    tools: Mapping[str, ResearchTool]
    gate: Gate


async def _search_evidence(
    ctx: RunContext[PipelineDeps],
    key: str,
    query: str,
    limit: int,
) -> str:
    tool = ctx.deps.tools.get(key)
    if tool is None:
        return wrap_untrusted_evidence([])
    try:
        results = await tool.search(query, limit=limit)
    except ResearchError:
        return wrap_untrusted_evidence([])
    if not results:
        return wrap_untrusted_evidence([])
    filtered = await ctx.deps.gate.filter_evidence(query, results)
    payload = [item.model_dump(mode="json") for item in cast("list[Evidence]", filtered)]
    return wrap_untrusted_evidence(payload)


async def web_search(ctx: RunContext[PipelineDeps], query: str, limit: int = 8) -> str:
    """Search the open web for market, competitor, and regulation evidence."""
    return await _search_evidence(ctx, "web", query, limit)


async def reddit_search(ctx: RunContext[PipelineDeps], query: str, limit: int = 8) -> str:
    """Search Reddit posts and comments where target users describe the pain."""
    return await _search_evidence(ctx, "reddit", query, limit)


async def hn_search(ctx: RunContext[PipelineDeps], query: str, limit: int = 8) -> str:
    """Search Hacker News stories and comments for demand and founder signals."""
    return await _search_evidence(ctx, "hn", query, limit)


async def leads_search(ctx: RunContext[PipelineDeps], query: str, limit: int = 8) -> str:
    """Look up company-level leads that fit the target-customer profile."""
    return await _search_evidence(ctx, "leads", query, limit)


SEARCH_TOOLS: dict[str, Any] = {
    "web": web_search,
    "reddit": reddit_search,
    "hn": hn_search,
    "leads": leads_search,
}


def build_agent(
    *,
    model: Model | str | None,
    output_type: Any,
    instructions: str,
    tool_keys: Sequence[str] = (),
    retries: int = 0,
) -> Agent[PipelineDeps, Any]:
    """Build one agent with the requested gated search tools and output schema.

    ``retries`` defaults to zero: the orchestrator owns the single schema
    feedback retry, so one validation failure costs exactly two model calls.
    """
    return Agent(
        model,
        output_type=output_type,
        instructions=instructions,
        deps_type=PipelineDeps,
        retries=retries,
        tools=[SEARCH_TOOLS[key] for key in tool_keys],
    )
