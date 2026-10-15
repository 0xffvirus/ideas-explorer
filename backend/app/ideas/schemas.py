"""Pydantic v2 schemas for the idea-core API and service boundaries."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ideas.models import Idea, IdeaStatus, IdeaVerdict

CONTEXT_MAX_CHARS = 10_000
TAGS_MAX = 20
TAG_MAX_CHARS = 50


def _validate_context(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """Reject contexts whose JSON serialization exceeds ``CONTEXT_MAX_CHARS``."""
    if value is None:
        return None
    serialized = json.dumps(value, default=str)
    if len(serialized) > CONTEXT_MAX_CHARS:
        raise ValueError(f"context must serialize to at most {CONTEXT_MAX_CHARS} characters")
    return value


def _validate_tags(value: list[str]) -> list[str]:
    """Trim, cap, and case-insensitively deduplicate tags while preserving order."""
    if len(value) > TAGS_MAX:
        raise ValueError(f"at most {TAGS_MAX} tags are allowed")
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in value:
        tag = raw.strip()
        if not tag:
            raise ValueError("tags must not be empty")
        if len(tag) > TAG_MAX_CHARS:
            raise ValueError(f"tags must be at most {TAG_MAX_CHARS} characters")
        folded = tag.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        normalized.append(tag)
    return normalized


def _validate_optional_tags(value: list[str] | None) -> list[str] | None:
    return None if value is None else _validate_tags(value)


class SearchMode(StrEnum):
    """How a query is matched: full text, embeddings, or both fused."""

    hybrid = "hybrid"
    keyword = "keyword"
    semantic = "semantic"


class SortField(Enum):
    """Ordering for unranked (filter-only) list queries.

    A plain ``Enum`` (not ``StrEnum``) because the ``title`` member would
    otherwise collide with ``str.title``.
    """

    recent = "recent"
    score = "score"
    title = "title"


CursorSort = Literal["recent", "score", "title", "rank"]


class ParsedCursor(BaseModel):
    """Decoded keyset cursor: sort discriminator, serialized sort key, UUID tiebreak."""

    sort: CursorSort
    value: str | None
    idea_id: uuid.UUID


class IdeaCreate(BaseModel):
    """Payload for creating an idea and its first version."""

    raw_input: str = Field(min_length=1, max_length=5000)
    title: str | None = Field(default=None, max_length=80)
    context: dict[str, Any] | None = None
    tags: list[str] = Field(default_factory=list[str])
    analyze: bool = True

    @field_validator("context")
    @classmethod
    def _context_within_cap(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _validate_context(value)

    @field_validator("tags")
    @classmethod
    def _tags_within_caps(cls, value: list[str]) -> list[str]:
        return _validate_tags(value)


class IdeaUpdate(BaseModel):
    """Patch fields accepted by PATCH /ideas/{id}; ``None`` means "leave unchanged"."""

    title: str | None = Field(default=None, max_length=80)
    tags: list[str] | None = None
    pinned: bool | None = None
    archived: bool | None = None

    @field_validator("tags")
    @classmethod
    def _tags_within_caps(cls, value: list[str] | None) -> list[str] | None:
        return _validate_optional_tags(value)


class IdeaVersionCreate(BaseModel):
    """Payload for appending a new version to an existing idea."""

    raw_input: str = Field(min_length=1, max_length=5000)
    context: dict[str, Any] | None = None
    analyze: bool = True

    @field_validator("context")
    @classmethod
    def _context_within_cap(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _validate_context(value)


class IdeaVersionRead(BaseModel):
    """One immutable version of an idea."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number: int
    raw_input: str
    context: dict[str, Any] | None
    brief: dict[str, Any] | None
    created_at: datetime


class IdeaRead(BaseModel):
    """Core idea fields shared by the detail and summary schemas."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: IdeaStatus
    verdict: IdeaVerdict | None
    category: str | None
    overall_score: float | None
    pinned: bool
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class IdeaSummary(IdeaRead):
    """List-row view of an idea."""

    tags: list[str] = Field(default_factory=list[str])
    latest_version_number: int

    @classmethod
    def from_idea(cls, idea: Idea) -> IdeaSummary:
        """Build a summary from a loaded ORM idea (versions and tags must be loaded)."""
        base = IdeaRead.model_validate(idea)
        return cls(
            **base.model_dump(),
            tags=sorted(tag.name for tag in idea.tags),
            latest_version_number=idea.versions[-1].number,
        )


class IdeaDetail(IdeaRead):
    """Full idea view: all versions plus tags and the latest version."""

    latest_version: IdeaVersionRead
    versions: list[IdeaVersionRead] = Field(default_factory=list[IdeaVersionRead])
    tags: list[str] = Field(default_factory=list[str])

    @classmethod
    def from_idea(cls, idea: Idea) -> IdeaDetail:
        """Build a detail view from a loaded ORM idea (versions and tags must be loaded)."""
        versions = [IdeaVersionRead.model_validate(version) for version in idea.versions]
        base = IdeaRead.model_validate(idea)
        return cls(
            **base.model_dump(),
            latest_version=versions[-1],
            versions=versions,
            tags=sorted(tag.name for tag in idea.tags),
        )


class TagCount(BaseModel):
    """A tag name with how many ideas carry it."""

    name: str
    count: int


class SimilarIdea(BaseModel):
    """A neighbouring idea and its cosine distance from the source idea."""

    id: uuid.UUID
    title: str
    distance: float


class IdeaListResponse(BaseModel):
    """One page of ideas plus the cursor for the next page (null on the last page)."""

    items: list[IdeaSummary] = Field(default_factory=list[IdeaSummary])
    next_cursor: str | None = None
