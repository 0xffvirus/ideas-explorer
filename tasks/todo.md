# web-app — task checklist

Plan: `tasks/plan.md`. Module spec: `SPEC-web-app.md`. All work lives in
`frontend/` (plus these task files).

Status: **T1–T14 complete** (2026-10-14). Final gates: lint, typecheck, 51 unit
tests, 22 Playwright e2e tests (incl. axe on every screen), production build —
all green. Measured on the production build with the 1,000-idea mock dataset:
LCP 408 ms (library) / 420 ms (intake) / 528 ms (idea detail) / 376 ms (compare),
CLS ≤ 0.076 — budget LCP < 2.5 s.

## Phase 1: Foundation
- [x] T1. Scaffold frontend (Next 16, TS strict, Tailwind 4, ESLint+Prettier, Vitest, Playwright, MSW, TanStack Query, openapi-typescript) + smoke build
- [x] T2. Soft Mono tokens → Tailwind theme, base primitives, app shell + nav + skip link, DESIGN.md
- [x] T3. OpenAPI contract snapshot, gen:api, typed client, query hooks, SSE hook
- [x] T4. MSW handlers + SSE mock + 1,000-idea dataset + browser/node setup

## Checkpoint A
- [x] Lint, typecheck, build green; dev server renders shell

## Phase 2: Screens
- [x] T5. Intake `/` (draft persistence, ⌘Enter, context disclosure, optimistic create)
- [x] T6. Library `/ideas` (debounced search + match hint, filters, URL sync + history, list/board, cursor pagination, j/k keyboard, empty state)
- [x] T7. Idea page `/ideas/[id]` (SSE progress + cost meter, tabs, claims/citations, unverified pills, low-confidence badges, per-section re-run, version switcher, clarify form, similar ideas, MD/PDF export)
- [x] T8. Compare `/compare?ids=`
- [x] T9. Command palette ⌘K + global shortcuts (`/`, `n`)

## Checkpoint B
- [x] All screens walked through in a real browser (Playwright checks + screenshots); SPEC acceptance checklist verified

## Phase 3: Verification & Quality
- [x] T10. Unit/component tests (51; includes run-events resume/backoff and URL round-trips)
- [x] T11. Playwright e2e + axe + keyboard + 360 px (22 tests)
- [x] T12. Performance pass (LCP/CLS measured; idea-page skeleton stabilized CLS to 0)
- [x] T13. Subagent reviews (code/security/performance) — all actionable findings fixed:
  - fixed unbounded SSE reconnect after terminal runs + retry budget on empty closes
  - fixed a real rerun bug (event cursor lost on re-seed → replayed old `run_done`)
  - safe external URL handling (no crash on schemeless competitor URLs; http/https allowlist)
  - `#main` landmark on all routes; roving keyboard on search mode; SR confidence text
  - mock-build isolation (`distDir` + `ALLOW_MOCK_BUILD` guard) — verified disabled build
    excludes the mock chunk and SSRs the shell
  - tab/version switches no longer trigger RSC round trips; command palette lazy-loaded;
    zod/date-fns/clsx/tailwind-merge removed from the bundle; list memoization
- [x] T14. Docs (`README.md`, `DESIGN.md`, `docs/API-CONTRACT-NOTES.md`) + final full gate
