"""Unit tests for idea-core schemas, the title placeholder, and the public surface."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

import app.ideas as ideas
from app.ideas import (
    Idea,
    IdeaCreate,
    IdeaDetail,
    IdeaStatus,
    IdeaSummary,
    IdeaUpdate,
    IdeaVerdict,
    IdeaVersion,
    IdeaVersionCreate,
    Tag,
)
from app.ideas.schemas import CONTEXT_MAX_CHARS, TAG_MAX_CHARS, TAGS_MAX
from app.ideas.service import placeholder_title

_EXPECTED_SURFACE = {
    "IdeaService",
    "AnalysisEnqueuer",
    "Idea",
    "IdeaVersion",
    "Tag",
    "IdeaStatus",
    "IdeaVerdict",
    "Embedder",
    "OpenAIEmbedder",
    "EmbeddingError",
    "IdeaNotFound",
    "IdeaCreate",
    "IdeaUpdate",
    "IdeaVersionCreate",
    "IdeaRead",
    "IdeaDetail",
    "IdeaVersionRead",
    "IdeaSummary",
    "IdeaListResponse",
    "TagCount",
    "SearchMode",
    "SimilarIdea",
    "SortField",
    "ParsedCursor",
}


def test_public_surface_exports_exactly_the_contract() -> None:
    assert set(ideas.__all__) == _EXPECTED_SURFACE
    for name in sorted(_EXPECTED_SURFACE):
        assert getattr(ideas, name) is not None, name


# ------------------------------------------------------------ title placeholder


def test_placeholder_title_collapses_whitespace_and_truncates() -> None:
    assert placeholder_title("  A dog\nwalking   app  ") == "A dog walking app"
    assert placeholder_title("x" * 80) == "x" * 60


def test_placeholder_title_falls_back_for_blank_input() -> None:
    assert placeholder_title("   ") == "Untitled idea"


def test_placeholder_title_uses_first_sixty_chars_of_raw_input() -> None:
    raw = "Build a marketplace for vintage bicycles in Berlin and beyond"
    assert placeholder_title(raw) == raw[:60].strip()


# ------------------------------------------------------------------- payloads


def test_idea_create_requires_raw_input() -> None:
    with pytest.raises(ValidationError):
        IdeaCreate(raw_input="")
    with pytest.raises(ValidationError):
        IdeaCreate(raw_input="x" * 5001)


def test_idea_create_defaults() -> None:
    data = IdeaCreate(raw_input="hello")
    assert data.title is None
    assert data.context is None
    assert data.tags == []
    assert data.analyze is True


def test_idea_create_rejects_oversize_title() -> None:
    with pytest.raises(ValidationError):
        IdeaCreate(raw_input="hello", title="t" * 81)


def test_idea_version_create_bounds() -> None:
    assert IdeaVersionCreate(raw_input="hi").analyze is True
    with pytest.raises(ValidationError):
        IdeaVersionCreate(raw_input="")
    with pytest.raises(ValidationError):
        IdeaVersionCreate(raw_input="x" * 5001)


def test_idea_update_is_all_optional() -> None:
    update = IdeaUpdate()
    assert update.title is None
    assert update.tags is None
    assert update.pinned is None
    assert update.archived is None


# ------------------------------------------------------------------- payload caps


def _context_of_exact_size(size: int) -> dict[str, object]:
    empty = len(json.dumps({"n": ""}))
    return {"n": "x" * (size - empty)}


def test_context_at_the_serialized_cap_is_accepted() -> None:
    context = _context_of_exact_size(CONTEXT_MAX_CHARS)
    assert len(json.dumps(context)) == CONTEXT_MAX_CHARS
    assert IdeaCreate(raw_input="hi", context=context).context == context
    assert IdeaVersionCreate(raw_input="hi", context=context).context == context


def test_context_over_the_serialized_cap_is_rejected() -> None:
    context = _context_of_exact_size(CONTEXT_MAX_CHARS + 1)
    with pytest.raises(ValidationError):
        IdeaCreate(raw_input="hi", context=context)
    with pytest.raises(ValidationError):
        IdeaVersionCreate(raw_input="hi", context=context)


def test_tags_are_trimmed_deduplicated_case_insensitively_and_ordered() -> None:
    data = IdeaCreate(raw_input="hi", tags=[" Pets ", "pets", "AI", "ai", " ml "])
    assert data.tags == ["Pets", "AI", "ml"]


def test_tags_boundaries() -> None:
    assert IdeaCreate(raw_input="hi", tags=["t" * TAG_MAX_CHARS]).tags == ["t" * TAG_MAX_CHARS]
    distinct = [f"tag-{index}" for index in range(TAGS_MAX)]
    assert IdeaCreate(raw_input="hi", tags=distinct).tags == distinct
    with pytest.raises(ValidationError):
        IdeaCreate(raw_input="hi", tags=["t" * (TAG_MAX_CHARS + 1)])
    with pytest.raises(ValidationError):
        IdeaCreate(raw_input="hi", tags=["   "])
    with pytest.raises(ValidationError):
        IdeaCreate(raw_input="hi", tags=["t"] * (TAGS_MAX + 1))


def test_idea_update_tags_share_the_caps() -> None:
    assert IdeaUpdate(tags=[" A ", "a", "b"]).tags == ["A", "b"]
    assert IdeaUpdate(tags=None).tags is None
    with pytest.raises(ValidationError):
        IdeaUpdate(tags=["t"] * (TAGS_MAX + 1))
    with pytest.raises(ValidationError):
        IdeaUpdate(tags=["t" * (TAG_MAX_CHARS + 1)])


# ------------------------------------------------------------------ from_idea


def _idea_with_children() -> Idea:
    now = datetime.now(UTC)
    idea = Idea(
        id=uuid.uuid4(),
        title="Dog walking app",
        status=IdeaStatus.done,
        verdict=IdeaVerdict.pursue,
        category="consumer",
        overall_score=82.5,
        pinned=True,
        archived_at=None,
        created_at=now,
        updated_at=now,
    )
    version = IdeaVersion(
        id=uuid.uuid4(),
        idea_id=idea.id,
        number=2,
        raw_input="walking dogs",
        context={"region": "eu"},
        brief={"problem": "busy owners"},
        created_at=now,
    )
    idea.versions = [version]
    idea.tags = [Tag(id=uuid.uuid4(), name="pets")]
    return idea


def test_idea_detail_from_idea() -> None:
    detail = IdeaDetail.from_idea(_idea_with_children())
    assert detail.title == "Dog walking app"
    assert detail.status is IdeaStatus.done
    assert detail.verdict is IdeaVerdict.pursue
    assert detail.latest_version.number == 2
    assert detail.latest_version.context == {"region": "eu"}
    assert detail.versions[0].brief == {"problem": "busy owners"}
    assert detail.tags == ["pets"]


def test_idea_summary_from_idea() -> None:
    summary = IdeaSummary.from_idea(_idea_with_children())
    assert summary.latest_version_number == 2
    assert summary.tags == ["pets"]
