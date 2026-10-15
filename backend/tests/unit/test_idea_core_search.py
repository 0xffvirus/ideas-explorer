"""Unit tests for the idea-core search helpers (no database)."""

from __future__ import annotations

import base64
import json
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.dialects import postgresql

from app.ideas.models import IdeaStatus, IdeaVerdict
from app.ideas.schemas import ParsedCursor, SearchMode, SortField
from app.ideas.search import (
    InvalidCursorError,
    SearchFilters,
    build_conditions,
    build_fts_candidates,
    build_list_query,
    build_search_index_upsert,
    build_search_text,
    build_vector_candidates,
    decode_cursor,
    encode_cursor,
    flatten_brief_text,
    paginate_ranked,
    rrf_fuse,
)


def _compiled(stmt: object) -> tuple[str, dict[str, object]]:
    compiled = stmt.compile(dialect=postgresql.dialect())
    return str(compiled), dict(compiled.params)


def _b64(payload: str) -> str:
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


# --------------------------------------------------------------------- RRF


def test_rrf_fuses_two_rankings_and_prefers_overlap() -> None:
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    fused = rrf_fuse([[a, b], [b, c]])
    assert [idea_id for idea_id, _ in fused] == [b, a, c]
    scores = dict(fused)
    assert scores[b] == pytest.approx(1 / 61 + 1 / 62)
    assert scores[a] == pytest.approx(1 / 61)
    assert scores[c] == pytest.approx(1 / 62)


def test_rrf_k_controls_flattening() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    sharp = dict(rrf_fuse([[a, b]], k=10))
    flat = dict(rrf_fuse([[a, b]], k=60))
    assert sharp[a] == pytest.approx(1 / 11)
    assert sharp[b] == pytest.approx(1 / 12)
    assert flat[a] == pytest.approx(1 / 61)
    assert flat[b] == pytest.approx(1 / 62)
    assert (sharp[a] - sharp[b]) > (flat[a] - flat[b])


def test_rrf_empty_input() -> None:
    assert rrf_fuse([]) == []
    assert rrf_fuse([[]]) == []


def test_rrf_ties_break_by_id() -> None:
    low, high = uuid.UUID(int=1), uuid.UUID(int=2)
    fused = rrf_fuse([[low, high], [high, low]])
    assert fused[0][1] == pytest.approx(1 / 61 + 1 / 62)
    assert fused[1][1] == pytest.approx(1 / 61 + 1 / 62)
    assert [idea_id for idea_id, _ in fused] == [low, high]


# ------------------------------------------------------------------ cursors


@pytest.mark.parametrize("sort", ["recent", "score", "title", "rank"])
def test_cursor_round_trip(sort: str) -> None:
    idea_id = uuid.uuid4()
    parsed = decode_cursor(encode_cursor(sort, "payload-value", idea_id))
    assert parsed == ParsedCursor(sort=sort, value="payload-value", idea_id=idea_id)


def test_cursor_round_trip_null_value() -> None:
    idea_id = uuid.uuid4()
    parsed = decode_cursor(encode_cursor("score", None, idea_id))
    assert parsed.value is None
    assert parsed.idea_id == idea_id


def test_cursor_is_urlsafe_and_padded_on_decode() -> None:
    raw = encode_cursor("recent", "2026-01-02T03:04:05+00:00", uuid.uuid4())
    assert "=" not in raw
    assert "+" not in raw and "/" not in raw
    assert decode_cursor(raw + "==").sort == "recent"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "!!!not-base64!!!",
        _b64("[]"),
        _b64('"just-a-string"'),
        _b64(json.dumps({"s": "bogus", "v": None, "i": str(uuid.uuid4())})),
        _b64(json.dumps({"s": "recent", "v": None, "i": "not-a-uuid"})),
        _b64(json.dumps({"s": "recent", "v": None})),
        _b64(json.dumps({"s": "recent", "v": 12, "i": str(uuid.uuid4())})),
    ],
)
def test_invalid_cursors_raise(raw: str) -> None:
    with pytest.raises(InvalidCursorError):
        decode_cursor(raw)


def test_paginate_ranked_walks_pages_without_duplicates() -> None:
    fused = [(uuid.UUID(int=i), 1.0 / (60 + i)) for i in range(5)]
    page, cursor = paginate_ranked(fused, cursor=None, limit=2)
    assert [idea_id for idea_id, _ in page] == [item[0] for item in fused[:2]]
    assert cursor is not None
    page2, cursor2 = paginate_ranked(fused, cursor=decode_cursor(cursor), limit=2)
    assert [idea_id for idea_id, _ in page2] == [item[0] for item in fused[2:4]]
    assert cursor2 is not None
    page3, cursor3 = paginate_ranked(fused, cursor=decode_cursor(cursor2), limit=2)
    assert len(page3) == 1
    assert cursor3 is None


def test_paginate_ranked_rejects_other_sort_cursor() -> None:
    cursor = decode_cursor(encode_cursor("recent", "x", uuid.uuid4()))
    with pytest.raises(InvalidCursorError):
        paginate_ranked([], cursor=cursor, limit=5)


# ------------------------------------------------------------------- text


def test_flatten_brief_text_collects_nested_values() -> None:
    brief = {
        "problem": "Busy pet owners forget walks",
        "competition": {"names": ["PawTime", 3, True, None]},
        "empty": {},
    }
    text = flatten_brief_text(brief)
    for fragment in ["problem", "Busy pet owners forget walks", "names", "PawTime", "3", "true"]:
        assert fragment in text


def test_flatten_brief_text_handles_none() -> None:
    assert flatten_brief_text(None) == ""


def test_build_search_text_joins_title_input_and_brief() -> None:
    text = build_search_text("Dog walking", "app for pets", {"audience": "pet owners"})
    assert text == "Dog walking app for pets audience pet owners"


# ----------------------------------------------------------------- filters


def test_conditions_cover_every_filter() -> None:
    filters = SearchFilters(
        status=IdeaStatus.done,
        verdict=IdeaVerdict.pursue,
        category="b2b_saas",
        tag="ai",
        pinned=False,
        archived=True,
        score_min=10.0,
        score_max=90.0,
    )
    sql, params = _compiled(
        build_list_query(filters=filters, sort=SortField.score, cursor=None, limit=30)
    )
    assert "ideas.archived_at IS NOT NULL" in sql
    assert "ideas.status =" in sql
    assert "ideas.verdict =" in sql
    assert "ideas.category =" in sql
    assert "ideas.pinned IS false" in sql
    assert "ideas.overall_score >=" in sql
    assert "ideas.overall_score <=" in sql
    assert "EXISTS (SELECT" in sql
    assert "JOIN tags" in sql
    assert "ORDER BY ideas.overall_score DESC NULLS LAST" in sql
    assert params["category_1"] == "b2b_saas"
    assert params["name_1"] == "ai"
    assert params["overall_score_1"] == 10.0
    assert params["overall_score_2"] == 90.0
    assert params["param_2"] == 31


def test_conditions_default_hides_archived() -> None:
    sql, _ = _compiled(
        build_list_query(filters=SearchFilters(), sort=SortField.recent, cursor=None, limit=30)
    )
    assert "ideas.archived_at IS NULL" in sql


def test_build_conditions_returns_no_tag_clause_without_tag() -> None:
    sql = " ".join(str(condition) for condition in build_conditions(SearchFilters()))
    assert "EXISTS" not in sql


# ------------------------------------------------------------ ranked SQL


def test_fts_candidates_use_english_websearch_and_ts_rank() -> None:
    stmt = build_fts_candidates("pets", build_conditions(SearchFilters()))
    sql, params = _compiled(stmt)
    assert "websearch_to_tsquery('english'" in sql
    assert "ts_rank(idea_search.tsv" in sql
    assert "idea_search.tsv @@" in sql
    assert "ORDER BY ts_rank(" in sql
    assert "DESC, idea_search.idea_id ASC" in sql
    assert "ideas.archived_at IS NULL" in sql
    assert params["param_1"] == "pets"


def test_vector_candidates_use_cosine_distance() -> None:
    stmt = build_vector_candidates(
        [0.25, 0.5], build_conditions(SearchFilters(status=IdeaStatus.queued))
    )
    sql, params = _compiled(stmt)
    assert "idea_search.embedding <=>" in sql
    assert "idea_search.embedding IS NOT NULL" in sql
    assert "ORDER BY idea_search.embedding <=>" in sql
    assert "idea_search.idea_id ASC" in sql
    assert params["embedding_1"] == [0.25, 0.5]


# -------------------------------------------------------------- list SQL


def test_recent_cursor_builds_keyset_predicate() -> None:
    idea_id = uuid.uuid4()
    cursor = decode_cursor(encode_cursor("recent", "2026-02-03T04:05:06+00:00", idea_id))
    sql, params = _compiled(
        build_list_query(filters=SearchFilters(), sort=SortField.recent, cursor=cursor, limit=30)
    )
    assert "ideas.created_at <" in sql
    assert "ideas.created_at =" in sql
    assert "ideas.id <" in sql
    assert "ORDER BY ideas.created_at DESC, ideas.id DESC" in sql
    assert params["id_1"] == idea_id
    assert params["created_at_1"] == datetime(2026, 2, 3, 4, 5, 6, tzinfo=UTC)


def test_score_cursor_includes_null_scores_after_non_null() -> None:
    cursor = decode_cursor(encode_cursor("score", "85.5", uuid.uuid4()))
    sql, params = _compiled(
        build_list_query(filters=SearchFilters(), sort=SortField.score, cursor=cursor, limit=5)
    )
    assert "ideas.overall_score <" in sql
    assert "ideas.overall_score IS NULL" in sql
    assert params["overall_score_1"] == 85.5


def test_score_cursor_null_position_only_returns_null_scores() -> None:
    cursor = decode_cursor(encode_cursor("score", None, uuid.uuid4()))
    sql, _ = _compiled(
        build_list_query(filters=SearchFilters(), sort=SortField.score, cursor=cursor, limit=5)
    )
    assert "ideas.overall_score IS NULL AND ideas.id <" in sql
    assert "ideas.overall_score <" not in sql


def test_title_sort_uses_lowercase_ordering() -> None:
    sql, _ = _compiled(
        build_list_query(filters=SearchFilters(), sort=SortField.title, cursor=None, limit=10)
    )
    assert "ORDER BY lower(ideas.title) ASC, ideas.id ASC" in sql


def test_cursor_sort_mismatch_raises() -> None:
    cursor = decode_cursor(encode_cursor("title", "abc", uuid.uuid4()))
    with pytest.raises(InvalidCursorError):
        build_list_query(filters=SearchFilters(), sort=SortField.recent, cursor=cursor, limit=5)


def test_bad_cursor_value_raises() -> None:
    cursor = decode_cursor(encode_cursor("recent", "not-a-date", uuid.uuid4()))
    with pytest.raises(InvalidCursorError):
        build_list_query(filters=SearchFilters(), sort=SortField.recent, cursor=cursor, limit=5)


# ------------------------------------------------------------- index write


def test_search_index_upsert_includes_embedding_when_present() -> None:
    stmt = build_search_index_upsert(idea_id=uuid.uuid4(), text="dog walking", embedding=[0.5, 0.5])
    sql, params = _compiled(stmt)
    assert "INSERT INTO idea_search" in sql
    assert "to_tsvector('english'" in sql
    assert "ON CONFLICT (idea_id) DO UPDATE" in sql
    assert "embedding = " in sql
    assert params["param_1"] == "dog walking"


def test_search_index_upsert_omits_embedding_when_missing() -> None:
    stmt = build_search_index_upsert(idea_id=uuid.uuid4(), text="dog walking", embedding=None)
    sql, _params = _compiled(stmt)
    assert "embedding" not in sql
    assert "to_tsvector('english'" in sql


def test_search_modes_are_exported_values() -> None:
    assert SearchMode.hybrid.value == "hybrid"
    assert SortField.title.value == "title"
