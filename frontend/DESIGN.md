# Idea Forge frontend — design decisions

This project uses the **Soft Mono** design system. `styles/tokens.css` is the single
source of truth for values; `app/globals.css` maps them into Tailwind v4 theme
variables and aliases the shadcn/ui CSS variables onto them. Components consume
semantic utilities (`bg-canvas`, `text-ink-secondary`, `rounded-card`, `.t-*`).

## Decisions beyond the system defaults

| Decision                                                                                                           | Reason                                                                                                                                      |
| ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Light theme only (no `.dark` token set)                                                                            | Soft Mono is light-first; dark mode was not requested. The `dark:` variant remains available on shadcn primitives if it is ever added.      |
| System font stack (`ui-sans-serif …`), no webfonts                                                                 | Protects LCP (no font download/FOUT); Soft Mono's Thmanyah Sans drop-in can be added later via `next/font/local` when licensed files exist. |
| shadcn/ui components restyled with Soft Mono tokens (pill buttons ≥ 44 px, 12 px field radius, 24 px cards)        | Keeps shadcn's accessible primitives (Radix) while meeting Soft Mono's shape/touch-target rules.                                            |
| Tabs list scrolls horizontally under `lg`                                                                          | Seven report tabs cannot fit at 360 px; the tab strip is the one intentional internal scroll region.                                        |
| Two extra semantic colors (`--color-warning`, `--color-info`)                                                      | Needed for the partial-run banner; derived from the palette and recorded here.                                                              |
| Skeletons mirror final layout (idea page uses the same component for the server fallback and client pending state) | Keeps CLS ≤ 0.076 across routes (measured).                                                                                                 |
| View-only URL params (report `?tab=`, `?version=`) use `window.history.replaceState`                               | Avoids an RSC round trip per tab switch on the dynamic idea route; deep links still work.                                                   |

## Accessibility contract (WCAG 2.2 AA)

- Skip link target `#main` exists on every route; one `main` landmark per page.
- Visible `:focus-visible` ring, 44 px minimum targets, labeled inputs, logical
  properties (`ps/pe/ms/me`) so RTL is a language change, not a refactor.
- Score badges announce Jev confidence to screen readers; low-confidence scores add
  a dashed border and "?" (not color-only).
- Unverified claims are muted plus an explicit "unverified" pill.
- Axe scans (`wcag2a`…`wcag22aa`) run in e2e on intake, library, board, idea detail
  (overview + market), compare, command palette, and the clarifying-questions state.

## Exceptions register

- `components/ui/*` are vendored shadcn files; their internal classes reference
  shadcn variables (aliased to Soft Mono). Treat them as system code: restyle via
  tokens, not per-screen overrides.
- `first paint with MSW enabled` renders nothing until the mock layer installs
  (dev/e2e only). Production builds never include the mock chunk — verified with a
  `NEXT_PUBLIC_API_MOCKING=disabled` build (no `installMockFetch` chunk).
