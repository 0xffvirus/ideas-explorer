"""Competitor agent: the competitive landscape and the differentiation wedge."""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models import Model

from app.config import Settings
from app.pipeline.agents.base import PipelineDeps, build_agent
from app.pipeline.outputs import CompetitorSection
from app.pipeline.prompts import load_prompt


def build_competitor_agent(
    model: Model | str | None = None, settings: Settings | None = None
) -> Agent[PipelineDeps, CompetitorSection]:
    """Build the competitor agent; web search only."""
    return build_agent(
        model=model or (settings.competitor_model if settings is not None else None),
        output_type=CompetitorSection,
        instructions=load_prompt("competitor"),
        tool_keys=("web",),
    )
