"""Reddit official API provider (OAuth2 client credentials only)."""

from __future__ import annotations

import time
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast

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

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
SEARCH_URL = "https://oauth.reddit.com/search"
UPVOTE_HALF_LIFE = 25.0
TOKEN_EXPIRY_SKEW_SECONDS = 60.0


def normalize_upvotes(upvotes: float) -> float:
    """Map Reddit upvotes to 0-1: ``min(1, upvotes / (upvotes + 25))``, 0 when <= 0."""
    if upvotes <= 0:
        return 0.0
    return min(1.0, upvotes / (upvotes + UPVOTE_HALF_LIFE))


def _from_epoch(value: object) -> datetime | None:
    seconds = as_float(value)
    if seconds is None:
        return None
    try:
        return datetime.fromtimestamp(seconds, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


class RedditProvider:
    """Reddit search via the official OAuth API; the token is reused until expiry."""

    name = "reddit"

    def __init__(
        self,
        settings: Settings,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        meter: CostMeter | None = None,
        limiter: TokenBucketRateLimiter | None = None,
    ) -> None:
        self._settings = settings
        self._client_id = settings.reddit_client_id if client_id is None else client_id
        self._client_secret = (
            settings.reddit_client_secret if client_secret is None else client_secret
        )
        self._http = http_client if http_client is not None else httpx.AsyncClient()
        self._owns_http = http_client is None
        self._meter = meter
        self._limiter = (
            limiter
            if limiter is not None
            else TokenBucketRateLimiter(settings.reddit_rate_limit_per_minute)
        )
        self._token: str | None = None
        self._token_expires_at = 0.0

    async def aclose(self) -> None:
        """Close the HTTP client when this provider created it."""
        if self._owns_http:
            await self._http.aclose()

    async def search(self, query: str, limit: int = 8) -> list[Evidence]:
        """Search Reddit; raises ResearchUnavailable without OAuth credentials."""
        if not self._client_id or not self._client_secret:
            raise ResearchUnavailable(
                "REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are not configured"
            )
        await self._limiter.acquire()
        token = await self._access_token()
        if token is None:
            return []
        response = await request_with_retries(
            self._http,
            "GET",
            SEARCH_URL,
            max_retries=self._settings.research_max_retries,
            request_timeout=self._settings.research_timeout_seconds,
            headers={
                "Authorization": f"bearer {token}",
                "User-Agent": self._settings.reddit_user_agent,
            },
            params={"q": query, "limit": limit, "sort": "relevance", "raw_json": 1},
        )
        if response is not None and response.status_code in (401, 403):
            logger.warning(
                "reddit rejected the cached token with HTTP %s; refetching",
                response.status_code,
            )
            self._token = None
            self._token_expires_at = 0.0
            await self._limiter.acquire()
            token = await self._access_token()
            if token is None:
                return []
            response = await request_with_retries(
                self._http,
                "GET",
                SEARCH_URL,
                max_retries=self._settings.research_max_retries,
                request_timeout=self._settings.research_timeout_seconds,
                headers={
                    "Authorization": f"bearer {token}",
                    "User-Agent": self._settings.reddit_user_agent,
                },
                params={"q": query, "limit": limit, "sort": "relevance", "raw_json": 1},
            )
        if response is None:
            return []
        if response.status_code != 200:
            logger.warning("reddit returned HTTP %s; returning no results", response.status_code)
            return []
        return self._map(response)

    async def _access_token(self) -> str | None:
        now = time.monotonic()
        if self._token is not None and now < self._token_expires_at:
            return self._token
        response = await request_with_retries(
            self._http,
            "POST",
            TOKEN_URL,
            max_retries=self._settings.research_max_retries,
            request_timeout=self._settings.research_timeout_seconds,
            headers={"User-Agent": self._settings.reddit_user_agent},
            data={"grant_type": "client_credentials"},
            auth=(self._client_id, self._client_secret),
        )
        if response is None or response.status_code != 200:
            logger.warning("reddit token request failed; returning no results")
            return None
        data = json_object(response)
        token = as_str(data.get("access_token") if data is not None else None)
        if not token:
            logger.warning("reddit token response is missing access_token")
            return None
        expires_in = as_float(data.get("expires_in") if data is not None else None)
        lifetime = expires_in if expires_in is not None else 3600.0
        self._token = token
        self._token_expires_at = time.monotonic() + max(0.0, lifetime - TOKEN_EXPIRY_SKEW_SECONDS)
        return token

    def _map(self, response: httpx.Response) -> list[Evidence]:
        data = json_object(response)
        listing_data = data.get("data") if data is not None else None
        if not isinstance(listing_data, dict):
            logger.warning("reddit response is missing data.children")
            return []
        listing = cast("dict[str, Any]", listing_data)
        children = listing.get("children")
        if not isinstance(children, list):
            logger.warning("reddit response is missing data.children")
            return []
        items: list[Evidence] = []
        for child in cast("list[object]", children):
            if not isinstance(child, dict):
                continue
            entry = cast("dict[str, Any]", child).get("data")
            if not isinstance(entry, dict):
                continue
            try:
                items.append(self._to_evidence(cast("dict[str, Any]", entry)))
            except (ValueError, KeyError) as exc:
                logger.warning("skipping malformed reddit result: %s", exc)
        return items

    def _to_evidence(self, entry: Mapping[str, object]) -> Evidence:
        title = as_str(entry.get("title"))
        selftext = as_str(entry.get("selftext"))
        permalink = as_str(entry.get("permalink"))
        url = f"https://www.reddit.com{permalink}" if permalink else "https://www.reddit.com"
        upvotes = as_float(entry.get("score"))
        return Evidence(
            source="reddit",
            url=HttpUrl(url),
            title=title,
            snippet=sanitize_snippet(
                selftext.strip() or title, self._settings.research_snippet_max_chars
            ),
            published_at=_from_epoch(entry.get("created_utc")),
            score=None if upvotes is None else normalize_upvotes(upvotes),
        )
