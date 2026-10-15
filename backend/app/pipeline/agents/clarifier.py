"""Clarifier agent: at most three questions when the brief is not specific."""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models import Model

from app.config import Settings
from app.pipeline.agents.base import PipelineDeps, build_agent
from app.pipeline.outputs import ClarifyingQuestion
from app.pipeline.prompts import load_prompt


def build_clarifier_agent(
    model: Model | str | None = None, settings: Settings | None = None
) -> Agent[PipelineDeps, list[ClarifyingQuestion]]:
    """Build the clarifier; no tools, small model, at most three questions."""
    return build_agent(
        model=model or (settings.clarifier_model if settings is not None else None),
        output_type=list[ClarifyingQuestion],
        instructions=load_prompt("clarifier"),
    )
