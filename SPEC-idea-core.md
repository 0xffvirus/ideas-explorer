# Spec: idea-core

> Module of [SPEC.md](SPEC.md). It inherits the stack, commands, style, and boundaries from there.
> Code lives in `backend/app/ideas/`. Depends on nothing.

## Objective

Own the **idea** as data: store it, version it, tag it, and make it findable
by keyword and by meaning. Every other module reads and writes ideas only through this
module's service and API.

## Data Model

```
ideas
  id            uuid pk
  title         text            -- user-given or auto-generated (≤ 80 chars)
  status        enum            -- draft | queued | analyzing | done | failed
  verdict       enum null       -- pursue | refine | park (written by pipeline)
  category      text null       -- Jev Choice result, e.g. "b2b_saas"
  overall_score numeric null    -- 0-100, from reports
  pinned        bool default false
  archived_at   timestamptz null
  created_at, updated_at

idea_versions                    -- every resubmission or refinement is a new version
  id            uuid pk
  idea_id       fk ideas
  number        int             -- 1, 2, 3… unique per idea
  raw_input     text            -- exactly what the user typed (1-5,000 chars)
  context       jsonb           -- optional: target_region, audience_hint, budget_hint
  brief         jsonb null      -- polished brief from pipeline (IdeaBrief schema)
  created_at

tags(id, name unique)  idea_tags(idea_id, tag_id)

idea_search                      -- one row per idea, latest version
  idea_id       pk fk
  tsv           tsvector        -- title + raw_input + brief text, GIN index
  embedding     vector(1536)    -- HNSW index, cosine
```

## Public Interface

Python (`app.ideas`): `IdeaService` with `create`, `get`, `list`, `update`, `add_version`,
`set_analysis_fields`, `search`, `archive`, and `Embedder` (protocol, OpenAI implementation).

REST:

| Method | Path | Notes |
|---|---|---|
| POST | `/ideas` | `{raw_input, title?, context?, tags?, analyze?=true}` → 201 Idea. Enqueues analysis if `analyze` |
| GET | `/ideas` | `?q=&mode=hybrid\|keyword\|semantic&status=&verdict=&category=&tag=&sort=recent\|score\|title&cursor=&limit=` |
| GET | `/ideas/{id}` | idea, latest version, and the version list |
| PATCH | `/ideas/{id}` | title, tags, pinned, archived |
| POST | `/ideas/{id}/versions` | new raw input → new version (+ optional re-analysis) |
| GET | `/ideas/{id}/similar` | top 5 by embedding distance |
| GET | `/tags` | tag names with counts |

**Hybrid search** = Reciprocal Rank Fusion of FTS rank and vector cosine rank (k=60).
Empty `q` means a plain filtered list.

## Acceptance Criteria

- [ ] `POST /ideas` with only `raw_input` succeeds. An empty or over-5,000-char input → 422.
- [ ] When the title is omitted, a placeholder is the first 60 chars of the input, replaced later by the pipeline's title.
- [ ] Adding a version keeps old versions readable. `number` is gapless per idea.
- [ ] Keyword search finds exact terms. Semantic search finds "dog walking app" for the query "pets".
- [ ] Hybrid search p95 < 300 ms across 1,000 seeded ideas (integration benchmark).
- [ ] Embedding failure doesn't fail the create. The idea is saved and the embedding retried by the worker.
- [ ] Cursor pagination is stable under concurrent inserts.
- [ ] Archived ideas are hidden from the list by default (`?archived=true` shows them).

## Testing

- Unit: RRF fusion and filter-to-SQL building.
- Integration (real Postgres): CRUD, versions, FTS, vector, hybrid, and a pagination stability test with a fake embedder
  (deterministic vectors).

## Boundaries (module-specific)

- Only this module writes the `ideas*` and `idea_search` tables.
- Schema changes go through Alembic migrations, never `create_all`.
