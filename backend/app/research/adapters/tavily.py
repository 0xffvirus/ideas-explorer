"""Tavily web-search provider behind the swappable WebSearchProvider port."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Protocol, cast

import httpx
from pydantic import HttpUrl

from app.config import Settings
from app.cost import CostMeter
from app.obs import get_logger
from app.research.adapters import as_float, as_str, json_object, request_with_retries
from app.research.errors import ResearchUnavailable
from app.research.evidence import Evidence, sanitize_snippet
from app.research.ratelimit import TokenBucketRateLimiter

logger = get_logger(__name__)

SEARCH_URL = "https://api.tavily.com/search"


class WebSearchProvider(Protocol):
    """Port for a web-search backend; Exa or Brave can implement it instead."""

    name: str

    async def search(self, query: str, limit: int = 8) -> list[Evidence]:
        """Return up to ``limit`` results for ``query``."""
        ...


def _parse_published(value: object) -> datetime | None:
    text = as_str(value).strip()
    if not text:
        return None
    parsed: datetime | None = None
    with suppress(ValueError):
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed is not None:
        return parsed
    try:
        return parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None


class TavilyProvider:
    """Tavily REST search; charges ``tavily_cost_per_search_usd`` per HTTP search.

    Results are mapped from ``results[{title,url,content,score,published_date?}]``.
    Scores are Tavily's own relevance values and are clamped to 0-1 by
    :class:`~app.research.evidence.Evidence`.
    """

    name = "web"

    def __init__(
        self,
        settings: Settings,
        *,
        api_key: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        meter: CostMeter | None = None,
        limiter: TokenBucketRateLimiter | None = None,
    ) -> None:
        self._settings = settings
        self._api_key = settings.tavily_api_key if api_key is None else api_key
        self._http = http_client if http_client is not None else httpx.AsyncClient()
        self._owns_http = http_client is None
        self._meter = meter
        self._limiter = (
            limiter
            if limiter is not None
            else TokenBucketRateLimiter(settings.web_rate_limit_per_minute)
        )

    async def aclose(self) -> None:
        """Close the HTTP client when this provider created it."""
        if self._owns_http:
            await self._http.aclose()

    async def search(self, query: str, limit: int = 8) -> list[Evidence]:
        """Search through Tavily; raises ResearchUnavailable without an API key."""
        if not self._api_key:
            raise ResearchUnavailable("TAVILY_API_KEY is not configured")
        await self._limiter.acquire()
        response = await request_with_retries(
            self._http,
            "POST",
            SEARCH_URL,
            max_retries=self._settings.research_max_retries,
            request_timeout=self._settings.research_timeout_seconds,
            json={
                "api_key": self._api_key,
                "query": query,
                "max_results": limit,
                "include_answer": False,
            },
        )
        if response is None:
            return []
        if response.status_code != 200:
            logger.warning("tavily returned HTTP %s; returning no results", response.status_code)
            return []
        self._charge()
        return self._map(response)

    def _charge(self) -> None:
        if self._meter is not None:
            self._meter.add(self._settings.tavily_cost_per_search_usd, category="web")

    def _map(self, response: httpx.Response) -> list[Evidence]:
        data = json_object(response)
        raw_results = data.get("results") if data is not None else None
        if not isinstance(raw_results, list):
            logger.warning("tavily response is missing the 'results' list")
            return []
        items: list[Evidence] = []
        for entry in cast("list[object]", raw_results):
            if not isinstance(entry, Mapping):
                continue
            try:
                items.append(self._to_evidence(cast("Mapping[str, object]", entry)))
            except (ValueError, KeyError) as exc:
                logger.warning("skipping malformed tavily result: %s", exc)
        return items

    def _to_evidence(self, entry: Mapping[str, object]) -> Evidence:
        return Evidence(
            source="web",
            url=HttpUrl(cast("str", entry["url"])),
            title=as_str(entry.get("title")),
            snippet=sanitize_snippet(
                as_str(entry.get("content")), self._settings.research_snippet_max_chars
            ),
            published_at=_parse_published(entry.get("published_date")),
            score=as_float(entry.get("score")),
        )
