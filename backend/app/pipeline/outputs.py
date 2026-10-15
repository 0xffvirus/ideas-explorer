"""Typed outputs produced by the pipeline agents and the final analysis result.

Every factual field carries ``claims: list[Claim]``. Prompts instruct agents to
put each fact, number, or quote in a claim together with the source URLs of the
research results that support it; :class:`app.jev.gate.Gate` verifies them and
the final :class:`AnalysisResult` carries their verification status as
:class:`ClaimRef` items.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

from app.jev import Claim, ClaimStatus, Classification, Scorecard, Verdict
from app.research import CompanyLead


class IdeaBrief(BaseModel):
    """The polished version of the user's raw input."""

    title: str = Field(min_length=1, max_length=80)
    one_liner: str
    problem: str
    solution: str
    target_users: str
    value_prop: str
    key_assumptions: list[str] = Field(default_factory=list[str])
    variants: list[str] = Field(default_factory=list[str], max_length=3)
    claims: list[Claim] = Field(default_factory=list[Claim])


class ClarifyingQuestion(BaseModel):
    """One question the clarifier asks before spending research budget."""

    question: str
    why: str


class MarketSize(BaseModel):
    """One TAM/SAM/SOM estimate with the method and sources behind it."""

    value: str
    method: str
    sources: list[HttpUrl] = Field(default_factory=list[HttpUrl])


class MarketSection(BaseModel):
    """Market size, trends, and why-now timing."""

    tam: MarketSize
    sam: MarketSize
    som: MarketSize
    trends: list[Claim] = Field(default_factory=list[Claim])
    timing_why_now: Claim
    claims: list[Claim] = Field(default_factory=list[Claim])


class Competitor(BaseModel):
    """One competitor and the gap it leaves open."""

    name: str
    url: HttpUrl
    positioning: str
    pricing: str
    gap: str


class CompetitorSection(BaseModel):
    """Competitive landscape plus the differentiation wedge."""

    competitors: list[Competitor] = Field(default_factory=list[Competitor])
    differentiation: Claim
    claims: list[Claim] = Field(default_factory=list[Claim])


class Persona(BaseModel):
    """One target-customer persona."""

    name: str
    description: str
    pains: list[str] = Field(default_factory=list[str])
    where_they_gather: list[str] = Field(default_factory=list[str])


class Community(BaseModel):
    """A place where the target users gather online."""

    name: str
    url: HttpUrl
    why: str


class PainQuote(BaseModel):
    """A real quote expressing the pain, with its source."""

    quote: str
    url: HttpUrl
    context: str


class CustomerSection(BaseModel):
    """Personas, communities, pain quotes, and optional company leads."""

    personas: list[Persona] = Field(default_factory=list[Persona])
    communities: list[Community] = Field(default_factory=list[Community])
    pain_quotes: list[PainQuote] = Field(default_factory=list[PainQuote])
    early_adopter_profile: str
    leads: list[CompanyLead] | None = None
    claims: list[Claim] = Field(default_factory=list[Claim])


class Risk(BaseModel):
    """One execution risk with likelihood, impact, and a mitigation."""

    description: str
    likelihood: int = Field(ge=1, le=5)
    impact: int = Field(ge=1, le=5)
    mitigation: str


class FeasibilitySection(BaseModel):
    """Technical, operational, legal, cost, and timeline feasibility."""

    technical: str
    operational: str
    legal_regulatory: str
    mvp_cost_range: str
    mvp_timeline: str
    risks: list[Risk] = Field(default_factory=list[Risk])
    claims: list[Claim] = Field(default_factory=list[Claim])


class PricingOption(BaseModel):
    """One candidate price point."""

    name: str
    price_point: str
    notes: str


class UnitEconomics(BaseModel):
    """Rough CAC/LTV estimates with their stated assumptions."""

    cac_estimate: str
    ltv_estimate: str
    assumptions: list[str] = Field(default_factory=list[str])


class BusinessModelSection(BaseModel):
    """Lean canvas, revenue, pricing, unit economics, and go-to-market."""

    lean_canvas: dict[str, str] = Field(default_factory=dict[str, str])
    revenue_streams: list[str] = Field(default_factory=list[str])
    pricing_options: list[PricingOption] = Field(default_factory=list[PricingOption])
    unit_economics: UnitEconomics
    go_to_market: list[str] = Field(default_factory=list[str])
    claims: list[Claim] = Field(default_factory=list[Claim])


class NextStep(BaseModel):
    """One cheap validation step the critic recommends."""

    assumption: str
    test: str
    cost_hint: str


class CriticOutput(BaseModel):
    """The critic's next steps (3-5) and the summary fed to Jev's verdict."""

    next_steps: list[NextStep] = Field(min_length=3, max_length=5)
    summary: str


SectionName = Literal[
    "brief",
    "market",
    "competitors",
    "customers",
    "feasibility",
    "business_model",
]


class ClaimRef(BaseModel):
    """A section's claim plus Jev's verification status for the report label."""

    section: SectionName
    claim: Claim
    status: ClaimStatus = "unverified"
    confidence: float | None = None


class AnalysisResult(BaseModel):
    """The final artifact handed to the reports module."""

    run_id: uuid.UUID
    idea_id: uuid.UUID
    version_id: uuid.UUID
    brief: IdeaBrief
    classification: Classification | None = None
    market: MarketSection | None = None
    competitors: CompetitorSection | None = None
    customers: CustomerSection | None = None
    feasibility: FeasibilitySection | None = None
    business_model: BusinessModelSection | None = None
    scorecard: Scorecard
    verdict: Verdict
    claims: list[ClaimRef] = Field(default_factory=list[ClaimRef])
    next_steps: list[NextStep] = Field(default_factory=list[NextStep])
    cost_usd: float = 0.0
    sections_status: dict[str, str] = Field(default_factory=dict[str, str])
    generated_at: datetime
