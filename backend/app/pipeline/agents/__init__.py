"""Agent builders keyed by pipeline step name."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models import Model

from app.config import Settings
from app.pipeline.agents.base import SEARCH_TOOLS, PipelineDeps
from app.pipeline.agents.business_model import build_business_model_agent
from app.pipeline.agents.clarifier import build_clarifier_agent
from app.pipeline.agents.competitor import build_competitor_agent
from app.pipeline.agents.critic import build_critic_agent
from app.pipeline.agents.customer import build_customer_agent
from app.pipeline.agents.feasibility import build_feasibility_agent
from app.pipeline.agents.market import build_market_agent
from app.pipeline.agents.refiner import build_refiner_agent

AgentBuilder = Callable[[Model | str | None, Settings | None], "Agent[PipelineDeps, Any]"]

STEP_MODEL_ATTRS: dict[str, str] = {
    "refine": "refiner_model",
    "clarify": "clarifier_model",
    "market": "market_model",
    "competitors": "competitor_model",
    "customers": "customer_model",
    "feasibility": "feasibility_model",
    "business_model": "business_model_model",
    "critic": "critic_model",
}

_AGENT_BUILDERS: dict[str, AgentBuilder] = {
    "refine": build_refiner_agent,
    "clarify": build_clarifier_agent,
    "market": build_market_agent,
    "competitors": build_competitor_agent,
    "customers": build_customer_agent,
    "feasibility": build_feasibility_agent,
    "business_model": build_business_model_agent,
    "critic": build_critic_agent,
}


def build_step_agent(
    step: str,
    model: Model | str | None = None,
    settings: Settings | None = None,
) -> Agent[PipelineDeps, Any]:
    """Build the agent that owns ``step``."""
    builder = _AGENT_BUILDERS.get(step)
    if builder is None:
        raise ValueError(f"unknown pipeline step {step!r}")
    return builder(model, settings)


def default_model_string(step: str, settings: Settings) -> str:
    """Return the configured ``provider:model`` string for a step."""
    return str(getattr(settings, STEP_MODEL_ATTRS[step]))


__all__ = [
    "SEARCH_TOOLS",
    "STEP_MODEL_ATTRS",
    "AgentBuilder",
    "PipelineDeps",
    "build_step_agent",
    "default_model_string",
]
