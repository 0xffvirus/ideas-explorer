"""Web search adapter (Tavily by default, behind a thin interface)."""

from __future__ import annotations

from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError

from app.obs import get_logger
from app.research.adapters.base import AdapterDeps, HttpAdapter
from app.research.contract import Evidence
from app.research.text import clamp01, clean_snippet, clean_title, parse_iso_datetime

logger = get_logger(__name__)

TAVILY_ENDPOINT = "https://api.tavily.com/search"


class _TavilyResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = ""
    url: str = ""
    content: str = ""
    score: float | None = None
    published_date: str | None = None


class _TavilyResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    results: list[_TavilyResult] = Field(default_factory=list[_TavilyResult])


class WebSearch(HttpAdapter):
    """Market data, competitor facts, and regulations via Tavily."""

    name = "web"

    def __init__(
        self,
        *,
        api_key: str,
        cost_per_search_usd: float = 0.0,
        endpoint: str = TAVILY_ENDPOINT,
        deps: AdapterDeps,
    ) -> None:
        super().__init__(deps=deps)
        self._api_key = api_key
        self._cost_per_search_usd = max(0.0, cost_per_search_usd)
        self._endpoint = endpoint
        if not api_key:
            logger.warning("WebSearch has no TAVILY_API_KEY; searches return no results")

    async def _fetch(self, query: str, limit: int) -> list[Evidence]:
        if not self._api_key:
            return []
        payload = await self._fetch_json(
            "POST",
            self._endpoint,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "query": query,
                "max_results": limit,
                "search_depth": "basic",
                "include_answer": False,
                "include_raw_content": False,
            },
        )
        if payload is None:
            return []
        self.charge(self._cost_per_search_usd)
        try:
            response = _TavilyResponse.model_validate(payload)
        except ValidationError:
            logger.warning("tavily returned an unexpected payload for query=%r", query)
            return []
        items: list[Evidence] = []
        for result in response.results:
            evidence = self._map_result(result)
            if evidence is not None:
                items.append(evidence)
        return items

    def _map_result(self, result: _TavilyResult) -> Evidence | None:
        if not result.url:
            return None
        title = clean_title(result.title) or urlsplit(result.url).netloc or result.url
        try:
            return Evidence(
                source="web",
                url=HttpUrl(result.url),
                title=title,
                snippet=clean_snippet(
                    result.content or result.title, max_chars=self.snippet_max_chars
                ),
                published_at=parse_iso_datetime(result.published_date),
                score=clamp01(result.score) if result.score is not None else None,
            )
        except ValidationError:
            logger.warning("skipping malformed tavily result url=%r", result.url)
            return None
