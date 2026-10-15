"""Unit tests for Evidence, CompanyLead, EvidenceLike, and snippet sanitization."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.research import CompanyLead, Evidence, EvidenceLike
from app.research.evidence import sanitize_snippet

PERSON_FIELD_MARKERS = ("email", "phone", "person", "contact")


def test_snippet_strips_html_unescapes_entities_and_collapses_whitespace() -> None:
    item = Evidence(
        source="web",
        url="https://example.com/a",
        title="t",
        snippet="<p>Hello &amp; welcome</p>\n\n<b>to</b>&nbsp;the   show",
    )
    assert item.snippet == "Hello & welcome to the show"


def test_snippet_truncates_long_input_with_an_ellipsis() -> None:
    item = Evidence(source="web", url="https://example.com/a", title="t", snippet="word " * 1000)
    assert len(item.snippet) <= 1500
    assert item.snippet.endswith("\u2026")


def test_title_strips_html_entities_and_whitespace() -> None:
    item = Evidence(
        source="web",
        url="https://example.com/a",
        title="<b>Hello</b> &amp; welcome\n  to the show",
        snippet="s",
    )
    assert item.title == "Hello & welcome to the show"


def test_title_truncates_long_input_with_an_ellipsis() -> None:
    item = Evidence(source="web", url="https://example.com/a", title="word " * 200, snippet="s")
    assert len(item.title) <= 300
    assert item.title.endswith("\u2026")


def test_title_exactly_at_the_cap_is_untouched() -> None:
    item = Evidence(source="web", url="https://example.com/a", title="t" * 300, snippet="s")
    assert item.title == "t" * 300


def test_sanitize_honors_max_chars() -> None:
    assert sanitize_snippet("a" * 100, 10) == "a" * 9 + "\u2026"
    assert sanitize_snippet("short", 10) == "short"
    assert sanitize_snippet("anything", 0) == ""


def test_sanitize_never_cuts_through_a_lingering_entity() -> None:
    result = sanitize_snippet("prefix " + "&zznotanentity" * 20, 20)
    assert result == "prefix\u2026"


def test_score_is_clamped_to_the_unit_interval() -> None:
    base = {"source": "web", "url": "https://example.com/a", "title": "t", "snippet": "s"}
    assert Evidence(**base, score=1.7).score == 1.0
    assert Evidence(**base, score=-0.3).score == 0.0
    assert Evidence(**base).score is None
    assert Evidence(**base, score=0.42).score == 0.42


def test_retrieved_at_defaults_to_aware_utc_now() -> None:
    before = datetime.now(UTC) - timedelta(seconds=1)
    item = Evidence(source="hn", url="https://example.com/a", title="t", snippet="s")
    after = datetime.now(UTC) + timedelta(seconds=1)
    assert item.retrieved_at.tzinfo is not None
    assert before <= item.retrieved_at <= after


def test_naive_published_at_is_treated_as_utc() -> None:
    item = Evidence(
        source="hn",
        url="https://example.com/a",
        title="t",
        snippet="s",
        published_at=datetime(2024, 1, 1, 12, 0),
    )
    assert item.published_at == datetime(2024, 1, 1, 12, 0, tzinfo=UTC)


def test_evidence_like_accepts_evidence_and_duck_types() -> None:
    item = Evidence(source="web", url="https://example.com/a", title="t", snippet="s")
    assert isinstance(item, EvidenceLike)

    class Duck:
        url = "https://example.com/a"
        title = "t"
        snippet = "s"

    assert isinstance(Duck(), EvidenceLike)


def test_company_lead_has_no_person_level_fields() -> None:
    field_names = set(CompanyLead.model_fields)
    assert field_names == {"name", "domain", "industry", "size_band", "country", "why_fit", "url"}
    for field_name in field_names:
        assert not any(marker in field_name for marker in PERSON_FIELD_MARKERS)
