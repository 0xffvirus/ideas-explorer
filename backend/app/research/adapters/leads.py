"""Lead DB adapter. Disabled by default; company-level data only.

The provider is an open question in SPEC.md, so the adapter is written
against an injectable :class:`LeadProvider` protocol. Until a provider is
chosen and ``LEADS_ENABLED=true`` with explicit approval, every search
raises :class:`~app.research.contract.ToolDisabled`.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import HttpUrl

from app.cost import CostMeter
from app.obs import get_logger
from app.research.contract import SNIPPET_MAX_CHARS, Cache, CompanyLead, Evidence, ToolDisabled
from app.research.ratelimit import RateLimiter
from app.research.text import clean_snippet, normalize_query

logger = get_logger(__name__)


class LeadProvider(Protocol):
    """Company search backend (Apollo, Clearbit, ...). Company-level only."""

    async def find(self, query: str, *, limit: int) -> list[CompanyLead]: ...


class LeadFinder:
    """Finds target companies; raises :class:`ToolDisabled` unless enabled."""

    name = "leads"

    def __init__(
        self,
        *,
        enabled: bool,
        cache: Cache,
        provider: LeadProvider | None = None,
        rate_limiter: RateLimiter | None = None,
        meter: CostMeter | None = None,
        cost_per_search_usd: float = 0.0,
        ttl_seconds: int = 604_800,
        snippet_max_chars: int = SNIPPET_MAX_CHARS,
    ) -> None:
        self._enabled = enabled
        self._cache = cache
        self._provider = provider
        self._rate_limiter = rate_limiter
        self._meter = meter
        self._cost_per_search_usd = max(0.0, cost_per_search_usd)
        self.ttl_seconds = ttl_seconds
        self.snippet_max_chars = min(snippet_max_chars, SNIPPET_MAX_CHARS)

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def search(self, query: str, *, limit: int = 8) -> list[Evidence]:
        """Company leads as evidence; cached like any other adapter."""
        try:
            self._require_enabled()
            normalized = normalize_query(query)
            if not normalized or limit <= 0:
                return []
            key = f"{self.name}:{normalized}"
            cached = await self._cache.get(key)
            if cached is not None:
                return cached[:limit]
            leads = await self._find(normalized, limit=limit)
            items = [item for lead in leads if (item := self._to_evidence(lead)) is not None]
            if items:
                await self._cache.set(key, items, ttl_seconds=self.ttl_seconds)
            return items[:limit]
        except ToolDisabled:
            raise
        except Exception:
            logger.exception("leads adapter failed; returning no results")
            return []

    async def find_companies(self, query: str, *, limit: int = 8) -> list[CompanyLead]:
        try:
            self._require_enabled()
            normalized = normalize_query(query)
            if not normalized or limit <= 0:
                return []
            return (await self._find(normalized, limit=limit))[:limit]
        except ToolDisabled:
            raise
        except Exception:
            logger.exception("leads provider failed; returning no companies")
            return []

    async def _find(self, normalized_query: str, *, limit: int) -> list[CompanyLead]:
        if self._provider is None:
            logger.warning("LeadFinder is enabled but no provider is configured; no leads")
            return []
        if self._rate_limiter is not None:
            await self._rate_limiter.acquire()
        leads = await self._provider.find(normalized_query, limit=limit)
        self._charge()
        return leads

    def _charge(self) -> None:
        if self._meter is not None and self._cost_per_search_usd > 0:
            self._meter.add(self._cost_per_search_usd, category=f"research:{self.name}")

    def _require_enabled(self) -> None:
        if not self._enabled:
            raise ToolDisabled("leads adapter is disabled; set LEADS_ENABLED=true to enable it")

    def _to_evidence(self, lead: CompanyLead) -> Evidence | None:
        url = lead.url
        if url is None and lead.domain:
            domain = lead.domain.removeprefix("https://").removeprefix("http://").strip("/")
            if domain:
                url = f"https://{domain}"
        if url is None:
            return None
        details = " · ".join(part for part in (lead.industry, lead.size_band, lead.country) if part)
        try:
            return Evidence(
                source="leads",
                url=HttpUrl(str(url)),
                title=lead.name,
                snippet=clean_snippet(
                    lead.why_fit or details or lead.name, max_chars=self.snippet_max_chars
                ),
            )
        except ValueError:
            logger.warning("skipping lead with unconstructable url name=%r", lead.name)
            return None
