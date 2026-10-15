"""Critic agent: next validation steps and the summary fed to Jev's verdict."""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models import Model

from app.config import Settings
from app.pipeline.agents.base import PipelineDeps, build_agent
from app.pipeline.outputs import CriticOutput
from app.pipeline.prompts import load_prompt


def build_critic_agent(
    model: Model | str | None = None, settings: Settings | None = None
) -> Agent[PipelineDeps, CriticOutput]:
    """Build the critic; no tools, reads only the analysis it is given."""
    return build_agent(
        model=model or (settings.critic_model if settings is not None else None),
        output_type=CriticOutput,
        instructions=load_prompt("critic"),
    )
