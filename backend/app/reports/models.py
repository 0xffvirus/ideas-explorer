"""Report DTOs: the JSON-serializable shapes the reports module serves.

The assembler builds these from a run's :class:`~app.pipeline.outputs.AnalysisResult`;
the renderers and the API only read them, so every model here is a plain
Pydantic object with no database or pipeline references.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

SectionName = Literal["market", "competitors", "customers", "feasibility", "business_model"]
SectionStatus = Literal["complete", "not_completed"]
ScoreBasis = Literal["all_dimensions", "partial", "not_scored"]


class Source(BaseModel):
    """One deduplicated, numbered source behind the report's claims."""

    number: int
    url: str
    title: str = ""


class ReportClaim(BaseModel):
    """One claim with the citation numbers that resolve into ``Report.sources``."""

    text: str
    citation_numbers: list[int] = Field(default_factory=list[int])
    status: str = "unverified"


class ReportBrief(BaseModel):
    """The polished idea plus its numbered claims."""

    title: str
    one_liner: str
    problem: str
    solution: str
    target_users: str
    value_prop: str
    key_assumptions: list[str] = Field(default_factory=list[str])
    variants: list[str] = Field(default_factory=list[str])
    claims: list[ReportClaim] = Field(default_factory=list[ReportClaim])


class ReportSection(BaseModel):
    """One report section: its status, raw payload, rendered markdown, and claims."""

    name: SectionName
    title: str
    status: SectionStatus = "not_completed"
    json_payload: dict[str, Any] = Field(default_factory=dict[str, Any])
    markdown: str = ""
    claims: list[ReportClaim] = Field(default_factory=list[ReportClaim])


class NextStep(BaseModel):
    """One cheap validation step recommended by the critic."""

    assumption: str
    test: str
    cost_hint: str


class ScorecardEntry(BaseModel):
    """One scorecard row: the Jev score plus a rationale drawn from its section."""

    dimension: str
    label: str
    score: float | None = None
    confidence: float | None = None
    needs_review: bool = True
    source: str = "unavailable"
    rationale: str = ""


class ReportHeader(BaseModel):
    """The report's headline: identity, verdict, overall score, run date, and cost."""

    title: str
    one_liner: str
    verdict: str | None = None
    verdict_confidence: float | None = None
    overall_score: float | None = None
    score_basis: ScoreBasis = "not_scored"
    run_date: datetime
    cost_usd: float = 0.0


class Report(BaseModel):
    """One complete report for one analyzed idea version."""

    idea_id: uuid.UUID
    version_id: uuid.UUID
    run_id: uuid.UUID
    header: ReportHeader
    scorecard: list[ScorecardEntry] = Field(default_factory=list[ScorecardEntry])
    brief: ReportBrief
    sections: list[ReportSection] = Field(default_factory=list[ReportSection])
    next_steps: list[NextStep] = Field(default_factory=list[NextStep])
    sources: list[Source] = Field(default_factory=list[Source])
    generated_at: datetime
    run_date: datetime
    cost_usd: float = 0.0
    is_partial: bool = False


class CompareIdeaReport(BaseModel):
    """The slice of a report the compare view needs: header plus scorecard."""

    header: ReportHeader
    scorecard: list[ScorecardEntry] = Field(default_factory=list[ScorecardEntry])


class CompareEntry(BaseModel):
    """One idea's column in a side-by-side comparison.

    Ideas without a completed report keep their idea-row fields but carry
    ``report=None`` and the reason the report could not be built.
    """

    idea_id: uuid.UUID
    title: str | None = None
    one_liner: str | None = None
    verdict: str | None = None
    verdict_confidence: float | None = None
    overall_score: float | None = None
    category: str | None = None
    report: CompareIdeaReport | None = None
    reason: str | None = None


class CompareReport(BaseModel):
    """2-3 ideas aligned by dimension, ready for a side-by-side render."""

    dimensions: list[str] = Field(default_factory=list[str])
    entries: list[CompareEntry] = Field(default_factory=list[CompareEntry])
