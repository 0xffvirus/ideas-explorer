# Research Tools — Feature Guide

> Module `research-tools` of Idea Forge. Code lives in `backend/app/research/`.
> Full specification: [SPEC-research-tools.md](../SPEC-research-tools.md).

## 1. What this module does

The agent pipeline needs **real-world evidence** to validate a business idea:
market numbers, competitor facts, community pain points, and (optionally)
target companies. This module is the single place that collects that evidence.

It gives the rest of the system five things:

1. **One data contract** — `Evidence`: every result carries its source URL.
2. **Four adapters behind one interface** (`ResearchTool`): web search,
   Reddit, Hacker News, and a disabled-by-default company lead finder.
3. **A shared cache** in Postgres so repeated queries never pay twice
   within their TTL.
4. **Rate limiting and resilience** — bounded retries, hard timeouts, and the
   guarantee that one broken provider returns *no results* instead of
   failing a run.
5. **Cost and privacy guardrails** — every call reports its cost to a
   `CostMeter`, and no personal data or secrets ever land in the cache,
   logs, or results.

### Where it fits

```
agent pipeline                        research-tools
-------------------------             -------------------------------------
MarketAgent      ──┐
CompetitorAgent  ──┼──► ResearchTools ──► web  (Tavily)
CustomerAgent    ──┘                      ├─► reddit (posts + comments)
                                          ├─► hn     (Hacker News)
                                          └─► leads  (off by default)
                                               │
                                               ▼
                                      research_cache (Postgres)
```

Agents never talk to providers directly and never touch these database
tables; they receive typed `Evidence` lists. Scores are *not* produced here —
Jev decides, this module only gathers facts.

## 2. Quick start

```python
from app.config import get_settings
from app.research import build_research_tools

tools = build_research_tools(get_settings())      # cache/client optional

try:
    market = await tools.web.search("pet sitting market size 2024", limit=8)
    pain = await tools.reddit.search("pet sitter cancelled last minute", limit=8)
    comments = await tools.reddit.comments_for(pain[0])   # optional deep dive
    chats = await tools.hn.search("pet sitter reliability")
finally:
    await tools.aclose()                          # closes only its own HTTP client
```

Every returned item is an `Evidence` object:

```python
Evidence(
    source="web",                      # web | reddit | hn | leads
    url=HttpUrl("https://..."),        # always present, always http(s)
    title="Pet Sitting Market Size",
    snippet="The market was valued at $2.4 billion ...",   # ≤ 1,500 chars
    published_at=datetime(2024, 6, 1, tzinfo=UTC),         # optional
    score=0.94,                        # provider signal normalized to 0–1
    retrieved_at=datetime.now(UTC),
)
```

## 3. The contract

### `Evidence`

| Field | Guarantee |
|---|---|
| `source` | One of `web`, `reddit`, `hn`, `leads` |
| `url` | Valid `http(s)` URL; URLs carrying credentials (`user@host`) are rejected |
| `title` | Non-empty, HTML-stripped, contact-redacted, ≤ 500 chars |
| `snippet` | HTML-stripped, contact-redacted, ≤ 1,500 chars |
| `published_at` | Timezone-aware UTC (naive input is normalized), or `None` |
| `score` | Provider relevance/upvotes/points normalized to `0.0–1.0`, or `None` |
| `retrieved_at` | When the evidence was fetched from the provider |

`Evidence` is **frozen**: once built, a record cannot be mutated, so cached
and returned data cannot drift.

### `ResearchTool` (the adapter interface)

```python
class ResearchTool(Protocol):
    name: str
    async def search(self, query: str, *, limit: int = 8) -> list[Evidence]: ...
```

### `CompanyLead` (leads only)

`name, domain, industry, size_band, country, why_fit, url` — **company-level
only**. There are deliberately no person fields (no names, emails, phones,
or social profiles), and a test pins that.

### `ToolDisabled`

Raised when a switched-off adapter is used. Only `LeadFinder` raises it
today; `search()` and `find_companies()` always raise it while
`LEADS_ENABLED=false`.

## 4. How one search works

```
search("Pet  Sitting")
   │
   ├─ 1. normalize query            lowercase, collapse whitespace,
   │                                strip control chars, cap at 500 chars
   ├─ 2. cache lookup               key = "adapter:normalized query"
   │       └─ hit? → return cached[:limit]   (0 HTTP calls, $0)
   ├─ 3. for each HTTP attempt:
   │       ├─ token bucket acquire  (per adapter, from config)
   │       └─ request              10 s timeout; retry 429/5xx/timeouts
   │                                up to 2× with jitter; other 4xx stop
   ├─ 4. validate payload          strict Pydantic models per provider
   │                                (third-party JSON is untrusted data)
   ├─ 5. map items → Evidence      strip HTML, redact contacts, truncate,
   │                                normalize scores + timestamps;
   │                                malformed items are skipped
   └─ 6. cache non-empty results   TTL per adapter; then return [:limit]
```

If any step fails, the adapter logs a warning and returns `[]`. **A single
tool failure can never fail an analysis run.**

## 5. The adapters

| Adapter | Provider | Default | Notes |
|---|---|---|---|
| `WebSearch` | Tavily (`POST /search`, bearer key) | on (needs key) | Market data, competitors, regulations. `max_results` clamped to 20. Cost charged per successful call. |
| `RedditSignals` | Reddit official API (OAuth client-credentials) | on (needs credentials) | Posts via `/search?type=link`; `comments_for()` retrieves top comments via the official `/comments/{id}` endpoint. Vote score saturated (`votes / (votes + 50)`). |
| `HackerNewsSignals` | HN Algolia API | on (no key) | Stories/discussions; points saturated the same way. Ask-HN posts without a URL fall back to the item page. |
| `LeadFinder` | TBD (open question in SPEC.md) | **off** | Company leads only. Provider injected via a `LeadProvider` protocol; must be explicitly enabled. |

### Reddit specifics

- The OAuth token is fetched once and reused; a single-flight lock prevents
  duplicate token calls under concurrency, and it refreshes 30 s before expiry.
- `comments_for(post, limit=5)` accepts a post URL or an `Evidence` item.
  Only `reddit.com` URLs are accepted; the request target is rebuilt from
  the extracted post ID, so nothing attacker-controlled reaches the URL.
- Comments are cached under `reddit:comments:{post_id}`.

## 6. Caching

| Aspect | Behaviour |
|---|---|
| Table | `research_cache(key text pk, payload jsonb, expires_at timestamptz)` |
| Key | `adapter:normalized query` (e.g. `web:pet sitting market size`) |
| TTL | Web **7 days**, Reddit/HN **1 day**, leads 7 days (all configurable) |
| Write | Upsert (`ON CONFLICT`), refreshes expiry; empty results are not stored |
| Read | Expired rows are deleted with a race-safe `DELETE ... WHERE expires_at <= now()` |
| Corruption | A payload that no longer matches `Evidence` is treated as a miss |
| Database down | Read/write failures degrade to a miss (logged), never break a search |
| Housekeeping | Every write also purges expired rows using the `expires_at` index |

Because the cache is shared in Postgres (not in-process), two workers or
two runs reuse the same evidence.

## 7. Rate limiting

A **token bucket per adapter**, configured in requests per minute
(`WEB_RATE_LIMIT_PER_MINUTE`, `REDDIT_RATE_LIMIT_PER_MINUTE`,
`HN_RATE_LIMIT_PER_MINUTE`, `LEADS_RATE_LIMIT_PER_MINUTE`).

- One token is consumed **per HTTP attempt**, retries included, so a 429
  storm cannot exceed the configured rate.
- Cache hits consume nothing.
- The bucket is lock-protected and sleeps outside the lock, so concurrent
  searches share the budget fairly.

## 8. Resilience

- **Timeout:** 10 s per request (`RESEARCH_TIMEOUT_SECONDS`).
- **Retries:** up to 2 (`RESEARCH_MAX_RETRIES`) with full jitter and
  exponential ceilings, but only for `429`, `500`, `502`, `503`, `504`,
  timeouts, and connection errors. Other `4xx` (auth, not found) are not
  retried.
- **After exhaustion:** `[]` plus a warning log — no exception escapes.
- **Malformed provider data:** payloads that fail schema validation return
  `[]`; individual broken items (bad URL, empty body) are skipped while the
  rest of the results survive.

## 9. Privacy and security

- **No personal data.** The leads schema is company-only, and no adapter
  maps author/person fields. Emails and phone-shaped numbers found in free
  text are replaced with `[email redacted]` / `[phone redacted]` before
  anything is cached or returned.
- **Secrets stay in settings.** API keys are only used in auth
  headers/basic-auth, never in URLs, cache keys, logs, or results.
- **Log hygiene.** Provider-controlled values are logged with `%r`;
  the database engine is configured with `hide_parameters=True` so failed
  statements cannot dump cached content into logs.
- **URL safety.** Result URLs reject embedded credentials; comment fetching
  only accepts `reddit.com` hosts.
- **Opt-in leads.** The lead adapter requires `LEADS_ENABLED=true`, which
  SPEC.md marks as "ask first" (costs money, personal-data sensitive).

## 10. Cost accounting

Adapters accept an optional `CostMeter` (shared with the LLM and Jev parts
of a run):

- Charged only on **successful** provider calls, so storms and retries cost
  nothing extra.
- Categories are `research:web` and `research:leads`, so the pipeline can
  show a per-tool breakdown.
- Cache hits are free.

## 11. Configuration

All settings come from `.env` (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `TAVILY_API_KEY` | — | Enables web search |
| `TAVILY_COST_PER_SEARCH_USD` | `0.008` | Cost charged per Tavily call |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | — | Enables Reddit |
| `REDDIT_USER_AGENT` | `idea-forge/0.1 (personal research)` | Reddit requires a UA |
| `LEADS_ENABLED` | `false` | Must be `true` to use `LeadFinder` |
| `LEADS_API_KEY` | — | Reserved for the future lead provider |
| `RESEARCH_WEB_TTL_HOURS` | `168` | Web cache TTL |
| `RESEARCH_COMMUNITY_TTL_HOURS` | `24` | Reddit/HN cache TTL |
| `RESEARCH_TIMEOUT_SECONDS` | `10` | Per-request timeout |
| `RESEARCH_MAX_RETRIES` | `2` | Retries after the first attempt |
| `RESEARCH_SNIPPET_MAX_CHARS` | `1500` | Snippet cap (hard max 1500) |
| `WEB_/REDDIT_/HN_/LEADS_RATE_LIMIT_PER_MINUTE` | `60/100/60/30` | Token bucket rates |

Adapters with a missing key or credential do not crash: they log a warning
and return `[]`.

## 12. Public API

Everything imports from the package root:

```python
from app.research import (
    Evidence, CompanyLead, ResearchTool, ToolDisabled,   # contract
    Cache, PostgresCache, InMemoryCache, NullCache,      # caching
    RateLimiter, TokenBucket,                            # limiting
    WebSearch, RedditSignals, HackerNewsSignals, LeadFinder,
    ResearchTools, build_research_tools,                 # wiring
)
```

Callers who hold the bundle get concrete types (`tools.reddit.comments_for`,
`tools.leads.find_companies`), and everything still satisfies the
`ResearchTool` protocol.

## 13. Module layout

```
backend/app/research/
├── contract.py     Evidence, CompanyLead, ResearchTool, Cache, ToolDisabled
├── models.py       ResearchCache SQLAlchemy model
├── cache.py        PostgresCache, InMemoryCache, NullCache
├── http.py         fetch_json: timeout, jittered retries, never raises
├── ratelimit.py    TokenBucket + RateLimiter protocol
├── text.py         HTML stripping, snippets, PII redaction, query normalization
├── toolkit.py      ResearchTools bundle + build_research_tools factory
├── adapters/
│   ├── base.py     HttpAdapter: cache → limit → fetch → map → cache
│   ├── web.py      Tavily
│   ├── reddit.py   Reddit OAuth + posts + comments_for
│   ├── hn.py       Hacker News Algolia
│   └── leads.py    LeadFinder + LeadProvider protocol (disabled by default)
└── __init__.py     public surface
```

## 14. Testing and quality

```bash
cd backend
uv run pytest -q                    # 131 tests: unit + integration, no network
uv run pytest -q -m eval            # live providers (HN free; Tavily/Reddit need keys)
uv run ruff check . && uv run pyright
```

- **Unit tests** use `respx` with recorded fixtures in
  `tests/fixtures/research/` — mapping, cache hits (0 HTTP calls), 429
  storms, malformed payloads, limits, redaction, token refresh, PII rules.
- **Integration tests** run against real Postgres (compose): cache
  round-trips, TTL, upsert, purge, DB-down behaviour, namespace isolation.
- **Eval tests** are excluded from the default suite and only run with
  `-m eval`; they never run in CI.
- Coverage is **96%** on `app/` (every research file ≥ 92%); ruff and
  pyright (strict) are clean.

### Acceptance criteria → proof

| Criterion (SPEC-research-tools.md) | Proven by |
|---|---|
| Each adapter maps provider JSON → `Evidence`, fixture-tested | `tests/unit/research/test_{web,reddit,hn}_adapter.py` |
| Repeat query within TTL hits cache with 0 HTTP calls (respx) | `test_web_adapter.py`, `tests/integration/research/test_cache_end_to_end.py` |
| 429 storm → bounded retries, then `[]`, no exception | `test_http.py`, storm tests in each adapter |
| `LeadFinder` raises `ToolDisabled` unless enabled; no person fields | `test_leads.py`, `test_contract.py` |
| Snippets truncated and HTML-stripped | `test_text.py`, adapter assertions |

## 15. What this module does not do

- It does not score or judge anything — that is Jev's job (`jev-gate`).
- It does not run agents or orchestrate runs — that is `agent-pipeline`.
- It writes only the `research_cache` table; ideas/versions/runs belong to
  other modules.
- It never scrapes: only official APIs are used.
- The lead provider is intentionally unimplemented until the SPEC.md open
  question is answered and someone approves enabling it.
