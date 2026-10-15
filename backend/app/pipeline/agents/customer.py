"""Customer agent: personas, communities, pain quotes, and optional leads."""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models import Model

from app.config import Settings
from app.pipeline.agents.base import PipelineDeps, build_agent
from app.pipeline.outputs import CustomerSection
from app.pipeline.prompts import load_prompt


def build_customer_agent(
    model: Model | str | None = None, settings: Settings | None = None
) -> Agent[PipelineDeps, CustomerSection]:
    """Build the customer agent; community tools plus web and (disabled) leads."""
    return build_agent(
        model=model or (settings.customer_model if settings is not None else None),
        output_type=CustomerSection,
        instructions=load_prompt("customer"),
        tool_keys=("reddit", "hn", "web", "leads"),
    )
