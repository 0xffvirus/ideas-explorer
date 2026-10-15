"""Assemble a run's :class:`AnalysisResult` into a :class:`Report`.

The module splits cleanly in two layers:

* Pure helpers (``compute_overall_score``, ``score_basis``, ``number_sources``,
  ``dimension_rationale``, ``render_section_markdown``, ``verdict_label``) hold
  every rule that does not need the database, so they are unit-testable.
* :func:`build_report` is the thin loader: it resolves the idea version, finds
  the latest completed run, validates the stored ``AnalysisResult``, and hands
  it to :func:`assemble_report`.

Citation contract: sources are numbered by first appearance across the brief
claims, then the sections in canonical order; duplicates (exact URL match) keep
their first number; every number in a claim resolves, and no source is emitted
without a citing claim.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime

from pydantic import HttpUrl, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.ideas import EmbeddingError, IdeaNotFound, IdeaService
from app.jev import DimensionName, DimensionScore, Scorecard
from app.pipeline.engine import DIMENSION_OWNER_STEP
from app.pipeline.models import AnalysisRun, RunStatus, RunStep, StepStatus
from app.pipeline.outputs import (
    AnalysisResult,
    BusinessModelSection,
    ClaimRef,
    CompetitorSection,
    CustomerSection,
    FeasibilitySection,
    MarketSection,
)
from app.reports.models import (
    NextStep,
    Report,
    ReportBrief,
    ReportClaim,
    ReportHeader,
    ReportSection,
    ScoreBasis,
    ScorecardEntry,
    SectionName,
    Source,
)

COMPETITION_DIMENSION = "competition_intensity"
MAX_SCORE = 5.0
ROUND_DIGITS = 1

DIMENSION_ORDER: tuple[DimensionName, ...] = (
    "problem_severity",
    "market_evidence",
    "competition_intensity",
    "customer_reachability",
    "feasibility",
    "monetization_clarity",
)

SECTION_ORDER: tuple[SectionName, ...] = (
    "market",
    "competitors",
    "customers",
    "feasibility",
    "business_model",
)

SECTION_TITLES: dict[SectionName, str] = {
    "market": "Market",
    "competitors": "Competitors",
    "customers": "Customers",
    "feasibility": "Feasibility",
    "business_model": "Business model",
}

DIMENSION_LABELS: dict[str, str] = {
    "problem_severity": "Problem severity",
    "market_evidence": "Market evidence",
    "competition_intensity": "Competition intensity",
    "customer_reachability": "Customer reachability",
    "feasibility": "Feasibility",
    "monetization_clarity": "Monetization clarity",
}

VERDICT_LABELS: dict[str, str] = {
    "pursue": "Pursue",
    "refine": "Refine",
    "park": "Park",
}

SectionModel = (
    MarketSection | CompetitorSection | CustomerSection | FeasibilitySection | BusinessModelSection
)


class ReportNotFound(Exception):
    """Raised when an idea has no completed analysis to report on."""


class InvalidReportVersion(Exception):
    """Raised when the requested idea version does not exist."""


class NoopEmbedder:
    """Embedder that refuses all work; reports never create or reindex ideas."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingError("reports does not embed ideas")


def verdict_label(decision: str | None) -> str:
    """Human label for a Jev decision; ``"unknown"`` when there is none."""
    if decision is None:
        return "unknown"
    return VERDICT_LABELS.get(decision, decision)


def _normalized_score(dimension: str, score: float) -> float:
    """Map a 1-5 dimension score onto 0-1, inverting competition intensity."""
    if dimension == COMPETITION_DIMENSION:
        return (MAX_SCORE + 1.0 - score) / MAX_SCORE
    return score / MAX_SCORE


def _scoring_dimensions(scorecard: Scorecard, weights: Mapping[str, float]) -> list[DimensionScore]:
    """Dimensions that count toward the overall score.

    A dimension counts only when it carries a Jev score and a configured
    weight; unavailable or unscored dimensions drop out entirely.
    """
    return [
        entry
        for entry in scorecard.dimensions
        if entry.dimension in weights and entry.score is not None and entry.source == "jev"
    ]


def compute_overall_score(scorecard: Scorecard, weights: Mapping[str, float]) -> float | None:
    """Weighted mean of normalized dimension scores, scaled to 0-100.

    The denominator is the total weight of the *included* dimensions, so an
    excluded dimension changes the denominator and never the 0-100 scale.
    Returns ``None`` when no dimension is scorable.
    """
    included = _scoring_dimensions(scorecard, weights)
    total_weight = sum(weights[entry.dimension] for entry in included)
    if not included or total_weight <= 0:
        return None
    weighted = sum(
        _normalized_score(entry.dimension, float(entry.score)) * weights[entry.dimension]
        for entry in included
        if entry.score is not None
    )
    return round(weighted / total_weight * 100.0, ROUND_DIGITS)


def score_basis(scorecard: Scorecard, weights: Mapping[str, float]) -> ScoreBasis:
    """Whether every dimension was scored: ``all_dimensions``/``partial``/``not_scored``."""
    included = _scoring_dimensions(scorecard, weights)
    if not included:
        return "not_scored"
    if len(included) == len(scorecard.dimensions):
        return "all_dimensions"
    return "partial"


def number_sources(claims: Sequence[ClaimRef]) -> tuple[list[Source], list[ReportClaim]]:
    """Number claim sources by first appearance; deduplicate on exact URL.

    Returns the numbered source list and the claims with their citation numbers
    sorted ascending. Claims without URLs get no numbers, and sources are only
    emitted when a claim cites them, so there can be no orphan numbers.
    """
    numbers: dict[str, int] = {}
    sources: list[Source] = []
    numbered: list[ReportClaim] = []
    for ref in claims:
        seen: set[int] = set()
        for raw in ref.claim.source_urls:
            url = str(raw)
            number = numbers.get(url)
            if number is None:
                number = len(sources) + 1
                numbers[url] = number
                sources.append(Source(number=number, url=url, title=url))
            seen.add(number)
        numbered.append(
            ReportClaim(
                text=ref.claim.text,
                citation_numbers=sorted(seen),
                status=ref.status,
            )
        )
    return sources, numbered


def _one_line(value: str) -> str:
    return " ".join(value.split())


def _cell(value: str) -> str:
    return _one_line(value).replace("|", "\\|")


def _links(urls: Sequence[HttpUrl]) -> str:
    if not urls:
        return ""
    rendered = ", ".join(f"[source]({url})" for url in urls)
    return f" ({rendered})"


def _status_marker(status: str) -> str:
    if status == "verified":
        return ""
    if status == "unavailable":
        return " _(unverified: source unavailable)_"
    return " _(unverified)_"


def _claims_block(claims: Sequence[ReportClaim]) -> list[str]:
    if not claims:
        return []
    lines = ["", "### Claims", ""]
    for claim in claims:
        citations = "".join(f" [{number}]" for number in claim.citation_numbers)
        lines.append(f"- {_one_line(claim.text)}{citations}{_status_marker(claim.status)}")
    return lines


def _section_model(result: AnalysisResult, owner_step: str) -> SectionModel | None:
    match owner_step:
        case "market":
            return result.market
        case "competitors":
            return result.competitors
        case "customers":
            return result.customers
        case "feasibility":
            return result.feasibility
        case "business_model":
            return result.business_model
        case _:
            return None


def dimension_rationale(
    dimension: DimensionName,
    score: DimensionScore | None,
    result: AnalysisResult,
) -> str:
    """One-line rationale for a scorecard row, drawn from its owning section.

    Unscored dimensions fall back to an explicit reason instead of guessing.
    """
    owner_step = DIMENSION_OWNER_STEP[dimension]
    section = _section_model(result, owner_step) if owner_step != "refine" else None
    if score is None or score.score is None or score.source != "jev":
        if owner_step == "refine":
            return "Not scored: Jev unavailable."
        if section is None:
            return "Not scored: section not completed."
        return "Not scored: Jev unavailable."
    if dimension == "problem_severity":
        return _one_line(result.brief.problem)
    if dimension == "market_evidence" and isinstance(section, MarketSection):
        return _one_line(
            f"TAM {section.tam.value}, SAM {section.sam.value}, SOM {section.som.value}."
        )
    if dimension == "competition_intensity" and isinstance(section, CompetitorSection):
        count = len(section.competitors)
        noun = "competitor" if count == 1 else "competitors"
        return _one_line(f"{count} {noun} profiled. {section.differentiation.text}")
    if dimension == "customer_reachability" and isinstance(section, CustomerSection):
        count = len(section.personas)
        noun = "persona" if count == 1 else "personas"
        return _one_line(f"{count} {noun}. {section.early_adopter_profile}")
    if dimension == "feasibility" and isinstance(section, FeasibilitySection):
        count = len(section.risks)
        noun = "risk" if count == 1 else "risks"
        return _one_line(
            f"MVP {section.mvp_cost_range} in {section.mvp_timeline}; {count} {noun} mapped."
        )
    if dimension == "monetization_clarity" and isinstance(section, BusinessModelSection):
        count = len(section.revenue_streams)
        noun = "revenue stream" if count == 1 else "revenue streams"
        return _one_line(
            f"{count} {noun}; CAC {section.unit_economics.cac_estimate}, "
            f"LTV {section.unit_economics.ltv_estimate}."
        )
    return "Section not completed."


def _render_market(section: MarketSection, claims: Sequence[ReportClaim]) -> list[str]:
    lines = [
        "## Market",
        "",
        f"**TAM:** {_one_line(section.tam.value)} — {_one_line(section.tam.method)}"
        f"{_links(section.tam.sources)}",
        f"**SAM:** {_one_line(section.sam.value)} — {_one_line(section.sam.method)}"
        f"{_links(section.sam.sources)}",
        f"**SOM:** {_one_line(section.som.value)} — {_one_line(section.som.method)}"
        f"{_links(section.som.sources)}",
    ]
    if section.trends:
        lines.extend(["", "### Trends", ""])
        lines.extend(
            f"- {_one_line(trend.text)}{_links(trend.source_urls)}" for trend in section.trends
        )
    lines.extend(
        [
            "",
            "### Why now",
            "",
            f"{_one_line(section.timing_why_now.text)}{_links(section.timing_why_now.source_urls)}",
        ]
    )
    lines.extend(_claims_block(claims))
    return lines


def _render_competitors(section: CompetitorSection, claims: Sequence[ReportClaim]) -> list[str]:
    lines = ["## Competitors", ""]
    if section.competitors:
        lines.append("| Competitor | Positioning | Pricing | Gap |")
        lines.append("| --- | --- | --- | --- |")
        for competitor in section.competitors:
            name = f"[{_cell(competitor.name)}]({competitor.url})"
            lines.append(
                f"| {name} | {_cell(competitor.positioning)} | {_cell(competitor.pricing)} "
                f"| {_cell(competitor.gap)} |"
            )
    else:
        lines.append("_No competitors found._")
    lines.extend(
        [
            "",
            f"**Differentiation:** {_one_line(section.differentiation.text)}"
            f"{_links(section.differentiation.source_urls)}",
        ]
    )
    lines.extend(_claims_block(claims))
    return lines


def _render_customers(section: CustomerSection, claims: Sequence[ReportClaim]) -> list[str]:
    lines = ["## Customers", ""]
    if section.personas:
        lines.extend(["### Personas", ""])
        for persona in section.personas:
            lines.append(f"- **{_one_line(persona.name)}** — {_one_line(persona.description)}")
            lines.extend(f"  - Pain: {_one_line(pain)}" for pain in persona.pains)
            lines.extend(
                f"  - Gathers in: {_one_line(place)}" for place in persona.where_they_gather
            )
        lines.append("")
    if section.communities:
        lines.extend(["### Communities", ""])
        lines.extend(
            f"- **{_one_line(community.name)}** — {_one_line(community.why)}"
            f" ([source]({community.url}))"
            for community in section.communities
        )
        lines.append("")
    if section.pain_quotes:
        lines.extend(["### Pain quotes", ""])
        lines.extend(
            f'- "{_one_line(quote.quote)}" — {_one_line(quote.context)} ([source]({quote.url}))'
            for quote in section.pain_quotes
        )
        lines.append("")
    lines.append(f"**Early adopters:** {_one_line(section.early_adopter_profile)}")
    if section.leads:
        lines.extend(["", "### Company leads", ""])
        for lead in section.leads:
            details = ", ".join(
                part for part in (lead.industry, lead.size_band, lead.country) if part
            )
            suffix = f" ({details})" if details else ""
            lines.append(
                f"- **{_one_line(lead.name)}** ({lead.domain}){suffix} — "
                f"{_one_line(lead.why_fit)} ([source]({lead.url}))"
            )
    lines.extend(_claims_block(claims))
    return lines


def _render_feasibility(section: FeasibilitySection, claims: Sequence[ReportClaim]) -> list[str]:
    lines = [
        "## Feasibility",
        "",
        f"- **Technical:** {_one_line(section.technical)}",
        f"- **Operational:** {_one_line(section.operational)}",
        f"- **Legal / regulatory:** {_one_line(section.legal_regulatory)}",
        f"- **MVP cost:** {_one_line(section.mvp_cost_range)}",
        f"- **MVP timeline:** {_one_line(section.mvp_timeline)}",
    ]
    if section.risks:
        lines.extend(
            [
                "",
                "### Risks",
                "",
                "| Risk | Likelihood | Impact | Mitigation |",
                "| --- | --- | --- | --- |",
            ]
        )
        lines.extend(
            f"| {_cell(risk.description)} | {risk.likelihood}/5 | {risk.impact}/5 "
            f"| {_cell(risk.mitigation)} |"
            for risk in section.risks
        )
    lines.extend(_claims_block(claims))
    return lines


def _render_business_model(
    section: BusinessModelSection, claims: Sequence[ReportClaim]
) -> list[str]:
    lines = ["## Business model", ""]
    if section.lean_canvas:
        lines.extend(["### Lean canvas", "", "| Block | Value |", "| --- | --- |"])
        lines.extend(
            f"| {_cell(block)} | {_cell(value)} |" for block, value in section.lean_canvas.items()
        )
        lines.append("")
    if section.revenue_streams:
        lines.extend(["### Revenue streams", ""])
        lines.extend(f"- {_one_line(stream)}" for stream in section.revenue_streams)
        lines.append("")
    if section.pricing_options:
        lines.extend(["### Pricing", ""])
        lines.extend(
            f"- **{_one_line(option.name)}** — {_one_line(option.price_point)}: "
            f"{_one_line(option.notes)}"
            for option in section.pricing_options
        )
        lines.append("")
    economics = section.unit_economics
    lines.extend(
        [
            "### Unit economics",
            "",
            f"- **CAC:** {_one_line(economics.cac_estimate)}",
            f"- **LTV:** {_one_line(economics.ltv_estimate)}",
        ]
    )
    lines.extend(f"- Assumption: {_one_line(item)}" for item in economics.assumptions)
    if section.go_to_market:
        lines.extend(["", "### Go to market", ""])
        lines.extend(f"- {_one_line(channel)}" for channel in section.go_to_market)
    lines.extend(_claims_block(claims))
    return lines


def render_section_markdown(section: SectionModel, claims: Sequence[ReportClaim] = ()) -> str:
    """Render one section's model as deterministic markdown.

    The numbered claims are rendered in the trailing claims block; other
    sourced fields (TAM/SAM/SOM, trends, quotes, competitor URLs) render as
    plain links because they are not part of the numbered citation registry.
    """
    if isinstance(section, MarketSection):
        lines = _render_market(section, claims)
    elif isinstance(section, CompetitorSection):
        lines = _render_competitors(section, claims)
    elif isinstance(section, CustomerSection):
        lines = _render_customers(section, claims)
    elif isinstance(section, FeasibilitySection):
        lines = _render_feasibility(section, claims)
    else:
        lines = _render_business_model(section, claims)
    return "\n".join(lines)


def _partition_claims(
    result: AnalysisResult,
) -> tuple[list[Source], list[ReportClaim], dict[SectionName, list[ReportClaim]]]:
    grouped: dict[str, list[ClaimRef]] = {}
    for ref in result.claims:
        grouped.setdefault(ref.section, []).append(ref)
    ordered = list(grouped.get("brief", []))
    for name in SECTION_ORDER:
        ordered.extend(grouped.get(name, []))
    sources, numbered = number_sources(ordered)
    offset = len(grouped.get("brief", []))
    brief_claims = numbered[:offset]
    section_claims: dict[SectionName, list[ReportClaim]] = {}
    for name in SECTION_ORDER:
        count = len(grouped.get(name, []))
        section_claims[name] = numbered[offset : offset + count]
        offset += count
    return sources, brief_claims, section_claims


def _build_sections(
    result: AnalysisResult,
    section_claims: Mapping[SectionName, list[ReportClaim]],
) -> list[ReportSection]:
    models: dict[SectionName, SectionModel | None] = {
        "market": result.market,
        "competitors": result.competitors,
        "customers": result.customers,
        "feasibility": result.feasibility,
        "business_model": result.business_model,
    }
    sections: list[ReportSection] = []
    for name in SECTION_ORDER:
        model = models[name]
        claims = section_claims.get(name, [])
        if model is None:
            sections.append(
                ReportSection(
                    name=name,
                    title=SECTION_TITLES[name],
                    status="not_completed",
                    json_payload={},
                    markdown="",
                    claims=[],
                )
            )
            continue
        sections.append(
            ReportSection(
                name=name,
                title=SECTION_TITLES[name],
                status="complete",
                json_payload=model.model_dump(mode="json"),
                markdown=render_section_markdown(model, claims),
                claims=claims,
            )
        )
    return sections


def assemble_report(
    result: AnalysisResult,
    *,
    run_date: datetime | None = None,
    cost_usd: float | None = None,
    is_partial: bool = False,
    weights: Mapping[str, float] | None = None,
) -> Report:
    """Build a :class:`Report` from a finished result without touching the database."""
    effective_weights: Mapping[str, float] = (
        weights if weights is not None else get_settings().report_score_weights
    )
    sources, brief_claims, section_claims = _partition_claims(result)
    sections = _build_sections(result, section_claims)
    partial = is_partial or any(section.status == "not_completed" for section in sections)
    overall_score = compute_overall_score(result.scorecard, effective_weights)
    basis = score_basis(result.scorecard, effective_weights)
    effective_cost = float(result.cost_usd if cost_usd is None else cost_usd)
    effective_run_date = run_date or result.generated_at
    header = ReportHeader(
        title=result.brief.title,
        one_liner=result.brief.one_liner,
        verdict=result.verdict.decision,
        verdict_confidence=result.verdict.confidence,
        overall_score=overall_score,
        score_basis=basis,
        run_date=effective_run_date,
        cost_usd=effective_cost,
    )
    brief = ReportBrief(
        title=result.brief.title,
        one_liner=result.brief.one_liner,
        problem=result.brief.problem,
        solution=result.brief.solution,
        target_users=result.brief.target_users,
        value_prop=result.brief.value_prop,
        key_assumptions=list(result.brief.key_assumptions),
        variants=list(result.brief.variants),
        claims=brief_claims,
    )
    return Report(
        idea_id=result.idea_id,
        version_id=result.version_id,
        run_id=result.run_id,
        header=header,
        scorecard=_scorecard_entries(result),
        brief=brief,
        sections=sections,
        next_steps=[
            NextStep(assumption=step.assumption, test=step.test, cost_hint=step.cost_hint)
            for step in result.next_steps
        ],
        sources=sources,
        generated_at=result.generated_at,
        run_date=effective_run_date,
        cost_usd=effective_cost,
        is_partial=partial,
    )


def _scorecard_entries(result: AnalysisResult) -> list[ScorecardEntry]:
    entries: list[ScorecardEntry] = []
    for score in result.scorecard.dimensions:
        entries.append(
            ScorecardEntry(
                dimension=score.dimension,
                label=DIMENSION_LABELS.get(score.dimension, score.dimension),
                score=score.score,
                confidence=score.confidence,
                needs_review=score.needs_review,
                source=score.source,
                rationale=dimension_rationale(score.dimension, score, result),
            )
        )
    return entries


async def _latest_completed_run(session: AsyncSession, version_id: uuid.UUID) -> AnalysisRun | None:
    stmt = (
        select(AnalysisRun)
        .where(
            AnalysisRun.idea_version_id == version_id,
            AnalysisRun.status.in_([RunStatus.done, RunStatus.partial]),
        )
        .order_by(AnalysisRun.started_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _load_result(session: AsyncSession, run: AnalysisRun) -> AnalysisResult:
    stmt = select(RunStep).where(
        RunStep.run_id == run.id,
        RunStep.step == "critic",
        RunStep.status == StepStatus.done,
    )
    step = (await session.execute(stmt)).scalar_one_or_none()
    raw = (step.output or {}).get("result") if step is not None else None
    if not isinstance(raw, dict):
        raise ReportNotFound(f"run {run.id} has no completed result")
    try:
        return AnalysisResult.model_validate(raw)
    except ValidationError as exc:
        raise ReportNotFound(f"run {run.id} has an invalid result") from exc


async def build_report(
    session_factory: async_sessionmaker[AsyncSession],
    idea_id: uuid.UUID,
    version_number: int | None = None,
) -> Report:
    """Load the latest completed run for an idea version and assemble its report."""
    async with session_factory() as session:
        service = IdeaService(session, NoopEmbedder())
        try:
            detail = await service.get(idea_id)
        except IdeaNotFound as exc:
            raise ReportNotFound(f"idea {idea_id} not found") from exc
        if version_number is not None:
            version = next(
                (item for item in detail.versions if item.number == version_number), None
            )
            if version is None:
                raise InvalidReportVersion(f"idea {idea_id} has no version {version_number}")
        else:
            version = detail.versions[-1]
        run = await _latest_completed_run(session, version.id)
        if run is None:
            raise ReportNotFound(
                f"idea {idea_id} has no completed analysis for version {version.number}"
            )
        result = await _load_result(session, run)
    return assemble_report(
        result,
        run_date=run.finished_at or result.generated_at,
        cost_usd=float(run.cost_usd),
        is_partial=run.status is RunStatus.partial,
    )
