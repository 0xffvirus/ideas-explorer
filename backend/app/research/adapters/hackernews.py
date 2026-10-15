"""Hacker News provider using the free Algolia search API (no key required)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import cast

import httpx
from pydantic import HttpUrl

from app.config import Settings
from app.cost import CostMeter
from app.obs import get_logger
from app.research.adapters import as_float, as_str, json_object, request_with_retries
from app.research.evidence import Evidence, sanitize_snippet
from app.research.ratelimit import TokenBucketRateLimiter

logger = get_logger(__name__)

SEARCH_URL = "https://hn.algolia.com/api/v1/search"
POINTS_FULL_SCORE = 300.0


def normalize_points(points: float) -> float:
    """Map HN points to 0-1: ``min(1, points / 300)``."""
    return min(1.0, max(0.0, points / POINTS_FULL_SCORE))


def _parse_created_at(value: object) -> datetime | None:
    text = as_str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


class HackerNewsProvider:
    """HN story search through Algolia; free and keyless."""

    name = "hn"

    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.AsyncClient | None = None,
        meter: CostMeter | None = None,
        limiter: TokenBucketRateLimiter | None = None,
    ) -> None:
        self._settings = settings
        self._http = http_client if http_client is not None else httpx.AsyncClient()
        self._owns_http = http_client is None
        self._meter = meter
        self._limiter = (
            limiter
            if limiter is not None
            else TokenBucketRateLimiter(settings.hn_rate_limit_per_minute)
        )

    async def aclose(self) -> None:
        """Close the HTTP client when this provider created it."""
        if self._owns_http:
            await self._http.aclose()

    async def search(self, query: str, limit: int = 8) -> list[Evidence]:
        """Search HN stories; transient failures return ``[]``."""
        await self._limiter.acquire()
        response = await request_with_retries(
            self._http,
            "GET",
            SEARCH_URL,
            max_retries=self._settings.research_max_retries,
            request_timeout=self._settings.research_timeout_seconds,
            params={"query": query, "tags": "story", "hitsPerPage": limit},
        )
        if response is None:
            return []
        if response.status_code != 200:
            logger.warning(
                "hacker news returned HTTP %s; returning no results", response.status_code
            )
            return []
        return self._map(response)

    def _map(self, response: httpx.Response) -> list[Evidence]:
        data = json_object(response)
        raw_hits = data.get("hits") if data is not None else None
        if not isinstance(raw_hits, list):
            logger.warning("hacker news response is missing the 'hits' list")
            return []
        items: list[Evidence] = []
        for hit in cast("list[object]", raw_hits):
            if not isinstance(hit, Mapping):
                continue
            try:
                items.append(self._to_evidence(cast("Mapping[str, object]", hit)))
            except ValueError as exc:
                logger.warning("skipping malformed hacker news result: %s", exc)
        return items

    def _to_evidence(self, hit: Mapping[str, object]) -> Evidence:
        title = as_str(hit.get("title"))
        object_id = as_str(hit.get("objectID"))
        url = as_str(hit.get("url")) or f"https://news.ycombinator.com/item?id={object_id}"
        snippet = as_str(hit.get("story_text")) or as_str(hit.get("comment_text")) or title
        points = as_float(hit.get("points"))
        return Evidence(
            source="hn",
            url=HttpUrl(url),
            title=title,
            snippet=sanitize_snippet(snippet, self._settings.research_snippet_max_chars),
            published_at=_parse_created_at(hit.get("created_at")),
            score=None if points is None else normalize_points(points),
        )
