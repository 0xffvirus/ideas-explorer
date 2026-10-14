"""Shared plumbing for HTTP-backed research adapters.

Handles the cross-cutting behaviour from SPEC-research-tools: cache lookup,
rate limiting, bounded retries, snippet truncation, cost accounting, and the
guarantee that a failing adapter returns no results instead of raising.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Mapping
from dataclasses import dataclass, field

import httpx

from app.cost import CostMeter
from app.obs import get_logger
from app.research.contract import (
    MAX_EVIDENCE_RESULTS,
    SNIPPET_MAX_CHARS,
    Cache,
    Evidence,
)
from app.research.http import SleepFn, fetch_json
from app.research.ratelimit import RateLimiter
from app.research.text import normalize_query

logger = get_logger(__name__)


@dataclass(frozen=True)
class AdapterDeps:
    """Everything an HTTP adapter needs besides provider-specific settings."""

    client: httpx.AsyncClient
    cache: Cache
    rate_limiter: RateLimiter
    meter: CostMeter | None = None
    timeout_seconds: float = 10.0
    retries: int = 2
    snippet_max_chars: int = SNIPPET_MAX_CHARS
    ttl_seconds: int = 86_400
    sleep: SleepFn = field(default=asyncio.sleep)
    rng: random.Random | None = None


class HttpAdapter:
    """Base class implementing the :class:`~app.research.contract.ResearchTool` protocol."""

    name: str = "http"
    max_results: int = MAX_EVIDENCE_RESULTS

    def __init__(self, *, deps: AdapterDeps) -> None:
        self._client = deps.client
        self._cache = deps.cache
        self._rate_limiter = deps.rate_limiter
        self._meter = deps.meter
        self._timeout_seconds = deps.timeout_seconds
        self._retries = deps.retries
        self.snippet_max_chars = min(deps.snippet_max_chars, SNIPPET_MAX_CHARS)
        self.ttl_seconds = deps.ttl_seconds
        self._sleep = deps.sleep
        self._rng = deps.rng

    async def search(self, query: str, *, limit: int = 8) -> list[Evidence]:
        """Return sourced evidence for ``query``; never raises on provider failure."""
        try:
            return await self._search(query, limit=limit)
        except Exception:
            logger.exception("research adapter %s failed; returning no results", self.name)
            return []

    async def _search(self, query: str, *, limit: int) -> list[Evidence]:
        normalized = normalize_query(query)
        if not normalized or limit <= 0:
            return []
        key = f"{self.name}:{normalized}"
        cached = await self._cache.get(key)
        if cached is not None:
            return cached[:limit]
        fetched = await self._fetch(normalized, min(limit, self.max_results))
        items = fetched[: self.max_results]
        if items:
            await self._cache.set(key, items, ttl_seconds=self.ttl_seconds)
        return items[:limit]

    def charge(self, usd: float) -> None:
        if self._meter is not None and usd > 0:
            self._meter.add(usd, category=f"research:{self.name}")

    async def _fetch_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        data: Mapping[str, str] | None = None,
        json: object | None = None,
        auth: tuple[str, str] | None = None,
    ) -> object | None:
        return await fetch_json(
            self._client,
            method,
            url,
            timeout_seconds=self._timeout_seconds,
            retries=self._retries,
            headers=headers,
            params=params,
            data=data,
            json=json,
            auth=auth,
            sleep=self._sleep,
            rng=self._rng,
            on_attempt=self._rate_limiter.acquire,
        )

    async def _fetch(self, query: str, limit: int) -> list[Evidence]:
        raise NotImplementedError
