"""Evidence and company-lead models, and the snippet sanitizer.

Score normalization per adapter (applied there, documented here):

* ``web`` (Tavily): the provider's own relevance score, clamped to 0-1.
* ``reddit``: ``min(1, upvotes / (upvotes + 25))``; non-positive scores clamp to 0.
* ``hn``: ``min(1, points / 300)``.
* ``leads``: companies carry no relevance score; ``None``.
"""

from __future__ import annotations

import html
import re
from datetime import UTC, datetime
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field, HttpUrl, field_validator

SNIPPET_MAX_CHARS = 1500
TITLE_MAX_CHARS = 300

_TAG_RE = re.compile(r"<[^>]*>")
_WHITESPACE_RE = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([.,;:!?])")


def sanitize_snippet(raw: str, max_chars: int = SNIPPET_MAX_CHARS) -> str:
    """Strip HTML tags, unescape entities, collapse whitespace, and truncate.

    Tag removal can leave a space before punctuation, which is dropped too.
    Truncation keeps at most ``max_chars`` characters and ends with an ellipsis,
    backing off so it never cuts through a lingering ``&entity;`` sequence.
    """
    text = _TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    text = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    cut = text[: max_chars - 1]
    amp = cut.rfind("&")
    if amp > cut.rfind(";"):
        cut = cut[:amp]
    return cut.rstrip() + "\u2026"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Evidence(BaseModel):
    """One traceable piece of evidence. ``title`` and ``snippet`` are sanitized and capped."""

    source: Literal["web", "reddit", "hn", "leads"]
    url: HttpUrl
    title: str
    snippet: str
    published_at: datetime | None = None
    score: float | None = None
    retrieved_at: datetime = Field(default_factory=_utcnow)

    @field_validator("title")
    @classmethod
    def _sanitize_title(cls, value: str) -> str:
        return sanitize_snippet(value, TITLE_MAX_CHARS)

    @field_validator("snippet")
    @classmethod
    def _sanitize(cls, value: str) -> str:
        return sanitize_snippet(value, SNIPPET_MAX_CHARS)

    @field_validator("score")
    @classmethod
    def _clamp_score(cls, value: float | None) -> float | None:
        if value is None:
            return None
        return min(1.0, max(0.0, value))

    @field_validator("published_at")
    @classmethod
    def _assume_utc(cls, value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=UTC)


class CompanyLead(BaseModel):
    """A company-level lead. Never carries individual contact data."""

    name: str
    domain: str
    industry: str | None = None
    size_band: str | None = None
    country: str | None = None
    why_fit: str
    url: HttpUrl


@runtime_checkable
class EvidenceLike(Protocol):
    """Duck type for anything citable, so claim checks need not import adapters."""

    url: HttpUrl
    title: str
    snippet: str
