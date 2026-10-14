"""Public contract of the research-tools module.

The agent pipeline consumes these types: :class:`Evidence` (one sourced
result), :class:`CompanyLead` (company-level only, never a person),
:class:`ResearchTool` (the adapter protocol), and :class:`Cache`.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

SNIPPET_MAX_CHARS = 1500
TITLE_MAX_CHARS = 500
MAX_EVIDENCE_RESULTS = 20
EvidenceSource = Literal["web", "reddit", "hn", "leads"]


class ToolDisabled(RuntimeError):
    """Raised when an adapter that is switched off (for example leads) is used."""


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class Evidence(BaseModel):
    """One piece of real-world evidence, always carrying its source URL."""

    model_config = ConfigDict(frozen=True)

    source: EvidenceSource
    url: HttpUrl
    title: str = Field(min_length=1, max_length=TITLE_MAX_CHARS)
    snippet: str = Field(max_length=SNIPPET_MAX_CHARS)
    published_at: datetime | None = None
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("url")
    @classmethod
    def _reject_url_credentials(cls, value: HttpUrl) -> HttpUrl:
        if value.username or value.password:
            raise ValueError("evidence URLs must not carry credentials")
        return value

    @field_validator("published_at")
    @classmethod
    def _normalize_published_at(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _ensure_utc(value)

    @field_validator("retrieved_at")
    @classmethod
    def _normalize_retrieved_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value)


class CompanyLead(BaseModel):
    """Company-level lead from the lead DB.

    Person-level fields (names, emails, phones) are deliberately absent:
    the module must never store personal contact data.
    """

    name: str = Field(min_length=1)
    domain: str | None = None
    industry: str | None = None
    size_band: str | None = None
    country: str | None = None
    why_fit: str | None = None
    url: HttpUrl | None = None


class Cache(Protocol):
    """Payload cache keyed by ``adapter:normalized query``."""

    async def get(self, key: str) -> list[Evidence] | None: ...

    async def set(self, key: str, items: Sequence[Evidence], *, ttl_seconds: int) -> None: ...


class ResearchTool(Protocol):
    """Uniform interface every adapter implements."""

    name: str

    async def search(self, query: str, *, limit: int = 8) -> list[Evidence]: ...
