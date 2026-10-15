"""Application settings.

Every env var lives here. Modules must read settings through :func:`get_settings`
and never touch ``os.environ`` directly.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelPrice(BaseModel):
    """USD per 1M tokens."""

    input: float = 0.0
    output: float = 0.0


def _default_model_pricing() -> dict[str, ModelPrice]:
    return {
        "openai:gpt-4o": ModelPrice(input=2.50, output=10.00),
        "openai:gpt-4o-mini": ModelPrice(input=0.15, output=0.60),
        "openai:text-embedding-3-small": ModelPrice(input=0.02, output=0.0),
    }


def _default_score_weights() -> dict[str, float]:
    return {
        "problem_severity": 0.20,
        "market_evidence": 0.20,
        "competition_intensity": 0.15,
        "customer_reachability": 0.15,
        "feasibility": 0.15,
        "monetization_clarity": 0.15,
    }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ app
    environment: str = "dev"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://idea:idea@localhost:5432/idea_forge"

    # ------------------------------------------------- openai (llm + embed)
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Per-agent models, "provider:model" (see SPEC.md tech stack).
    refiner_model: str = "openai:gpt-4o-mini"
    clarifier_model: str = "openai:gpt-4o-mini"
    market_model: str = "openai:gpt-4o"
    competitor_model: str = "openai:gpt-4o"
    customer_model: str = "openai:gpt-4o"
    feasibility_model: str = "openai:gpt-4o"
    business_model_model: str = "openai:gpt-4o"
    critic_model: str = "openai:gpt-4o"

    # Pricing table for CostMeter, keyed by "provider:model".
    model_pricing: dict[str, ModelPrice] = Field(default_factory=_default_model_pricing)

    # ----------------------------------------------------- typesafe / jev
    typesafe_api_key: str = ""
    jev_base_url: str = "https://api.typesafe.ai/v1"
    jev_model: str = "jev-latest"
    jev_timeout_seconds: float = 60.0
    jev_max_questions_per_call: int = 20
    jev_confidence_floor: float = 0.6
    jev_claim_threshold: float = 0.7
    jev_input_usd_per_million: float = 0.0
    jev_output_usd_per_million: float = 0.0

    # ---------------------------------------------------- research-tools
    tavily_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "idea-forge/0.1 (personal research)"

    leads_enabled: bool = False
    leads_api_key: str = ""

    research_web_ttl_hours: int = 168  # 7 days
    research_community_ttl_hours: int = 24  # 1 day
    research_timeout_seconds: float = 10.0
    research_max_retries: int = 2
    research_snippet_max_chars: int = 1500

    web_rate_limit_per_minute: int = 60
    reddit_rate_limit_per_minute: int = 100
    hn_rate_limit_per_minute: int = 60
    leads_rate_limit_per_minute: int = 30

    tavily_cost_per_search_usd: float = 0.008

    # ------------------------------------------------------ agent-pipeline
    run_cost_cap_usd: float = 0.75
    step_timeout_seconds: float = 120.0
    step_max_retries: int = 2
    max_parallel_research_agents: int = 3
    worker_poll_interval_seconds: float = 1.0
    worker_job_stale_seconds: float = 900.0
    max_critic_reresearch_passes: int = 1

    # ------------------------------------------------------------ reports
    report_score_weights: dict[str, float] = Field(default_factory=_default_score_weights)
    pdf_render_timeout_seconds: float = 10.0

    # ---------------------------------------------------------------- api
    api_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Used by tests that tweak the environment."""
    get_settings.cache_clear()


def settings_as_test_overrides(**overrides: Any) -> Settings:
    """Build a Settings instance ignoring the .env file (tests only)."""
    return Settings(_env_file=None, **overrides)  # pyright: ignore[reportCallIssue]
