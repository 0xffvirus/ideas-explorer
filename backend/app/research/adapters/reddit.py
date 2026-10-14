"""Reddit signals adapter: posts and comments that express the pain."""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Callable
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, ValidationError

from app.obs import get_logger
from app.research.adapters.base import AdapterDeps, HttpAdapter
from app.research.contract import Evidence
from app.research.text import clean_snippet, clean_title, parse_epoch_datetime, saturate_score

logger = get_logger(__name__)

REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
REDDIT_API_BASE = "https://oauth.reddit.com"
SCORE_HALF_POINT = 50.0
TOKEN_REFRESH_MARGIN_SECONDS = 30.0
COMMENT_TITLE_FALLBACK_CHARS = 80
POST_PATH_PATTERN = re.compile(r"^/r/[^/]+/comments/(?P<post_id>[A-Za-z0-9]+)")


def _is_reddit_host(netloc: str) -> bool:
    host = netloc.rsplit("@", 1)[-1].split(":", 1)[0].lower().rstrip(".")
    return host == "reddit.com" or host.endswith(".reddit.com")


class _RedditToken(BaseModel):
    model_config = ConfigDict(extra="ignore")

    access_token: str
    expires_in: float = 3600.0


class _RedditItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = ""
    body: str = ""
    permalink: str = ""
    selftext: str = ""
    link_title: str = ""
    subreddit: str = ""
    created_utc: float | None = None
    score: float | None = None
    ups: float | None = None


class _RedditChild(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: str = ""
    data: _RedditItem


class _RedditListing(BaseModel):
    model_config = ConfigDict(extra="ignore")

    children: list[_RedditChild] = Field(default_factory=list[_RedditChild])


class _RedditListingEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    data: _RedditListing


_comments_payload_adapter: TypeAdapter[list[_RedditListingEnvelope]] = TypeAdapter(
    list[_RedditListingEnvelope]
)


class RedditSignals(HttpAdapter):
    """Reddit posts via official search and comments via ``comments_for``."""

    name = "reddit"

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        user_agent: str,
        deps: AdapterDeps,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(deps=deps)
        self._client_id = client_id
        self._client_secret = client_secret
        self._user_agent = user_agent
        self._clock = clock
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()
        if not self.configured:
            logger.warning("RedditSignals has no client credentials; searches return no results")

    @property
    def configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    async def _fetch(self, query: str, limit: int) -> list[Evidence]:
        if not self.configured:
            return []
        token = await self._ensure_token()
        if token is None:
            return []
        payload = await self._fetch_json(
            "GET",
            f"{REDDIT_API_BASE}/search",
            headers={"Authorization": f"bearer {token}", "User-Agent": self._user_agent},
            params={
                "q": query,
                "limit": str(limit),
                "sort": "relevance",
                "type": "link",
                "raw_json": "1",
            },
        )
        if payload is None:
            return []
        try:
            listing = _RedditListingEnvelope.model_validate(payload)
        except ValidationError:
            logger.warning("reddit returned an unexpected payload for query=%r", query)
            return []
        items: list[Evidence] = []
        for child in listing.data.children:
            evidence = self._map_child(child)
            if evidence is not None:
                items.append(evidence)
        return items

    async def comments_for(self, post: str | Evidence, *, limit: int = 5) -> list[Evidence]:
        """Top comments of one post, via the official ``/comments/{id}`` endpoint."""
        try:
            return await self._comments(post, limit=limit)
        except Exception:
            logger.exception("reddit comments fetch failed post=%r", post)
            return []

    async def _comments(self, post: str | Evidence, *, limit: int) -> list[Evidence]:
        url = str(post.url) if isinstance(post, Evidence) else post
        parsed = urlsplit(url)
        if not _is_reddit_host(parsed.netloc):
            return []
        match = POST_PATH_PATTERN.match(parsed.path)
        if match is None or limit <= 0 or not self.configured:
            return []
        post_id = match.group("post_id")
        effective_limit = min(limit, self.max_results)
        key = f"{self.name}:comments:{post_id}"
        cached = await self._cache.get(key)
        if cached is not None:
            return cached[:effective_limit]
        token = await self._ensure_token()
        if token is None:
            return []
        payload = await self._fetch_json(
            "GET",
            f"{REDDIT_API_BASE}/comments/{post_id}",
            headers={"Authorization": f"bearer {token}", "User-Agent": self._user_agent},
            params={"limit": str(effective_limit), "sort": "top", "raw_json": "1"},
        )
        if payload is None:
            return []
        try:
            listings = _comments_payload_adapter.validate_python(payload)
        except ValidationError:
            logger.warning("reddit returned an unexpected comments payload post=%r", post_id)
            return []
        items: list[Evidence] = []
        if len(listings) >= 2:
            for child in listings[1].data.children:
                evidence = self._map_comment(child)
                if evidence is not None:
                    items.append(evidence)
        if items:
            await self._cache.set(key, items, ttl_seconds=self.ttl_seconds)
        return items[:effective_limit]

    async def _ensure_token(self) -> str | None:
        async with self._token_lock:
            if self._token is not None and self._clock() < self._token_expires_at:
                return self._token
            payload = await self._fetch_json(
                "POST",
                REDDIT_TOKEN_URL,
                headers={"User-Agent": self._user_agent},
                data={"grant_type": "client_credentials"},
                auth=(self._client_id, self._client_secret),
            )
            if payload is None:
                self._token = None
                return None
            try:
                token = _RedditToken.model_validate(payload)
            except ValidationError:
                logger.warning("reddit token endpoint returned an unexpected payload")
                return None
            self._token = token.access_token
            self._token_expires_at = self._clock() + token.expires_in - TOKEN_REFRESH_MARGIN_SECONDS
            return self._token

    def _map_child(self, child: _RedditChild) -> Evidence | None:
        item = child.data
        if not item.permalink.startswith("/"):
            return None
        body = item.selftext.strip()
        title = clean_title(item.title)
        if not (body or title):
            return None
        fallback = clean_snippet(body, max_chars=COMMENT_TITLE_FALLBACK_CHARS)
        if not fallback:
            fallback = (
                f"Reddit discussion in r/{item.subreddit}"
                if item.subreddit
                else "Reddit discussion"
            )
        votes = item.score if item.score is not None else (item.ups or 0.0)
        try:
            return Evidence(
                source="reddit",
                url=HttpUrl(f"https://www.reddit.com{item.permalink}"),
                title=clean_title(title or fallback),
                snippet=clean_snippet(body or item.title, max_chars=self.snippet_max_chars),
                published_at=parse_epoch_datetime(item.created_utc),
                score=saturate_score(votes, half_point=SCORE_HALF_POINT),
            )
        except ValidationError:
            logger.warning("skipping malformed reddit item permalink=%r", item.permalink)
            return None

    def _map_comment(self, child: _RedditChild) -> Evidence | None:
        item = child.data
        body = item.body.strip()
        if not item.permalink.startswith("/") or not body:
            return None
        title = clean_title(item.link_title) or clean_snippet(
            body, max_chars=COMMENT_TITLE_FALLBACK_CHARS
        )
        votes = item.score if item.score is not None else (item.ups or 0.0)
        try:
            return Evidence(
                source="reddit",
                url=HttpUrl(f"https://www.reddit.com{item.permalink}"),
                title=title,
                snippet=clean_snippet(body, max_chars=self.snippet_max_chars),
                published_at=parse_epoch_datetime(item.created_utc),
                score=saturate_score(votes, half_point=SCORE_HALF_POINT),
            )
        except ValidationError:
            logger.warning("skipping malformed reddit comment permalink=%r", item.permalink)
            return None
