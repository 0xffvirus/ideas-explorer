"""Feasibility agent: technical, operational, legal, cost, timeline, risks."""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models import Model

from app.config import Settings
from app.pipeline.agents.base import PipelineDeps, build_agent
from app.pipeline.outputs import FeasibilitySection
from app.pipeline.prompts import load_prompt


def build_feasibility_agent(
    model: Model | str | None = None, settings: Settings | None = None
) -> Agent[PipelineDeps, FeasibilitySection]:
    """Build the feasibility agent; web search only."""
    return build_agent(
        model=model or (settings.feasibility_model if settings is not None else None),
        output_type=FeasibilitySection,
        instructions=load_prompt("feasibility"),
        tool_keys=("web",),
    )
