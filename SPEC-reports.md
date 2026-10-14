# Spec: reports

> Module of [SPEC.md](SPEC.md). Code lives in `backend/app/reports/`. Depends on `agent-pipeline` (AnalysisResult).

## Objective

Turn a run's `AnalysisResult` into one readable **report** and **scorecard**, compute
the overall score and verdict fields on the idea, and export to Markdown and PDF.

## Report Shape (`Report`)

1. **Header**: title, one-liner, verdict (pursue / refine / park) with Jev confidence, overall score 0-100, run date, cost.
2. **Scorecard**: 6 dimensions (score 1-5, confidence bar, "needs review" flag, and a one-line rationale
   drawn from the section).
3. **Polished idea**: the brief, key assumptions, variants.
4. **Market**, **Competitors**, **Customers**, **Feasibility**, **Business model**: each section shows claims
   with numbered citations. Unverified claims are visibly marked.
5. **Next steps**: the 3–5 riskiest assumptions, each with a cheap way to test it (this comes from the critic).
6. **Sources**: a deduplicated, numbered list.

**Overall score** = weighted mean of the dimension scores (competition is inverted), scaled to 0-100, with
weights in config. Dimensions flagged "not scored" are excluded and the header says so.

## Interface

| Method | Path | Notes |
|---|---|---|
| GET | `/ideas/{id}/report?version=` | latest completed run by default |
| GET | `/ideas/{id}/report.md` | Markdown export |
| GET | `/ideas/{id}/report.pdf` | PDF via WeasyPrint from the same HTML template (**Ask first**: new dependency) |
| GET | `/compare?ids=a,b,c` | 2-3 ideas: scorecards side by side and key fields aligned |

After a run completes, `reports` calls `IdeaService.set_analysis_fields(verdict, overall_score, category, title)`.

## Acceptance Criteria

- [ ] Every citation number resolves to an entry in Sources. No orphans and no duplicates.
- [ ] Partial runs render the available sections, with a "not completed" placeholder for the rest.
- [ ] The overall score matches a hand-computed fixture. An excluded dimension changes the denominator, not the scale.
- [ ] The Markdown export round-trips (snapshot test). The PDF renders a non-empty file under 5 s.
- [ ] Compare rejects fewer than 2 or more than 3 ids → 422.
