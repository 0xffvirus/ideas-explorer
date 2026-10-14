"""Wire the research adapters with a shared client, cache, meter, and limits."""

from __future__ import annotations

import httpx

from app.config import Settings
from app.cost import CostMeter
from app.research.adapters import (
    AdapterDeps,
    HackerNewsSignals,
    LeadFinder,
    LeadProvider,
    RedditSignals,
    WebSearch,
)
from app.research.cache import NullCache
from app.research.contract import SNIPPET_MAX_CHARS, Cache, ResearchTool
from app.research.ratelimit import TokenBucket


class ResearchTools:
    """The four adapters, built once per run and closed together."""

    def __init__(
        self,
        *,
        web: WebSearch,
        reddit: RedditSignals,
        hn: HackerNewsSignals,
        leads: LeadFinder,
        owned_client: httpx.AsyncClient | None,
    ) -> None:
        self.web = web
        self.reddit = reddit
        self.hn = hn
        self.leads = leads
        self._owned_client = owned_client

    def all(self) -> tuple[ResearchTool, ResearchTool, ResearchTool, LeadFinder]:
        return (self.web, self.reddit, self.hn, self.leads)

    def by_name(self, name: str) -> ResearchTool:
        for tool in self.all():
            if tool.name == name:
                return tool
        raise KeyError(f"unknown research tool: {name}")

    async def aclose(self) -> None:
        if self._owned_client is not None:
            await self._owned_client.aclose()


def build_research_tools(
    settings: Settings,
    *,
    cache: Cache | None = None,
    meter: CostMeter | None = None,
    client: httpx.AsyncClient | None = None,
    lead_provider: LeadProvider | None = None,
) -> ResearchTools:
    """Build the adapter bundle from settings.

    The HTTP client and cache may be injected (tests, shared app resources);
    otherwise the bundle creates and owns a client and uses a null cache.
    """
    owned_client = client if client is not None else httpx.AsyncClient()
    resolved_cache: Cache = cache if cache is not None else NullCache()
    snippet_max_chars = min(settings.research_snippet_max_chars, SNIPPET_MAX_CHARS)
    web_ttl = settings.research_web_ttl_hours * 3600
    community_ttl = settings.research_community_ttl_hours * 3600

    def deps(rate_per_minute: int, ttl_seconds: int) -> AdapterDeps:
        return AdapterDeps(
            client=owned_client,
            cache=resolved_cache,
            rate_limiter=TokenBucket(rate_per_minute),
            meter=meter,
            timeout_seconds=settings.research_timeout_seconds,
            retries=settings.research_max_retries,
            snippet_max_chars=snippet_max_chars,
            ttl_seconds=ttl_seconds,
        )

    return ResearchTools(
        web=WebSearch(
            api_key=settings.tavily_api_key,
            cost_per_search_usd=settings.tavily_cost_per_search_usd,
            deps=deps(settings.web_rate_limit_per_minute, web_ttl),
        ),
        reddit=RedditSignals(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
            deps=deps(settings.reddit_rate_limit_per_minute, community_ttl),
        ),
        hn=HackerNewsSignals(deps=deps(settings.hn_rate_limit_per_minute, community_ttl)),
        leads=LeadFinder(
            enabled=settings.leads_enabled,
            cache=resolved_cache,
            provider=lead_provider,
            rate_limiter=TokenBucket(settings.leads_rate_limit_per_minute),
            meter=meter,
            ttl_seconds=web_ttl,
            snippet_max_chars=snippet_max_chars,
        ),
        owned_client=owned_client if client is None else None,
    )


__all__ = ["ResearchTools", "build_research_tools"]
