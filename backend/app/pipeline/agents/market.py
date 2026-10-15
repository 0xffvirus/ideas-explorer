"""Market agent: TAM/SAM/SOM, trends, and timing backed by web evidence."""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models import Model

from app.config import Settings
from app.pipeline.agents.base import PipelineDeps, build_agent
from app.pipeline.outputs import MarketSection
from app.pipeline.prompts import load_prompt


def build_market_agent(
    model: Model | str | None = None, settings: Settings | None = None
) -> Agent[PipelineDeps, MarketSection]:
    """Build the market agent; web search only."""
    return build_agent(
        model=model or (settings.market_model if settings is not None else None),
        output_type=MarketSection,
        instructions=load_prompt("market"),
        tool_keys=("web",),
    )
