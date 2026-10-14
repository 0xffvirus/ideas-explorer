"""Hacker News signals adapter (Algolia API, no key required)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError

from app.obs import get_logger
from app.research.adapters.base import AdapterDeps, HttpAdapter
from app.research.contract import Evidence
from app.research.text import clean_snippet, clean_title, parse_iso_datetime, saturate_score

logger = get_logger(__name__)

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
HN_ITEM_URL = "https://news.ycombinator.com/item?id={object_id}"
SCORE_HALF_POINT = 50.0
TITLE_FALLBACK_CHARS = 80


class _HnHit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    objectID: str = ""
    title: str | None = None
    url: str | None = None
    story_text: str | None = None
    points: int | None = None
    created_at: str | None = None


class _HnResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hits: list[_HnHit] = Field(default_factory=list[_HnHit])


class HackerNewsSignals(HttpAdapter):
    """Stories and discussions from Hacker News."""

    name = "hn"

    def __init__(self, *, deps: AdapterDeps, endpoint: str = HN_SEARCH_URL) -> None:
        super().__init__(deps=deps)
        self._endpoint = endpoint

    async def _fetch(self, query: str, limit: int) -> list[Evidence]:
        payload = await self._fetch_json(
            "GET",
            self._endpoint,
            params={"query": query, "tags": "story", "hitsPerPage": str(limit)},
        )
        if payload is None:
            return []
        try:
            response = _HnResponse.model_validate(payload)
        except ValidationError:
            logger.warning("hacker news returned an unexpected payload for query=%r", query)
            return []
        items: list[Evidence] = []
        for hit in response.hits:
            evidence = self._map_hit(hit)
            if evidence is not None:
                items.append(evidence)
        return items

    def _map_hit(self, hit: _HnHit) -> Evidence | None:
        text = (hit.story_text or "").strip()
        title = clean_title(hit.title)
        if not title and not text:
            return None
        if not title:
            title = clean_snippet(text, max_chars=TITLE_FALLBACK_CHARS)
        url = hit.url or HN_ITEM_URL.format(object_id=hit.objectID)
        try:
            return Evidence(
                source="hn",
                url=HttpUrl(url),
                title=title,
                snippet=clean_snippet(text or title, max_chars=self.snippet_max_chars),
                published_at=parse_iso_datetime(hit.created_at),
                score=saturate_score(float(hit.points or 0), half_point=SCORE_HALF_POINT),
            )
        except ValidationError:
            logger.warning("skipping malformed hacker news hit objectID=%r", hit.objectID)
            return None
