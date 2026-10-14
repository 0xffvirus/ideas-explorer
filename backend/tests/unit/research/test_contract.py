"""Unit tests for the public evidence contract."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.research.contract import SNIPPET_MAX_CHARS, TITLE_MAX_CHARS, CompanyLead, Evidence


def test_evidence_requires_an_http_url() -> None:
    with pytest.raises(ValidationError):
        Evidence(source="web", url="not a url", title="x", snippet="s")


def test_evidence_rejects_urls_with_credentials() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            source="reddit",
            url="https://www.reddit.com@evil.example.com/x",
            title="x",
            snippet="s",
        )


def test_evidence_snippet_is_length_capped() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            source="web",
            url="https://example.com",
            title="x",
            snippet="a" * (SNIPPET_MAX_CHARS + 1),
        )


def test_evidence_title_is_length_capped() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            source="web",
            url="https://example.com",
            title="t" * (TITLE_MAX_CHARS + 1),
            snippet="s",
        )


def test_evidence_is_immutable() -> None:
    evidence = Evidence(source="web", url="https://example.com", title="x", snippet="s")
    with pytest.raises(ValidationError):
        evidence.title = "changed"


def test_evidence_normalizes_naive_datetimes_to_utc() -> None:
    evidence = Evidence(
        source="hn",
        url="https://example.com",
        title="x",
        snippet="s",
        published_at=datetime(2024, 1, 1),
    )
    assert evidence.published_at == datetime(2024, 1, 1, tzinfo=UTC)
    assert evidence.retrieved_at.tzinfo is not None


def test_evidence_preserves_aware_offsets() -> None:
    offset = timezone(timedelta(hours=5))
    evidence = Evidence(
        source="hn",
        url="https://example.com",
        title="x",
        snippet="s",
        published_at=datetime(2024, 1, 1, 12, 0, tzinfo=offset),
    )
    assert evidence.published_at == datetime(2024, 1, 1, 12, 0, tzinfo=offset)
    assert evidence.published_at.utcoffset() == timedelta(hours=5)


def test_evidence_score_is_bounded() -> None:
    with pytest.raises(ValidationError):
        Evidence(source="web", url="https://example.com", title="x", snippet="s", score=1.5)
    with pytest.raises(ValidationError):
        Evidence(source="web", url="https://example.com", title="x", snippet="s", score=-0.1)


def test_company_lead_has_no_person_level_fields() -> None:
    fields = set(CompanyLead.model_fields)
    assert fields == {"name", "domain", "industry", "size_band", "country", "why_fit", "url"}
    forbidden = {
        "email",
        "phone",
        "phone_number",
        "first_name",
        "last_name",
        "full_name",
        "contact",
        "person",
        "linkedin",
    }
    assert fields.isdisjoint(forbidden)
