# Spec: agent-pipeline

> Module of [SPEC.md](SPEC.md). Code lives in `backend/app/pipeline/`.
> Depends on `idea-core` (IdeaService), `research-tools` (ResearchTool, Evidence), and `jev-gate` (Gate).

## Objective

Turn one idea version into a set of typed, sourced analysis sections by orchestrating
specialized LLM agents (Pydantic AI). Jev gates are applied between steps. Runs are durable,
observable, resumable, and cost-capped.

## Flow

```
              ┌─ classify (Jev) ─┐
raw input ──► Refiner ──► brief_is_specific? ──low──► Clarifier (≤3 questions, user may skip)
                 │
                 ▼  IdeaBrief
     ┌───────────┼──────────────┐            (parallel)
 MarketAgent  CompetitorAgent  CustomerAgent
     └───────────┼──────────────┘
                 ▼
   FeasibilityAgent ─► BusinessModelAgent    (sequential; read prior sections)
                 ▼
   Critic: Jev verify_claims + scorecard ─► ≤1 re-research of flagged dims ─► verdict
                 ▼
           AnalysisResult → reports
```

| Agent | Output schema (Pydantic) | Tools |
|---|---|---|
| Refiner | `IdeaBrief`: title, one_liner, problem, solution, target_users, value_prop, key_assumptions[], variants[≤3] | none |
| Clarifier | `list[ClarifyingQuestion]` (≤ 3) | none |
| MarketAgent | `MarketSection`: TAM/SAM/SOM each with `value, method, sources[]`, trends[], timing_why_now | web |
| CompetitorAgent | `CompetitorSection`: competitors[] (name, url, positioning, pricing, gap), differentiation | web |
| CustomerAgent | `CustomerSection`: personas[], communities[] (where they gather), pain_quotes[] (text + url), early_adopter_profile, leads[]? | reddit, hn, web, leads (if enabled) |
| FeasibilityAgent | `FeasibilitySection`: technical, operational, legal_regulatory, mvp_cost_range, mvp_timeline, risks[] (with likelihood, impact, mitigation) | web |
| BusinessModelAgent | `BusinessModelSection`: lean_canvas, revenue_streams[], pricing_options[], unit_economics (CAC/LTV estimates, with assumptions stated), go_to_market[] | web |

Every factual field holds `claims: list[Claim(text, source_urls[])]`. That is what Jev verifies.
Research results go through `Gate.filter_evidence` before an agent sees them.

## Runs and Jobs

```
analysis_runs(id, idea_version_id, status, step, cost_usd, cost_cap_usd, error, started_at, finished_at)
run_steps(run_id, step, status, output jsonb, cost_usd, model, attempts, started_at, finished_at)
jobs(id, kind, payload, status, run_after, locked_by, locked_at, attempts)
```

- The worker claims jobs with `FOR UPDATE SKIP LOCKED`. A step's output is persisted before the next step starts,
  so after a crash the run **resumes from the last completed step**.
- **Re-run a single section**: `POST /runs/{id}/steps/{step}/rerun` re-executes that step and its dependents.
- **Progress events** (`step_started`, `step_completed`, `step_failed`, `cost_update`, `run_done`) are written to
  `run_events` and streamed via `GET /runs/{id}/events` (SSE, resumable with `Last-Event-ID`).
- **Cost cap**: `CostMeter` sums LLM, Jev, and tool costs. If the next step's estimate would exceed the cap → stop
  gracefully with `status=partial` and emit a clear event. Default cap is $0.75 (`RUN_COST_CAP_USD`).
- **Models**: these are configured per agent in `config.py` (`provider:model`). OpenAI is the default. Use a small model for
  Refiner and Clarifier and a stronger one for synthesis agents. Swapping to another provider is a config change only.
- Step timeout is 120 s, with 2 retries on transient errors. An output schema validation failure → 1 retry with the
  validation error fed back, then the step fails.

## Acceptance Criteria

- [ ] Creating an idea enqueues a run, and a worker completes it end-to-end with fake LLM, Jev, and tools (integration).
- [ ] The three research agents run concurrently (asserted by overlapping timestamps in the test).
- [ ] Killing the worker mid-run and restarting resumes without redoing completed steps.
- [ ] A claim whose sources don't support it ends up `verified=false` in the output.
- [ ] A flagged dimension triggers at most one re-research, and the final score keeps its confidence.
- [ ] Hitting the cost cap → `partial` run with completed sections intact. It never overspends by more than one step's estimate.
- [ ] If the brief is not specific, the run pauses in `awaiting_input` with questions. Answering or skipping resumes it.
- [ ] One tool or agent failing marks only that section failed, and the run still reaches the critic with whatever exists.
- [ ] Live eval: 10 golden ideas, all with schema-valid output, ≥ 90% of claims with ≥ 1 URL, p50 ≤ 5 min, mean cost ≤ $0.75.

## Testing

Pydantic AI `TestModel` and `FunctionModel` for agents, `FakeJevClient`, fake tools that return fixture
`Evidence`, and a real Postgres for the job and run tables. Prompts live in `agents/prompts/*.md` and are snapshot-tested
so changes show up in review.

## Boundaries (module-specific)

- Agents never write to the DB directly. Only the orchestrator persists step outputs.
- No agent may output a score. Scores come only from Jev (see SPEC-jev-gate).
