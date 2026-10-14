# Spec: research-tools

> Module of [SPEC.md](SPEC.md). Code lives in `backend/app/research/`. Depends on nothing.

## Objective

Give agents a uniform, cached, rate-limited way to collect **real-world evidence**.
Every result carries its source URL so claims can be traced.

## Contract (consumed by agent-pipeline)

```python
class Evidence(BaseModel):
    source: Literal["web", "reddit", "hn", "leads"]
    url: HttpUrl
    title: str
    snippet: str            # ≤ 1,500 chars of the relevant text
    published_at: datetime | None
    score: float | None     # provider relevance / upvotes, normalized 0-1
    retrieved_at: datetime

class ResearchTool(Protocol):
    name: str
    async def search(self, query: str, *, limit: int = 8) -> list[Evidence]: ...
```

`CompanyLead` (leads only): `name, domain, industry, size_band, country, why_fit, url`.
**No individual names, emails, or phones.**

## Adapters

| Adapter | Provider | Default | Notes |
|---|---|---|---|
| `WebSearch` | Tavily (behind an interface; Exa or Brave can be swapped in) | on | market data, competitors, regulations |
| `RedditSignals` | Reddit official API (OAuth app) | on | posts and comments that express the pain. Respect the 100 QPM limit |
| `HackerNewsSignals` | HN Algolia API | on | free, with no key |
| `LeadFinder` | TBD (see root Open Questions) | **off** | needs `LEADS_ENABLED=true` and explicit approval |

## Cross-cutting Behaviour

- **Cache:** a Postgres table `research_cache(key, payload, expires_at)`. The key is `adapter+normalized query`,
  with a TTL of 7 days (web) or 1 day (community).
- **Rate limit:** a token bucket per adapter, with limits set in config.
- **Resilience:** 10 s timeout, 2 retries with jitter on 429/5xx, then return `[]` and log a warning.
  A single tool failure never fails a run.
- **Cost accounting:** each call reports `cost_usd` to a `CostMeter` passed in by the caller.

## Acceptance Criteria

- [ ] Each adapter maps provider JSON → `Evidence` and is tested against recorded fixtures.
- [ ] Repeating a query within the TTL hits the cache (0 HTTP calls, as asserted with respx).
- [ ] A 429 storm leads to bounded retries, then `[]`, with no exception escaping.
- [ ] `LeadFinder` raises `ToolDisabled` unless enabled, and its output schema has no person-level fields.
- [ ] Snippets are truncated and stripped of HTML.

## Testing

Unit tests with `respx` and fixtures in `tests/fixtures/research/`. Live checks live only in `-m eval`.
