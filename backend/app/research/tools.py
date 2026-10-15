"""Research tools: one uniform, cached interface over every evidence source."""

from __future__ import annotations

from datetime import timedelta
from typing import Protocol

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.cost import CostMeter
from app.research.adapters.hackernews import HackerNewsProvider
from app.research.adapters.leads import LeadProvider
from app.research.adapters.reddit import RedditProvider
from app.research.adapters.tavily import TavilyProvider
from app.research.cache import ResearchCache, cache_key
from app.research.errors import ResearchUnavailable, ToolDisabled
from app.research.evidence import CompanyLead, Evidence


class ResearchTool(Protocol):
    """Uniform access to one evidence source (consumed by agent-pipeline)."""

    name: str

    async def search(self, query: str, *, limit: int = 8) -> list[Evidence]:
        """Return up to ``limit`` pieces of evidence for ``query``.

        Transient provider failures yield ``[]``; configuration errors raise
        :class:`~app.research.errors.ResearchUnavailable` or
        :class:`~app.research.errors.ToolDisabled`.
        """
        ...


class _EvidenceProvider(Protocol):
    """What the cached tool layer needs from an HTTP provider."""

    name: str

    async def search(self, query: str, limit: int = 8) -> list[Evidence]:
        """Return up to ``limit`` results for ``query``."""
        ...

    async def aclose(self) -> None:
        """Release the provider's HTTP resources."""
        ...


class _CachedTool:
    """Cache-first flow shared by the HTTP-backed tools.

    The cache is checked before the rate limiter and any HTTP call; misses run
    the provider and store non-empty results under the adapter's TTL, so a
    transient empty result never poisons the cache.
    """

    name: str

    def __init__(
        self, provider: _EvidenceProvider, *, cache: ResearchCache, ttl: timedelta
    ) -> None:
        self.name = provider.name
        self._provider = provider
        self._cache = cache
        self._ttl = ttl

    async def search(self, query: str, *, limit: int = 8) -> list[Evidence]:
        key = cache_key(self.name, query, limit)
        cached = await self._cache.get(key)
        if cached is not None:
            return cached[: max(0, limit)]
        items = await self._provider.search(query, limit)
        if items:
            await self._cache.set(key, items, self._ttl)
        return items

    async def aclose(self) -> None:
        """Close the provider's HTTP client when it owns one."""
        await self._provider.aclose()


class WebSearch(_CachedTool):
    """Web search (Tavily by default) for market, competitor, and regulation data."""


class RedditSignals(_CachedTool):
    """Reddit posts and comments that express the pain."""


class HackerNewsSignals(_CachedTool):
    """Hacker News stories via the free Algolia API."""


class LeadFinder:
    """Company-level leads only; off until ``LEADS_ENABLED=true`` (root open question).

    The provider port is defined in :mod:`app.research.adapters.leads` and stays
    unconfigured until a lead DB is approved, so an enabled finder without a
    provider raises :class:`ResearchUnavailable`.
    """

    name = "leads"

    def __init__(self, settings: Settings, provider: LeadProvider | None = None) -> None:
        self._settings = settings
        self._provider = provider

    async def find_leads(self, query: str, *, limit: int = 8) -> list[CompanyLead]:
        """Return company leads; raises when disabled or without a provider."""
        return await self._ready().find(query, limit=limit)

    async def search(self, query: str, *, limit: int = 8) -> list[Evidence]:
        """Lead results as evidence so they flow through the same pipeline."""
        leads = await self._ready().find(query, limit=limit)
        return [self._to_evidence(lead) for lead in leads]

    def _ready(self) -> LeadProvider:
        if not self._settings.leads_enabled:
            raise ToolDisabled("lead finder is disabled; set LEADS_ENABLED=true after approval")
        if self._provider is None:
            raise ResearchUnavailable("lead provider not configured")
        return self._provider

    @staticmethod
    def _to_evidence(lead: CompanyLead) -> Evidence:
        parts = [part for part in (lead.industry, lead.size_band, lead.country) if part]
        return Evidence(
            source="leads",
            url=lead.url,
            title=lead.name,
            snippet=" | ".join([*parts, lead.why_fit]),
        )


def build_default_tools(
    settings: Settings,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    meter: CostMeter | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> dict[str, ResearchTool]:
    """Build the four tools by key: ``web``, ``reddit``, ``hn``, and ``leads``.

    Every key is always present. Tools whose provider is unconfigured raise
    their configuration error at ``search()`` time, not here, and none of them
    does any I/O at construction time.
    """
    cache = ResearchCache(session_factory)
    web_ttl = timedelta(hours=settings.research_web_ttl_hours)
    community_ttl = timedelta(hours=settings.research_community_ttl_hours)
    return {
        "web": WebSearch(
            TavilyProvider(settings, http_client=http_client, meter=meter),
            cache=cache,
            ttl=web_ttl,
        ),
        "reddit": RedditSignals(
            RedditProvider(settings, http_client=http_client, meter=meter),
            cache=cache,
            ttl=community_ttl,
        ),
        "hn": HackerNewsSignals(
            HackerNewsProvider(settings, http_client=http_client, meter=meter),
            cache=cache,
            ttl=community_ttl,
        ),
        "leads": LeadFinder(settings),
    }
