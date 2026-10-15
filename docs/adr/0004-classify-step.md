# ADR 0004: A separate classify step, and Jev judges while LLMs write

Status: accepted (2026-10-14)

## Context

SPEC.md's rule is "LLMs write and Jev judges". The pipeline flow in
SPEC-agent-pipeline.md starts with a Jev classification, and the idea row's
`category` column is documented as a "Jev Choice result". An early iteration
folded classification away; the review caught that `AnalysisResult` carried no
category, so reports could not set the field.

## Decision

`classify` is a first-class pipeline step (executed with `Gate.classify` before
the refiner, persisted as a `run_steps` row, included in `AnalysisResult` as
`classification`). It is deliberately not exposed in the per-section rerun API,
whose sections are the report sections a user can see.

## Consequences

- `idea.category` is populated from Jev's typed choice with its confidence, not
  from an LLM guess.
- Classification is observable in the event stream and resumable like any step.
- Step ordering tests and progress UIs include `classify` as the first row.
