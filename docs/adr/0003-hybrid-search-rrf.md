# ADR 0003: Hybrid search via Reciprocal Rank Fusion (k=60)

Status: accepted (2026-10-14)

## Context

SPEC-idea-core.md requires keyword search, semantic search, and hybrid search
with p95 < 300 ms over 1,000 ideas, plus cursor pagination that is stable under
concurrent inserts.

## Decision

Hybrid search fuses the Postgres FTS rank (`websearch_to_tsquery` over a GIN
`tsvector`) with the pgvector cosine rank (HNSW index) using Reciprocal Rank
Fusion with `k=60`. Ranked result sets materialize candidate lists and paginate
with an opaque keyset cursor carrying the rank key and the idea id as tiebreak.
An embedding failure degrades semantic search to keyword search and never 500s.

## Consequences

- One query per modality plus an in-process fusion; measured p95 is ~24 ms over
  1,000 seeded ideas (integration benchmark asserts < 300 ms).
- Cursor pagination is deterministic: ties break by id and the cursor carries the
  last rank key, so inserts during pagination neither duplicate nor skip rows.
- Fusion is a pure function (`app/ideas/search.py`) covered by unit tests.

## Alternatives considered

- Single SQL `ORDER BY` mixing rank expressions: not monotonic across inserts,
  breaks cursor stability.
- Postgres `ts_rank_cd` + `<=>` in one score: weights become opaque and cannot
  be tuned per modality.
