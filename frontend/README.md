# web-app — Idea Forge frontend

Next.js 16 (App Router) frontend for Idea Forge: one-box intake, live analysis
progress over SSE, a searchable idea library, report reading with citations, and
side-by-side comparison.

Specs: [`SPEC-web-app.md`](../SPEC-web-app.md) (module) and [`SPEC.md`](../SPEC.md) (stack,
style, boundaries). Design decisions: [`DESIGN.md`](DESIGN.md). API contract notes:
[`docs/API-CONTRACT-NOTES.md`](docs/API-CONTRACT-NOTES.md).

## Requirements

- Node.js ≥ 20.9 (developed on 26.x) and pnpm 9+
- A running Idea Forge API for real data, **or** the built-in MSW mocks (default in dev)

## Quick start

```bash
pnpm install
pnpm dev          # http://localhost:3000 — runs against MSW mocks by default
```

To talk to a real backend instead, create `.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_MOCKING=disabled
```

## Commands

```bash
pnpm dev            # dev server (mocks on via .env.development)
pnpm build          # production build (refuses a mock-enabled build unless ALLOW_MOCK_BUILD=1)
pnpm start          # serve the production build
pnpm lint           # ESLint
pnpm typecheck      # next typegen && tsc --noEmit
pnpm test           # Vitest + Testing Library (no network)
pnpm test:coverage  # coverage report
pnpm e2e            # Playwright + axe against a mocked build (.next-e2e)
pnpm gen:api        # regenerate lib/api/schema.d.ts from OPENAPI_URL (default openapi/openapi.json)
pnpm format         # Prettier
pnpm check          # lint + typecheck + test
```

`pnpm e2e` builds into `.next-e2e` with `NEXT_PUBLIC_API_MOCKING=enabled` so the
normal `.next` output can never be a mock build. Stop any server on port 3100
before running it (`reuseExistingServer` is on locally).

## Environment variables

| Variable                    | Default                                      | Purpose                                                         |
| --------------------------- | -------------------------------------------- | --------------------------------------------------------------- |
| `NEXT_PUBLIC_API_URL`       | `http://localhost:8000`                      | API base URL                                                    |
| `NEXT_PUBLIC_API_MOCKING`   | `disabled` (`enabled` in `.env.development`) | Serve all API calls from the in-browser MSW layer               |
| `NEXT_PUBLIC_MOCK_STEP_MS`  | `450`                                        | Mock pipeline step cadence                                      |
| `NEXT_PUBLIC_MOCK_RERUN_MS` | `2× step`                                    | Mock section re-run duration                                    |
| `OPENAPI_URL`               | `openapi/openapi.json`                       | Source for `pnpm gen:api` (point at a live backend to diff)     |
| `ALLOW_MOCK_BUILD`          | —                                            | Must be `1` to production-build with mocking enabled (e2e only) |
| `NEXT_DIST_DIR`             | `.next`                                      | Build output dir; e2e uses `.next-e2e`                          |

## Layout

```
app/                    routes: / (intake) · /ideas (library) · /ideas/[id] · /compare
  providers.tsx         QueryClient, tooltips, MSW bootstrap (dynamic, mock builds only)
components/
  ideas/                cards, list, board, progress timeline, scorecard, report view, claims
  intake/               intake form, recent ideas
  site/                 header, palette host + palette, shortcuts
  ui/                   shadcn primitives (styled with the Soft Mono tokens)
lib/
  api/                  generated schema, typed client, TanStack Query hooks, SSE hook + reducer
  mocks/                MSW handlers, deterministic 1,000-idea dataset, fetch-wrapper install
openapi/openapi.json    contract snapshot authored from the module specs
e2e/                    Playwright specs (flows, keyboard, 360px, axe on every screen)
styles/tokens.css       Soft Mono design tokens (single source of truth)
```

## How data flows

1. `lib/api/client.ts` — one fetch wrapper, typed from `lib/api/schema.d.ts`.
2. `lib/api/hooks.ts` — TanStack Query hooks; query keys in `lib/api/keys.ts`.
3. Live runs — `useRunEvents` streams `/runs/{id}/events` (fetch + ReadableStream),
   resumes with `last_event_id`, dedupes via a pure reducer (`lib/api/run-events.ts`),
   and stops at terminal status.
4. Dev/e2e — `lib/mocks/install.ts` swaps `window.fetch` for an MSW-backed resolver
   (no service worker). The 1,000-idea dataset and run simulator live in `lib/mocks/`.

## Quality gates

- ESLint + Prettier, TypeScript strict with typed routes, `no-explicit-any` clean.
- 51 unit/component tests (Vitest + Testing Library) — reducer, URL-state round-trips,
  badges, filters, intake, run-events hook (resume/backoff), format/download helpers.
- 22 Playwright tests: intake → live progress → report → search → compare, section
  re-run, clarifying questions, exports, keyboard (`/`, `n`, `j`/`k`, ⌘K), 360px
  responsiveness, and axe scans (`wcag2a`–`wcag22aa`) on every screen plus the
  board, palette, and clarify states.
- Measured on the production build with the 1,000-idea mock: LCP 368–532 ms across
  library / intake / idea detail / compare, CLS 0 on every route. Budget: LCP < 2.5 s.

## Notes

- Accessibility target is WCAG 2.2 AA; the design system is Soft Mono
  (`styles/tokens.css`), mapped into Tailwind and shadcn variables in
  `app/globals.css`. No literal colors/radii in components.
- The UI is English-only for now (root spec open question #3); logical CSS
  properties keep an RTL switch possible later.
