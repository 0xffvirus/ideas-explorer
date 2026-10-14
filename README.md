# ideas-explorer

Validate business ideas with AI agents and real-world evidence.

A rough idea goes in as a single sentence. The system polishes it into a brief,
researches the market, competitors, and customer pain points against real
sources, runs a feasibility and business-model analysis, and returns a report
and scorecard where every factual claim is backed by a source URL and every
score carries calibrated confidence.

## What's in this repository today

- `backend/app/research/` — the research tools module: cached, rate-limited
  adapters for web search (Tavily), Reddit, and Hacker News. Every result is
  an `Evidence` record that always carries its source URL. See
  [docs/research-tools.md](docs/research-tools.md) for the full feature guide.
- `SPEC.md` and `SPEC-*.md` — the architecture, capability map, and module
  specifications. Remaining modules (idea-core, jev-gate, agent-pipeline,
  reports, web-app) are being built in parallel.

## Development

```bash
cp .env.example .env                 # fill in API keys as needed
docker compose up -d db              # Postgres + pgvector
cd backend
uv sync
uv run alembic upgrade head
uv run pytest -q                     # unit + integration, no network
uv run ruff check . && uv run pyright
```

Live provider checks (cost money / hit external services) are opt-in:

```bash
cd backend && uv run pytest -q -m eval
```
