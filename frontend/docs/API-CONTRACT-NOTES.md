# API contract notes

The frontend types are generated from `openapi/openapi.json`, a **contract snapshot**
authored from the module specs:

- `SPEC-idea-core.md` — ideas, versions, tags, search, pagination, reports paths
- `SPEC-agent-pipeline.md` — runs, run steps, SSE progress events, re-run
- `SPEC-reports.md` — report shape, scorecard, sources, compare

Regenerate the types with `pnpm gen:api`. To diff against a running backend:

```bash
OPENAPI_URL=http://localhost:8000/openapi.json pnpm gen:api
```

## Assumptions that need backend sign-off

1. **`POST /runs/{id}/respond`** (marked `x-assumed` in the snapshot) does not exist
   in any module spec yet. The web-app spec requires answering or skipping clarifying
   questions inline, so the contract assumes:
   ```json
   { "answers": [{ "question_id": "q1", "answer": "…" }], "skip": false }
   ```
   Returns `202` with the resumed `Run`. `409` when the run is not awaiting input.
2. **`POST /runs/{id}/steps/{step}/rerun`** returns `202` with the updated `Run`
   (steps marked running) and streams the remaining events on the same run id. The
   frontend resumes the SSE stream from its last event id; if the backend starts a
   **new** run id for re-runs, the client handles it (new id ⇒ fresh stream), but
   the returned body must contain the new `Run`.
3. **`GET /ideas/{id}` includes `latest_run`** (with `steps` and, when paused,
   `questions`), so progress can be seeded correctly on reload.
4. **Report payload**: claims carry `source_urls[]`, `verified`, and `confidence`;
   `sources[]` is the deduplicated numbered list; `header.partial` and
   `sections_status` drive the partial-run UI.
5. **Search response** echoes `mode` so the UI can show a keyword/semantic match
   hint; `cursor` is an opaque string and `next_cursor` is `null` on the last page.

If the backend diverges from any of these, regenerate `schema.d.ts` and adjust
`lib/mocks/handlers.ts` + the fixtures together, then run `pnpm check && pnpm e2e`.
