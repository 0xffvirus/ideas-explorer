"""Refiner agent: raw input plus clarifying answers into an IdeaBrief."""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models import Model

from app.config import Settings
from app.pipeline.agents.base import PipelineDeps, build_agent
from app.pipeline.outputs import IdeaBrief
from app.pipeline.prompts import load_prompt


def build_refiner_agent(
    model: Model | str | None = None, settings: Settings | None = None
) -> Agent[PipelineDeps, IdeaBrief]:
    """Build the refiner; no tools, small model."""
    return build_agent(
        model=model or (settings.refiner_model if settings is not None else None),
        output_type=IdeaBrief,
        instructions=load_prompt("refiner"),
    )
