"""Unit tests for the text helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from app.research.text import (
    MAX_QUERY_CHARS,
    clamp01,
    clean_snippet,
    clean_title,
    normalize_query,
    parse_epoch_datetime,
    parse_iso_datetime,
    redact_contact_info,
    saturate_score,
    strip_html,
)


def test_strip_html_removes_tags_and_entities() -> None:
    assert strip_html("<p>Hello <b>world</b> &amp; friends</p>") == "Hello world & friends"


def test_strip_html_drops_script_and_style_content() -> None:
    html = "<style>.a{color:red}</style><p>Visible</p><script>alert(1)</script>"
    assert strip_html(html) == "Visible"


def test_strip_html_collapses_whitespace() -> None:
    assert strip_html("<p>one\n\n  two</p>\t <div>three</div>") == "one two three"


def test_clean_snippet_truncates_after_stripping() -> None:
    html = "<p>" + "x" * 2000 + "</p>"
    out = clean_snippet(html, max_chars=1500)
    assert len(out) == 1500
    assert "<" not in out


def test_clean_snippet_handles_missing_or_empty_values() -> None:
    assert clean_snippet(None, max_chars=10) == ""
    assert clean_snippet("", max_chars=10) == ""
    assert clean_snippet("  <b>hi</b>  ", max_chars=10) == "hi"


def test_clean_snippet_redacts_emails_and_phones() -> None:
    out = clean_snippet(
        "Email me at jane.doe@example.com or call +1 (555) 123-4567 today.", max_chars=200
    )
    assert "jane.doe@example.com" not in out
    assert "[email redacted]" in out
    assert "+1 (555) 123-4567" not in out
    assert "[phone redacted]" in out


def test_clean_snippet_keeps_dates_and_numbers() -> None:
    text = "Published 2024-06-01, priced at $30/visit, 120 people upvoted."
    assert clean_snippet(text, max_chars=200) == text


def test_clean_snippet_preserves_date_times_and_decimals() -> None:
    text = "At 2024-06-01 10:30 the value was 3.1415926535 in market 2400000000."
    assert clean_snippet(text, max_chars=200) == text


def test_redact_contact_info_matches_exact_phone_shapes() -> None:
    assert redact_contact_info("(555) 123-4567") == "[phone redacted]"
    assert redact_contact_info("555-123-4567") == "[phone redacted]"
    assert redact_contact_info("+1 555 123 4567") == "[phone redacted]"
    assert redact_contact_info("call 555-1234") == "call 555-1234"
    assert redact_contact_info("order 1234567890") == "order 1234567890"


def test_clean_title_strips_html_and_caps_length() -> None:
    assert clean_title("<b>Pet</b> market &amp; growth") == "Pet market & growth"
    assert len(clean_title("t" * 900)) == 500
    assert clean_title(None) == ""


def test_normalize_query() -> None:
    assert normalize_query("  Pet  SITTING\nmarket ") == "pet sitting market"
    assert normalize_query("   ") == ""
    assert normalize_query("a\x00b\x1fc") == "a b c"


def test_normalize_query_caps_length() -> None:
    assert len(normalize_query("pet sitting " * 100)) == MAX_QUERY_CHARS


def test_clamp01() -> None:
    assert clamp01(-3.0) == 0.0
    assert clamp01(0.4) == 0.4
    assert clamp01(7.0) == 1.0


def test_saturate_score() -> None:
    assert saturate_score(0, half_point=50) == 0.0
    assert saturate_score(-4, half_point=50) == 0.0
    assert saturate_score(50, half_point=50) == 0.5
    assert saturate_score(3, half_point=50) == 3 / 53


def test_parse_iso_datetime() -> None:
    assert parse_iso_datetime("2024-06-01T10:30:00Z") == datetime(2024, 6, 1, 10, 30, tzinfo=UTC)
    assert parse_iso_datetime("2024-06-01") == datetime(2024, 6, 1)
    assert parse_iso_datetime("") is None
    assert parse_iso_datetime(None) is None
    assert parse_iso_datetime("not-a-date") is None


def test_parse_epoch_datetime() -> None:
    assert parse_epoch_datetime(0) == datetime(1970, 1, 1, tzinfo=UTC)
    assert parse_epoch_datetime(None) is None
    assert parse_epoch_datetime("not-a-number") is None  # type: ignore[arg-type]
