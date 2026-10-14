# Spec: Idea Forge

> Root spec. It holds the capability map (the index of module specs) and the
> conventions every module shares. Each module's own spec is `SPEC-<module-id>.md`.

## Objective

A user types a rough business idea in one sentence or a paragraph. A backend
multi-agent system then:

1. **Polishes** it into a sharp brief (problem, solution, target user, key assumptions).
2. **Validates** it against real evidence: market size and trends, competitors,
   and community pain-point signals.
3. **Finds potential customers**: personas, the places they gather online, real posts
   that express the pain, and (optionally) a list of target companies.
4. **Runs a feasibility study**: technical, operational, legal/regulatory, and cost to MVP.
5. **Designs a business model**: Lean Canvas, pricing, revenue streams, and rough unit economics.
6. **Scores** the idea with **Jev** (TypeSafe AI). Jev gives a typed, calibrated-confidence
   verdict per dimension, and low-confidence results are flagged or re-researched
   instead of being presented as fact.

The user can browse and search all their ideas, compare them, re-run sections,
and export reports.

**User.** Single user (the owner). This is a personal and portfolio MVP. It has no
sign-up and no billing.

**Why Jev and LLMs.** LLMs (OpenAI first, behind a provider-agnostic interface)
do the open-ended work: research, synthesis, and writing. Jev handles the
*decisions*, meaning classification, dimension scores, evidence checks, and routing,
because it returns typed values with calibrated confidence that code can branch
on. The rule is that **LLMs write and Jev judges.**

### Top-level success criteria

- Submitting an idea takes **one text box and one click**. Every other field is optional.
- A full analysis completes in **≤ 5 min p50 and ≤ 10 min p95**, costs **≤ $0.75 by default**
  (the cap is configurable), and streams progress per agent while it runs.
- Every factual claim in a report (market numbers, competitor facts, customer quotes)
  links to **at least one source URL**. Jev's evidence check rejects claims that
  have no supporting source, and the report labels them "unverified".
- Every score on the scorecard shows its Jev confidence. Scores below the
  confidence threshold are visibly flagged.
- The library finds an idea by keyword *or* meaning ("ideas about pets") in
  **< 300 ms** for 1,000 ideas, with filters for status, verdict, category, and tags.

## Capability Map (approved 2026-10-11)

| Module id | Responsibility | Depends on | Spec |
|---|---|---|---|
| `idea-core` | Idea and version model, CRUD, tags, Postgres schema, search (FTS + pgvector), REST API | — | [SPEC-idea-core.md](SPEC-idea-core.md) |
| `research-tools` | Adapters for web search, Reddit and HN signals, and lead DB, with caching and rate limits | — | [SPEC-research-tools.md](SPEC-research-tools.md) |
| `jev-gate` | Typed Jev client: question catalog, scoring, evidence gates, confidence routing | — | [SPEC-jev-gate.md](SPEC-jev-gate.md) |
| `agent-pipeline` | Orchestrator and agents (refine, market, competitors, customers, feasibility, business model, critic), job runner, progress events, cost cap | idea-core, research-tools, jev-gate | [SPEC-agent-pipeline.md](SPEC-agent-pipeline.md) |
| `reports` | Assembles agent outputs into a report and scorecard, and exports Markdown and PDF | agent-pipeline | [SPEC-reports.md](SPEC-reports.md) |
| `web-app` | One-box intake, live progress, library with search and filters, idea page, compare | idea-core, reports | [SPEC-web-app.md](SPEC-web-app.md) |

**Build order:** `idea-core`, `research-tools`, `jev-gate` (in parallel) → `agent-pipeline` → `reports` → `web-app`.
A thin `web-app` intake and list slice may start right after `idea-core`.

Contracts live in the provider module's spec. For example, `agent-pipeline` consumes the
`ResearchTool` protocol defined in `SPEC-research-tools.md`.

## Tech Stack

| Layer | Choice |
|---|---|
| Backend language | Python 3.12, managed with **uv** |
| API | FastAPI with Pydantic v2 |
| Agents | **Pydantic AI** (typed outputs, provider-agnostic). OpenAI is the default provider |
| Decision model | **Jev** via `typesafe-sdk` (`POST https://api.typesafe.ai/v1/systemone`, model `jev-latest`) |
| DB | PostgreSQL 16 with **pgvector**, SQLAlchemy 2 (async) and Alembic |
| Jobs | Postgres-backed job table with a worker process (`SELECT … FOR UPDATE SKIP LOCKED`). No Redis |
| Live progress | Server-Sent Events (SSE) |
| Frontend | Next.js (App Router), TypeScript strict, Tailwind, shadcn/ui, TanStack Query |
| API types | OpenAPI → `openapi-typescript` generated client |
| Embeddings | OpenAI `text-embedding-3-small` (1536-d) behind an `Embedder` interface |
| Local infra | Docker Compose (postgres+pgvector) |

Exact library versions are pinned in `pyproject.toml` / `package.json` at scaffold time.

## Commands

```bash
# one-time
cp .env.example .env                 # fill OPENAI_API_KEY, TYPESAFE_API_KEY, TAVILY_API_KEY, ...
docker compose up -d db
cd backend && uv sync && uv run alembic upgrade head
cd frontend && pnpm install

# dev
cd backend && uv run fastapi dev app/main.py          # API on :8000
cd backend && uv run python -m app.worker             # job worker
cd frontend && pnpm dev                               # web on :3000

# quality
cd backend && uv run ruff check --fix . && uv run ruff format . && uv run pyright
cd backend && uv run pytest -q                        # unit + integration (no network)
cd backend && uv run pytest -q -m eval                # live evals, real APIs, costs money
cd frontend && pnpm lint && pnpm typecheck && pnpm test
cd frontend && pnpm e2e                               # Playwright against mocked API
cd frontend && pnpm gen:api                           # regenerate TS client from /openapi.json

# all checks
make check
```

## Project Structure

```
idea-forge/
├── SPEC.md, SPEC-*.md        → specs (this file is the index)
├── docker-compose.yml        → postgres+pgvector
├── .env.example              → every env var, documented, no real values
├── Makefile                  → check, dev, eval shortcuts
├── backend/
│   ├── app/
│   │   ├── main.py           → FastAPI app factory
│   │   ├── worker.py         → job worker entrypoint
│   │   ├── config.py         → pydantic-settings
│   │   ├── ideas/            → idea-core
│   │   ├── research/         → research-tools
│   │   ├── jev/              → jev-gate
│   │   ├── pipeline/         → agent-pipeline (agents/, orchestrator.py, jobs.py)
│   │   └── reports/          → reports
│   ├── migrations/           → Alembic
│   └── tests/
│       ├── unit/  integration/  eval/
│       └── fixtures/         → recorded HTTP responses, golden ideas
├── frontend/
│   ├── app/                  → routes: /, /ideas, /ideas/[id], /compare
│   ├── components/
│   ├── lib/api/              → generated client + hooks
│   └── e2e/
└── docs/adr/                 → architecture decisions
```

Each backend module exposes a small public surface in its `__init__.py`. Other
modules import only from there and never from its internals.

## Code Style

**Python.** Ruff (lint and format, line length 100), pyright strict on `app/`, async everywhere
for I/O, Pydantic models at every boundary, no bare `dict` crossing module lines.

```python
# app/jev/scoring.py
from app.jev.client import JevClient
from app.jev.models import DimensionScore, Dimension

CONFIDENCE_FLOOR = 0.6


async def score_dimension(client: JevClient, brief: str, dim: Dimension) -> DimensionScore:
    """Ask Jev for one dimension's 1-5 score. Never raises on low confidence; flags it."""
    answer = await client.score(state=brief, instructions=dim.instructions, criteria=dim.criteria)
    return DimensionScore(
        dimension=dim.id,
        score=answer.score,
        confidence=answer.confidence,
        needs_review=answer.confidence < CONFIDENCE_FLOOR,
    )
```

**TypeScript.** strict, no `any`, ESLint and Prettier, server components by default,
data through TanStack Query hooks in `lib/api`, components in PascalCase files.

```tsx
export function ScoreBadge({ score, confidence }: { score: number; confidence: number }) {
  const uncertain = confidence < 0.6;
  return (
    <span className={cn("rounded-full px-2 py-0.5 text-sm", uncertain && "border border-dashed")}
          title={`Confidence ${(confidence * 100).toFixed(0)}%`}>
      {score}/5{uncertain && " ?"}
    </span>
  );
}
```

**Naming.** snake_case in Python and the DB, camelCase in TS. API JSON uses snake_case
(the generated client keeps it). Module ids match folder names.

## Testing Strategy

| Level | Tool | Scope | Network |
|---|---|---|---|
| Unit | pytest, Vitest | pure logic, prompts' output parsing, Jev response mapping | none |
| Agent | Pydantic AI `TestModel` / `FunctionModel` | agent wiring, tool calls, output schemas | none |
| Integration | pytest + real Postgres (compose) + `respx` fixtures | API ↔ DB, search, job runner, pipeline end-to-end with fakes | none |
| E2E | Playwright | intake → progress → report → search, against a mocked API | none |
| Eval | pytest `-m eval` | ~10 golden ideas through the real pipeline. Checks schema validity, source coverage, cost, and latency | **real, costs money**, run manually |

- The default `pytest` and CI runs must never hit a paid API.
- Coverage is **≥ 80% lines** on `backend/app` (not counting `eval/`).
- Bug fixes start with a failing test.

## Boundaries

**Always**
- Validate all input with Pydantic or Zod at the boundary.
- Keep API keys in `.env` only, and keep `.env.example` up to date.
- Attach source URLs to factual claims and show Jev confidence next to scores.
- Enforce the per-run cost cap and per-tool rate limits.
- Run `make check` before committing, and write conventional commit messages.
- Regenerate the TS client after any API change.

**Ask first**
- Adding a dependency or a new external data provider.
- DB schema changes beyond what a module spec defines.
- Changing the default LLM model, the cost cap, or the Jev confidence threshold.
- Enabling the lead-DB adapter (it costs money and involves personal data).
- Any deployment or public exposure of the app.

**Never**
- Commit secrets or real `.env` values.
- Call paid APIs in the default test suite or CI.
- Scrape sites against their ToS or bypass rate limits. Use official APIs only.
- Store personal contact data (emails, phones) of individuals found during research.
- Present an unsourced LLM claim as fact, or hide a low-confidence score.
- Delete or skip failing tests to get to green.

## Open Questions

1. **Lead-DB provider.** Apollo, Clearbit or another? Company-level only (recommended) or also roles?
   It is disabled by default until answered.
2. **Deployment.** Should it stay local only, or be deployed as a portfolio demo (for example
   Vercel + a hosted Postgres)? A public demo needs an access password and a stricter cost cap.
3. **Language.** Should reports be English only, or follow the input language (e.g. Arabic with RTL UI)?
4. **Jev pricing and limits** aren't in the public docs. Confirm the account quota before we fix
   the fan-out size per run.
