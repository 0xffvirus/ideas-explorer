"""Unit tests for report rendering: markdown snapshots, HTML markers, compare parsing."""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from pathlib import Path

import pytest

from app.reports.api import parse_compare_ids
from app.reports.assembler import SECTION_ORDER, assemble_report
from app.reports.render import PDF_RENDER_CONCURRENCY, render_html, render_markdown, render_pdf
from tests.fixtures.reports.fixtures import GENERATED_AT, make_result

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "reports"


def _report():
    return assemble_report(make_result(), run_date=GENERATED_AT, cost_usd=0.42)


@pytest.mark.parametrize("name", SECTION_ORDER)
def test_section_markdown_snapshot(name: str) -> None:
    report = _report()
    section = next(item for item in report.sections if item.name == name)
    expected = (FIXTURES / f"section_{name}.md").read_text()
    assert section.markdown + "\n" == expected


def test_full_markdown_snapshot() -> None:
    expected = (FIXTURES / "expected_report.md").read_text()
    assert render_markdown(_report()) == expected


def test_markdown_numbers_sources_and_marks_unverified() -> None:
    markdown = render_markdown(_report())
    assert "## Sources" in markdown
    assert "1. https://example.com/pet-market" in markdown
    assert "2. https://example.com/vettrack-pricing" in markdown
    assert "[2] _(unverified)_" in markdown
    assert "_(unverified: source unavailable)_" in markdown
    assert "75.9 / 100 (partial: some dimensions were not scored)" in markdown
    assert "2.0/5 ?" in markdown


def test_markdown_renders_not_completed_placeholder() -> None:
    report = assemble_report(
        make_result(drop_sections=("market",)),
        run_date=GENERATED_AT,
        cost_usd=0.42,
    )
    assert report.is_partial is True
    markdown = render_markdown(report)
    assert "## Market" in markdown
    assert "_Not completed._" in markdown
    assert "**Partial run:** some sections were not completed." in markdown
    market = next(item for item in report.sections if item.name == "market")
    assert market.status == "not_completed"
    assert market.json_payload == {}
    assert market.claims == []


def test_html_contains_dashed_low_confidence_and_unverified_markers() -> None:
    html = render_html(_report())
    assert html.startswith("<!doctype html>")
    assert html.rstrip().endswith("</html>")
    assert "low-confidence" in html
    assert "dashed" in html
    assert "unverified" in html
    assert "not scored" in html
    assert "Jev unavailable" in html
    assert "https://example.com/vettrack-pricing" in html
    assert html.count("low-confidence") >= 3


def test_report_json_round_trips() -> None:
    from app.reports.models import Report

    report = _report()
    restored = Report.model_validate_json(report.model_dump_json())
    assert restored == report


async def test_render_pdf_bounds_parallel_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    active = 0
    max_active = 0
    lock = threading.Lock()

    def fake_write_pdf(html: str) -> bytes:
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return b"%PDF-fake"

    monkeypatch.setattr("app.reports.render._write_pdf", fake_write_pdf)
    report = _report()
    payloads = await asyncio.gather(*(render_pdf(report) for _ in range(4)))

    assert payloads == [b"%PDF-fake"] * 4
    assert max_active == PDF_RENDER_CONCURRENCY


def test_parse_compare_ids_accepts_two_or_three_unique_ids() -> None:
    first = uuid.uuid4()
    second = uuid.uuid4()
    third = uuid.uuid4()
    assert parse_compare_ids(f"{first},{second}") == [first, second]
    assert parse_compare_ids(f" {first} , {second},{third} ") == [first, second, third]


def test_parse_compare_ids_rejects_wrong_count() -> None:
    idea = str(uuid.uuid4())
    with pytest.raises(ValueError):
        parse_compare_ids("")
    with pytest.raises(ValueError):
        parse_compare_ids("   ")
    with pytest.raises(ValueError):
        parse_compare_ids(idea)
    four = ",".join(str(uuid.uuid4()) for _ in range(4))
    with pytest.raises(ValueError):
        parse_compare_ids(four)


def test_parse_compare_ids_rejects_duplicates_and_invalid_uuids() -> None:
    idea = uuid.uuid4()
    with pytest.raises(ValueError):
        parse_compare_ids(f"{idea},{idea}")
    with pytest.raises(ValueError):
        parse_compare_ids(f"{idea},not-a-uuid")
