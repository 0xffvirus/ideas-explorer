"""Render a :class:`Report` as Markdown, self-contained HTML, or PDF bytes.

The Markdown export is the plain-text mirror of the report; the HTML export is
the print-friendly document WeasyPrint turns into the PDF. Both consume only
the DTOs, so a report renders identically regardless of how it was assembled.
Low-confidence scores get a dashed border and a trailing ``?``; unverified
claims get a pill in both formats.
"""

from __future__ import annotations

import asyncio
import importlib
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import get_settings
from app.reports.models import Report, ReportClaim, ReportHeader, ScorecardEntry, Source

TEMPLATES_DIR = Path(__file__).parent / "templates"

PDF_RENDER_CONCURRENCY = 2

_PDF_SEMAPHORE = asyncio.Semaphore(PDF_RENDER_CONCURRENCY)

_ENV = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _one_line(value: str) -> str:
    return " ".join(value.split())


def _cell(value: str) -> str:
    return _one_line(value).replace("|", "\\|")


def _status_marker(status: str) -> str:
    if status == "verified":
        return ""
    if status == "unavailable":
        return " _(unverified: source unavailable)_"
    return " _(unverified)_"


def _format_date(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")


def _verdict_text(header: ReportHeader) -> str:
    if header.verdict is None:
        return "not decided"
    if header.verdict_confidence is not None:
        return f"{header.verdict} (confidence {header.verdict_confidence * 100:.0f}%)"
    return header.verdict


def _score_text(header: ReportHeader) -> str:
    if header.overall_score is None:
        return "not scored (no Jev-scored dimensions)"
    scored = f"{header.overall_score:.1f} / 100"
    if header.score_basis == "partial":
        return f"{scored} (partial: some dimensions were not scored)"
    return scored


def _score_cell(entry: ScorecardEntry) -> str:
    if entry.score is None:
        return "not scored"
    suffix = " ?" if entry.needs_review else ""
    return f"{entry.score:.1f}/5{suffix}"


def _confidence_cell(entry: ScorecardEntry) -> str:
    if entry.confidence is None:
        return "—"
    return f"{entry.confidence * 100:.0f}%"


def _markdown_claims(claims: list[ReportClaim]) -> list[str]:
    if not claims:
        return []
    lines = ["", "**Claims**", ""]
    for claim in claims:
        citations = "".join(f" [{number}]" for number in claim.citation_numbers)
        lines.append(f"- {_one_line(claim.text)}{citations}{_status_marker(claim.status)}")
    return lines


def _source_line(source: Source) -> str:
    title = source.title.strip()
    if title and title != source.url:
        return f"{source.number}. {title} — {source.url}"
    return f"{source.number}. {source.url}"


def render_markdown(report: Report) -> str:
    """Render the full report as Markdown with numbered citations."""
    header = report.header
    lines: list[str] = [f"# {header.title}", ""]
    if header.one_liner:
        lines.extend([f"_{_one_line(header.one_liner)}_", ""])
    lines.append(f"- **Verdict:** {_verdict_text(header)}")
    lines.append(f"- **Overall score:** {_score_text(header)}")
    lines.append(f"- **Run date:** {_format_date(report.run_date)}")
    lines.append(f"- **Cost:** ${report.cost_usd:.2f}")
    if report.is_partial:
        lines.append("- **Partial run:** some sections were not completed.")
    lines.extend(
        [
            "",
            "## Scorecard",
            "",
            "| Dimension | Score | Confidence | Rationale |",
            "| --- | --- | --- | --- |",
        ]
    )
    for entry in report.scorecard:
        lines.append(
            f"| {_cell(entry.label)} | {_score_cell(entry)} | {_confidence_cell(entry)} "
            f"| {_cell(entry.rationale)} |"
        )
    brief = report.brief
    lines.extend(
        [
            "",
            "## Polished idea",
            "",
            f"**Problem:** {_one_line(brief.problem)}",
            "",
            f"**Solution:** {_one_line(brief.solution)}",
            "",
            f"**Target users:** {_one_line(brief.target_users)}",
            "",
            f"**Value proposition:** {_one_line(brief.value_prop)}",
        ]
    )
    if brief.key_assumptions:
        lines.extend(["", "**Key assumptions**", ""])
        lines.extend(f"- {_one_line(item)}" for item in brief.key_assumptions)
    if brief.variants:
        lines.extend(["", "**Variants**", ""])
        lines.extend(f"- {_one_line(item)}" for item in brief.variants)
    lines.extend(_markdown_claims(brief.claims))
    lines.append("")
    for section in report.sections:
        body = section.markdown.strip()
        if body:
            lines.extend([body, ""])
        else:
            lines.extend([f"## {section.title}", "", "_Not completed._", ""])
    lines.extend(["## Next steps", ""])
    if report.next_steps:
        for index, step in enumerate(report.next_steps, start=1):
            lines.append(
                f"{index}. **{_one_line(step.assumption)}** — {_one_line(step.test)} "
                f"(cost: {_one_line(step.cost_hint)})"
            )
    else:
        lines.append("_No next steps were produced._")
    lines.extend(["", "## Sources", ""])
    if report.sources:
        lines.extend(_source_line(source) for source in report.sources)
    else:
        lines.append("_No sources were cited._")
    lines.append("")
    return "\n".join(lines)


def render_html(report: Report) -> str:
    """Render the report with the self-contained, print-friendly HTML template."""
    template = _ENV.get_template("report.html.j2")
    settings = get_settings()
    return template.render(
        report=report,
        confidence_floor=settings.jev_confidence_floor,
        score_text=_score_text(report.header),
        verdict_text=_verdict_text(report.header),
        run_date_text=_format_date(report.run_date),
        cost_text=f"${report.cost_usd:.2f}",
    )


def _write_pdf(html: str) -> bytes:
    module = importlib.import_module("weasyprint")
    document = module.HTML(string=html)
    payload: bytes = document.write_pdf()
    return payload


async def render_pdf(report: Report) -> bytes:
    """Render the report to PDF bytes in a worker thread, bounded by a timeout.

    At most :data:`PDF_RENDER_CONCURRENCY` renders run at once; parallel
    requests queue for a slot instead of spawning unbounded CPU threads. A
    render that exceeds the configured timeout raises ``TimeoutError``, which
    the API maps to a 503.
    """
    html = render_html(report)
    timeout = get_settings().pdf_render_timeout_seconds
    async with _PDF_SEMAPHORE:
        return await asyncio.wait_for(asyncio.to_thread(_write_pdf, html), timeout=timeout)
