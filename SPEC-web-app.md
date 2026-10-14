# Spec: web-app

> Module of [SPEC.md](SPEC.md). Code lives in `frontend/`. Depends on the `idea-core` and `reports` APIs.

## Objective

Make getting an idea in **effortless** and finding it again **instant**.

## Screens

| Route | Purpose |
|---|---|
| `/` **Home / Intake** | One large textarea ("Describe your idea, however rough"), with an **Analyze** button and ⌘/Ctrl+Enter. A collapsed "Add context" link reveals optional region, audience, and budget fields. Below it are recent ideas as cards. |
| `/ideas` **Library** | A search bar (hybrid by default) plus filter chips: status, verdict, category, tag, and score range. Sort by recent, score, or title. There are list and board (by status) views, and URL-synced state so a search can be bookmarked. |
| `/ideas/[id]` **Idea** | A header with verdict, score, and confidence. A live progress timeline while the run is going (SSE). Section tabs: Overview · Market · Competitors · Customers · Feasibility · Business model · Sources. Per section: **Re-run**. There's a version switcher, "Similar ideas", and Export (MD/PDF). |
| `/compare?ids=` | 2–3 ideas side by side. Started by multi-selecting in the Library. |
| **Command palette** (global, ⌘K) | Jump to any idea by title or meaning, plus "New idea", "Compare selected", and recent searches. |

## Interaction Details

- Intake: submitting navigates immediately to `/ideas/[id]` with an optimistic "Queued" state, so there's no waiting on the form.
- Clarifying questions (if the run is `awaiting_input`) appear inline on the idea page as a short form with a **Skip** button.
- Progress: each agent row shows queued → running (with elapsed time) → done or failed, plus a cost meter. Reconnecting resumes the stream.
- Low-confidence scores get a dashed border and a "?" with a tooltip. Unverified claims get muted text and an "unverified" pill.
- Search is debounced (200 ms) and shows a keyword or semantic match hint. An empty state suggests creating an idea from the query.
- Keyboard: `/` focuses search, `n` starts a new idea, `j/k` move through the list, and `Enter` opens.

## Acceptance Criteria

- [ ] Submit with only text works, and an empty submit is disabled. The input survives a reload (draft is kept in localStorage).
- [ ] Progress updates within 1 s of a backend event, and closing and reopening the tab shows the correct state.
- [ ] Library filters and query are reflected in the URL, and back and forward restore them.
- [ ] ⌘K finds an idea by a word that appears only in its brief (semantic or FTS).
- [ ] WCAG 2.2 AA: everything is keyboard-reachable, with visible focus, labeled inputs, and contrast ≥ 4.5:1. No axe violations in e2e.
- [ ] Responsive down to 360 px, and the Library is usable on a phone.
- [ ] LCP < 2.5 s on Library with 1,000 ideas (paginated, 30 per page).

## Testing

Vitest + Testing Library for components (ScoreBadge, filters, progress reducer). Playwright e2e against a
mocked API (MSW): intake → progress → report → search → compare, plus an axe check on each screen.
