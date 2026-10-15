"""Business model agent: lean canvas, pricing, unit economics, go-to-market."""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models import Model

from app.config import Settings
from app.pipeline.agents.base import PipelineDeps, build_agent
from app.pipeline.outputs import BusinessModelSection
from app.pipeline.prompts import load_prompt


def build_business_model_agent(
    model: Model | str | None = None, settings: Settings | None = None
) -> Agent[PipelineDeps, BusinessModelSection]:
    """Build the business-model agent; web search only."""
    return build_agent(
        model=model or (settings.business_model_model if settings is not None else None),
        output_type=BusinessModelSection,
        instructions=load_prompt("business_model"),
        tool_keys=("web",),
    )
