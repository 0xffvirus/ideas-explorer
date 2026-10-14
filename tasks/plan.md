# Implementation Plan: web-app (Idea Forge frontend)

> **Status: complete (2026-10-14).** All tasks landed in `frontend/`; the plan
> below is kept as the record. Final results: 51 unit tests, 22 Playwright e2e
> tests (incl. axe on every screen), lint/typecheck/build green, LCP 376–528 ms
> and CLS ≤ 0.076 on the production build with 1,000 mocked ideas. See
> `tasks/todo.md` for the per-task outcomes and the review fixes applied.

## Overview

Build the `web-app` module of Idea Forge: a Next.js (App Router) frontend for one-box idea
intake, live analysis progress, a searchable idea library with filters/compare, and a
report reader — per `SPEC-web-app.md`, inheriting the stack, style, and boundaries of `SPEC.md`.
The backend modules (`idea-core`, `agent-pipeline`, `reports`) are being built in sibling
worktrees; this worktree owns `frontend/` only.

## Architecture Decisions

- **Stack (from SPEC.md):** Next.js 16 App Router, TypeScript strict, Tailwind v4,
  shadcn-style Radix primitives, TanStack Query v5, MSW v3 (dev/test/e2e mocks), Vitest,
  Playwright + axe. openapi-typescript generates the API types from a committed OpenAPI 3.1
  contract snapshot (`frontend/openapi/openapi.json`); `pnpm gen:api` regenerates it from a
  live backend (`OPENAPI_URL`) once one is running.
- **Design system:** Soft Mono tokens (`tokens.css`, the project's design system) imported
  once and mapped through Tailwind v4 `@theme inline`; no literal hex/px in components.
  System font stack (no webfont) to protect LCP. Logical CSS properties for future RTL.
- **State:** TanStack Query for server state; URL `searchParams` for library filters/sort/view
  (debounced, back/forward-safe); localStorage for the intake draft; no global store.
- **Live progress:** fetch-based SSE reader (`/runs/{id}/events`) with `Last-Event-ID`
  reconnect + reducer; progress rendered from a pure reducer so it is unit-testable.
- **Contract snapshot:** REST paths/shapes authored from SPEC-idea-core.md, SPEC-reports.md,
  SPEC-agent-pipeline.md (snake_case JSON). One assumed endpoint is flagged in
  `frontend/docs/API-CONTRACT-NOTES.md`: clarifying answers (`POST /runs/{id}/respond`),
  which no module spec defines yet.
- **Accessibility:** WCAG 2.2 AA — skip link, visible focus, 44px targets, labeled controls,
  keyboard shortcuts (`/`, `n`, `j`/`k`, `Enter`, ⌘K), axe check per screen in e2e.
- **Performance:** Library paginated 30/page with cursor; skeleton rows; list view is
  default; LCP budget < 2.5 s measured with the 1,000-idea mock dataset.

## Assumptions (surfaced, not silently applied)

1. The frontend is the only deliverable in this worktree; backend stays in sibling worktrees.
2. Dev/e2e run against MSW mocks (`NEXT_PUBLIC_API_MOCKING=enabled`); real integration uses
   `NEXT_PUBLIC_API_URL` with mocking off.
3. UI language is English only (SPEC open question #3 unresolved); RTL is kept possible.
4. The clarifying-answers endpoint shape is assumed and documented; flagged for backend
   sign-off before integration.
5. Dependency list is limited to the stack named in SPEC.md plus its ecosystem
   (Radix/cmdk/lucide/zod/date-fns) — no extras.

## Task List

### Phase 1: Foundation
- [ ] T1. Scaffold `frontend/` (Next 16, TS strict, Tailwind 4, ESLint+Prettier, Vitest, Playwright, MSW, TanStack Query, openapi-typescript) + smoke build.
- [ ] T2. Soft Mono tokens → Tailwind theme, global styles, `DESIGN.md`, base primitives (Button, Badge, Card, Field, Skeleton, Segmented, Tooltip, Dialog), app shell + nav + skip link.
- [ ] T3. OpenAPI contract snapshot + `pnpm gen:api` + typed client (`lib/api`) + query keys + TanStack Query provider + SSE hook.
- [ ] T4. MSW: full API handlers, SSE stream mock, deterministic 1,000-idea dataset, browser/node setup.

### Checkpoint A
- [ ] Lint, typecheck, build pass; `pnpm dev` renders shell; gen:api reproducible.

### Phase 2: Screens (vertical slices)
- [ ] T5. Intake `/` — textarea, ⌘Enter, context disclosure, draft persistence, optimistic create → navigate, recent ideas.
- [ ] T6. Library `/ideas` — debounced search + match hint, filter chips, sort, URL sync, list/board views, cursor pagination, keyboard nav (j/k/Enter), empty state.
- [ ] T7. Idea page `/ideas/[id]` — header (verdict/score/confidence), SSE progress timeline + cost meter, tabs (Overview/Market/Competitors/Customers/Feasibility/Business model/Sources), claims + citations + unverified pills, low-confidence badge, per-section re-run, version switcher, similar ideas, export MD/PDF.
- [ ] T8. Compare `/compare?ids=` — 2–3 side-by-side scorecards + aligned fields, 422 handling; multi-select in Library.
- [ ] T9. Command palette ⌘K + global shortcuts — search by title/meaning, actions, recent searches.

### Checkpoint B
- [ ] Manual browser walkthrough of all screens; acceptance-criteria checklist from SPEC-web-app.md verified.

### Phase 3: Verification & Quality
- [ ] T10. Unit/component tests (ScoreBadge, filters/URL sync, progress reducer, intake draft, palette, compare selection).
- [ ] T11. Playwright e2e (intake → progress → report → search → compare) + axe on each screen + keyboard + 360px viewport.
- [ ] T12. Performance pass — LCP/CLS on Library with 1,000 ideas (Lighthouse/devtools), fix regressions.
- [ ] T13. Subagent reviews: code-reviewer (five-axis) + web-performance-auditor + security-auditor (light); fix findings.
- [ ] T14. Docs (`frontend/README.md`, `DESIGN.md`, contract notes) + final `pnpm lint && typecheck && test && e2e && build`.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Backend contract drift | Med | Contract snapshot + generated types; `gen:api` against live OpenAPI; notes file flags assumptions |
| Next 16 / Tailwind 4 / Vitest 5 freshness | Med | Scaffold + smoke-test first; pin versions; verify each tool early |
| Playwright browser availability | Low | `pnpm exec playwright install chromium`; fallback to system Chrome channel |
| SSE mocking with MSW | Med | Prove streaming mock early (T4); fallback page.route in e2e |
| LCP with 1,000 ideas | Med | Pagination 30/page, skeletons, no heavy client bundle on list route; measure in T12 |

## Open Questions (deferred to backend owners)

- Clarifying-answers endpoint (`POST /runs/{id}/respond`) shape — assumed, documented.
- Report payload version field and excluded-dimension naming — aligned to SPEC-reports.md.
- Deployment/access remains out of scope (root SPEC open question #2).
