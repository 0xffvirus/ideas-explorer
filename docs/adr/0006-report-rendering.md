# ADR 0006: Reports render from one JSON model to Markdown, HTML, and PDF

Status: accepted (2026-10-14)

## Context

SPEC-reports.md requires a single report shape rendered as JSON (API), Markdown
(export), and PDF (WeasyPrint) with numbered citations, "unverified" labeling,
partial-run placeholders, and a weighted 0-100 overall score.

## Decision

`assembler.build_report` produces a typed `Report` DTO from the persisted
`AnalysisResult`. `render.py` turns that DTO into Markdown and into a
self-contained Jinja2 HTML template (autoescaped, no external resources), and
WeasyPrint renders the same HTML to PDF. The PDF path is bounded by a timeout
and a `Semaphore(2)` so parallel exports cannot spawn unbounded render threads.
The overall score is a weighted mean of dimension scores (competition inverted),
scaled to 0-100; dimensions marked unavailable are excluded from the
denominator, and the header states the basis (`all_dimensions` | `partial` |
`not_scored`).

## Consequences

- One source of truth: JSON, Markdown, and PDF cannot drift in content.
- Citation numbering is computed once over claims in canonical order, so every
  number resolves and there are no orphans or duplicates in any format.
- PDF export depends on system libs (pango/cairo); the endpoint returns 503 with
  a clear message when rendering is unavailable, and Markdown export still works.
