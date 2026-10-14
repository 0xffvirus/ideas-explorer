"""Text helpers shared by the adapters: HTML stripping, snippets, scores."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from html.parser import HTMLParser

from app.research.contract import TITLE_MAX_CHARS

_WHITESPACE = re.compile(r"\s+")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?:\+\d{1,3}[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]\d{4}")
_SKIPPED_TAGS = frozenset({"script", "style"})

MAX_QUERY_CHARS = 500


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIPPED_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


def strip_html(value: str) -> str:
    """Return the visible text of ``value`` without tags or entities."""
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    return _WHITESPACE.sub(" ", parser.text()).strip()


def redact_contact_info(value: str) -> str:
    """Replace email addresses and phone-shaped numbers with placeholders.

    The phone pattern requires a real phone shape (separators or a country
    prefix) so that dates, decimals, and large plain numbers survive.
    """
    without_emails = _EMAIL.sub("[email redacted]", value)
    return _PHONE.sub("[phone redacted]", without_emails)


def clean_snippet(value: str | None, *, max_chars: int) -> str:
    """Strip HTML, redact contact details, collapse whitespace, truncate."""
    if not value:
        return ""
    cleaned = redact_contact_info(strip_html(value))
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rstrip()


def clean_title(value: str | None, *, max_chars: int = TITLE_MAX_CHARS) -> str:
    """Strip HTML and contacts from a provider title, cap it to the contract."""
    if not value:
        return ""
    cleaned = redact_contact_info(strip_html(value))
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rstrip()


def normalize_query(query: str) -> str:
    """Collapse whitespace, drop control characters, lowercase, and cap length."""
    without_controls = _CONTROL_CHARS.sub(" ", query)
    collapsed = _WHITESPACE.sub(" ", without_controls).strip().lower()
    return collapsed[:MAX_QUERY_CHARS]


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def saturate_score(value: float, *, half_point: float) -> float:
    """Map an unbounded count (upvotes, points) smoothly into ``[0, 1]``."""
    if value <= 0:
        return 0.0
    return clamp01(value / (value + half_point))


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def parse_epoch_datetime(value: float | int | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None
