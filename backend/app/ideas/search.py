"""Search helpers for idea-core: RRF fusion, tsvector text, cursors, SQL builders.

Cursor design
-------------
Cursors are opaque base64url-encoded JSON objects ``{"s", "v", "i"}``: ``s`` is
the sort discriminator (``recent``, ``score``, ``title`` or ``rank``), ``v`` is
the serialized sort key and ``i`` is the idea UUID tiebreak.

* ``recent`` paginates on ``(created_at DESC, id DESC)``. This is a true keyset
  on immutable columns: an idea inserted while the client pages is newer than
  the cursor and therefore can never displace, duplicate or skip a row that the
  client has not seen yet.
* ``score`` paginates on ``(overall_score DESC NULLS LAST, id DESC)``.
* ``title`` paginates on ``(lower(title) ASC, id ASC)``.
* ``rank`` (keyword/hybrid/semantic with a query) carries the Reciprocal Rank
  Fusion score plus the idea id. The fused list is recomputed deterministically
  from the candidate rankings on every request; inserting new ideas can only
  push existing rows *down* in each ranking (never up), so rows after the
  cursor are never skipped. In the pathological case where many new rows push a
  pre-cursor row's score below the cursor score it can resurface on a later
  page; the API documents this as "rare duplicate, never a skip".

All comparisons are strict with the UUID tiebreak, so a row equal to the
cursor key is never returned twice.
"""

from __future__ import annotations

import base64
import binascii
import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from sqlalchemy import (
    ColumnElement,
    and_,
    func,
    literal,
    literal_column,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import Insert as PgInsert
from sqlalchemy.sql import Select

from app.ideas.models import Idea, IdeaSearch, IdeaStatus, IdeaTag, IdeaVerdict, Tag
from app.ideas.schemas import CursorSort, ParsedCursor, SortField

RRF_K = 60
MAX_LIMIT = 100

_TS_CONFIG = cast("ColumnElement[str]", literal_column("'english'"))
_CURSOR_SORTS: tuple[str, ...] = ("recent", "score", "title", "rank")


class InvalidCursorError(ValueError):
    """Raised when a cursor is malformed, stale, or does not match the requested sort."""


def encode_cursor(sort: str, value: str | None, idea_id: uuid.UUID) -> str:
    """Encode a keyset position as an opaque base64url cursor."""
    payload = json.dumps(
        {"s": sort, "v": value, "i": str(idea_id)},
        separators=(",", ":"),
        sort_keys=True,
    )
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def decode_cursor(raw: str) -> ParsedCursor:
    """Decode a cursor produced by :func:`encode_cursor`; raises :class:`InvalidCursorError`."""
    if not raw:
        raise InvalidCursorError("cursor is empty")
    padded = raw + "=" * (-len(raw) % 4)
    try:
        data = base64.urlsafe_b64decode(padded.encode("ascii"))
        payload = json.loads(data)
    except (binascii.Error, UnicodeError, ValueError) as exc:
        raise InvalidCursorError("cursor is not valid base64url JSON") from exc
    if not isinstance(payload, dict):
        raise InvalidCursorError("cursor payload must be a JSON object")
    fields = cast("Mapping[str, object]", payload)
    sort = fields.get("s")
    value = fields.get("v")
    raw_id = fields.get("i")
    if sort not in _CURSOR_SORTS:
        raise InvalidCursorError(f"cursor sort must be one of {_CURSOR_SORTS}, got {sort!r}")
    if value is not None and not isinstance(value, str):
        raise InvalidCursorError("cursor value must be a string or null")
    if not isinstance(raw_id, str):
        raise InvalidCursorError("cursor idea id is missing")
    try:
        idea_id = uuid.UUID(raw_id)
    except ValueError as exc:
        raise InvalidCursorError("cursor idea id is not a UUID") from exc
    return ParsedCursor(sort=cast("CursorSort", sort), value=value, idea_id=idea_id)


def rrf_fuse(
    ranked_lists: Sequence[Sequence[uuid.UUID]],
    *,
    k: int = RRF_K,
) -> list[tuple[uuid.UUID, float]]:
    """Fuse ranked id lists with Reciprocal Rank Fusion, highest score first.

    Each list contributes ``1 / (k + position)`` per id (positions start at 1).
    Ties are broken by ascending id so the result is fully deterministic.
    """
    scores: dict[uuid.UUID, float] = {}
    for ranked in ranked_lists:
        for position, idea_id in enumerate(ranked, start=1):
            scores[idea_id] = scores.get(idea_id, 0.0) + 1.0 / (k + position)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def paginate_ranked(
    fused: Sequence[tuple[uuid.UUID, float]],
    *,
    cursor: ParsedCursor | None,
    limit: int,
) -> tuple[list[tuple[uuid.UUID, float]], str | None]:
    """Apply a rank cursor to a fused list; returns ``(page, next_cursor)``.

    The fused list is ordered by ``(score DESC, id ASC)``; items after the
    cursor therefore satisfy ``score < cursor.score`` or
    ``(score == cursor.score and id > cursor.id)``.
    """
    remaining = list(fused)
    if cursor is not None:
        if cursor.sort != "rank":
            raise InvalidCursorError(f"cursor is for sort={cursor.sort!r}, not 'rank'")
        if cursor.value is None:
            raise InvalidCursorError("rank cursor is missing its score")
        try:
            score = float(cursor.value)
        except ValueError as exc:
            raise InvalidCursorError("rank cursor score is not a number") from exc
        remaining = [
            item
            for item in remaining
            if item[1] < score or (item[1] == score and item[0] > cursor.idea_id)
        ]
    page = remaining[:limit]
    next_cursor: str | None = None
    if len(remaining) > limit and page:
        next_cursor = encode_cursor("rank", repr(page[-1][1]), page[-1][0])
    return page, next_cursor


def flatten_brief_text(brief: Mapping[str, Any] | None) -> str:
    """Flatten nested brief JSON into one searchable text blob."""
    parts: list[str] = []
    _collect_text(brief, parts)
    return " ".join(parts)


def _collect_text(value: object, parts: list[str]) -> None:
    if value is None:
        return
    if isinstance(value, str):
        text = value.strip()
        if text:
            parts.append(text)
    elif isinstance(value, bool):
        parts.append("true" if value else "false")
    elif isinstance(value, (int, float)):
        parts.append(str(value))
    elif isinstance(value, Mapping):
        for key, item in cast("Mapping[object, object]", value).items():
            parts.append(str(key))
            _collect_text(item, parts)
    elif isinstance(value, Sequence):
        for item in cast("Sequence[object]", value):
            _collect_text(item, parts)


def build_search_text(title: str, raw_input: str, brief: Mapping[str, Any] | None) -> str:
    """Build the indexed text: title, latest raw input, and flattened brief."""
    return " ".join(part for part in (title, raw_input, flatten_brief_text(brief)) if part)


def tsvector_expr(text: str) -> ColumnElement[Any]:
    """SQL ``to_tsvector('english', :text)`` expression."""
    return func.to_tsvector(_TS_CONFIG, literal(text))


def _tsquery_expr(q: str) -> ColumnElement[Any]:
    return func.websearch_to_tsquery(_TS_CONFIG, literal(q))


@dataclass(frozen=True)
class SearchFilters:
    """Filters shared by ranked search and the plain list query."""

    status: IdeaStatus | None = None
    verdict: IdeaVerdict | None = None
    category: str | None = None
    tag: str | None = None
    pinned: bool | None = None
    archived: bool = False
    score_min: float | None = None
    score_max: float | None = None


def build_conditions(filters: SearchFilters) -> list[ColumnElement[bool]]:
    """Translate :class:`SearchFilters` into SQL conditions on ``ideas``."""
    conditions: list[ColumnElement[bool]] = []
    if filters.archived:
        conditions.append(Idea.archived_at.is_not(None))
    else:
        conditions.append(Idea.archived_at.is_(None))
    if filters.status is not None:
        conditions.append(Idea.status == filters.status)
    if filters.verdict is not None:
        conditions.append(Idea.verdict == filters.verdict)
    if filters.category is not None:
        conditions.append(Idea.category == filters.category)
    if filters.pinned is not None:
        conditions.append(Idea.pinned.is_(filters.pinned))
    if filters.score_min is not None:
        conditions.append(Idea.overall_score >= filters.score_min)
    if filters.score_max is not None:
        conditions.append(Idea.overall_score <= filters.score_max)
    if filters.tag is not None:
        conditions.append(
            select(literal(1))
            .select_from(IdeaTag)
            .join(Tag, Tag.id == IdeaTag.tag_id)
            .where(IdeaTag.idea_id == Idea.id, Tag.name == filters.tag)
            .exists()
        )
    return conditions


def build_fts_candidates(
    q: str, conditions: Sequence[ColumnElement[bool]]
) -> Select[uuid.UUID, float]:
    """Candidate ranking by full-text rank: ``ts_rank`` descending."""
    tsquery = _tsquery_expr(q)
    rank = func.ts_rank(IdeaSearch.tsv, tsquery)
    return (
        select(IdeaSearch.idea_id, rank.label("rank"))
        .join(Idea, Idea.id == IdeaSearch.idea_id)
        .where(*conditions, IdeaSearch.tsv.op("@@")(tsquery))
        .order_by(rank.desc(), IdeaSearch.idea_id.asc())
    )


def build_vector_candidates(
    query_embedding: Sequence[float], conditions: Sequence[ColumnElement[bool]]
) -> Select[uuid.UUID, float]:
    """Candidate ranking by embedding cosine distance ascending."""
    distance = IdeaSearch.embedding.cosine_distance(query_embedding)
    return (
        select(IdeaSearch.idea_id, distance.label("distance"))
        .join(Idea, Idea.id == IdeaSearch.idea_id)
        .where(*conditions, IdeaSearch.embedding.is_not(None))
        .order_by(distance, IdeaSearch.idea_id.asc())
    )


def _cursor_datetime(cursor: ParsedCursor) -> datetime:
    if cursor.value is None:
        raise InvalidCursorError("recent cursor is missing its timestamp")
    try:
        return datetime.fromisoformat(cursor.value)
    except ValueError as exc:
        raise InvalidCursorError("recent cursor timestamp is not ISO-8601") from exc


def _cursor_float(cursor: ParsedCursor, label: str) -> float | None:
    if cursor.value is None:
        return None
    try:
        return float(cursor.value)
    except ValueError as exc:
        raise InvalidCursorError(f"{label} cursor value is not a number") from exc


def _list_cursor_conditions(sort: SortField, cursor: ParsedCursor) -> list[ColumnElement[bool]]:
    if cursor.sort != sort.value:
        raise InvalidCursorError(f"cursor is for sort={cursor.sort!r}, not {sort.value!r}")
    match sort:
        case SortField.recent:
            created_at = _cursor_datetime(cursor)
            return [
                or_(
                    Idea.created_at < created_at,
                    and_(Idea.created_at == created_at, Idea.id < cursor.idea_id),
                )
            ]
        case SortField.score:
            score = _cursor_float(cursor, "score")
            if score is None:
                return [and_(Idea.overall_score.is_(None), Idea.id < cursor.idea_id)]
            return [
                or_(
                    Idea.overall_score < score,
                    and_(Idea.overall_score == score, Idea.id < cursor.idea_id),
                    Idea.overall_score.is_(None),
                )
            ]
        case SortField.title:
            if cursor.value is None:
                raise InvalidCursorError("title cursor is missing its title")
            value = cursor.value.lower()
            return [
                or_(
                    func.lower(Idea.title) > value,
                    and_(func.lower(Idea.title) == value, Idea.id > cursor.idea_id),
                )
            ]


def build_list_query(
    *,
    filters: SearchFilters,
    sort: SortField,
    cursor: ParsedCursor | None,
    limit: int,
) -> Select[Idea]:
    """Build the unranked filtered list query with keyset pagination."""
    conditions = build_conditions(filters)
    if cursor is not None:
        conditions.extend(_list_cursor_conditions(sort, cursor))
    stmt = select(Idea).where(*conditions).limit(limit + 1)
    match sort:
        case SortField.recent:
            stmt = stmt.order_by(Idea.created_at.desc(), Idea.id.desc())
        case SortField.score:
            stmt = stmt.order_by(Idea.overall_score.desc().nulls_last(), Idea.id.desc())
        case SortField.title:
            stmt = stmt.order_by(func.lower(Idea.title).asc(), Idea.id.asc())
    return stmt


def build_search_index_upsert(
    *,
    idea_id: uuid.UUID,
    text: str,
    embedding: Sequence[float] | None,
) -> PgInsert:
    """Upsert the one-row-per-idea search index.

    ``tsv`` is always rebuilt from ``text``; ``embedding`` is only written when
    one was computed, so a failed embedding never wipes a working vector.
    """
    values: dict[str, object] = {"idea_id": idea_id, "tsv": tsvector_expr(text)}
    assignments: dict[str, object] = {"tsv": tsvector_expr(text)}
    if embedding is not None:
        values["embedding"] = embedding
        assignments["embedding"] = embedding
    return (
        PgInsert(IdeaSearch)
        .values(**values)
        .on_conflict_do_update(index_elements=["idea_id"], set_=assignments)
    )
