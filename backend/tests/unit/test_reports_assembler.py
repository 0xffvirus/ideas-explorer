"""Unit tests for report assembly and the loader's error behavior."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

import app.reports.assembler as assembler
from app.ideas import IdeaDetail, IdeaNotFound, IdeaStatus, IdeaVersionRead
from app.reports.assembler import (
    SECTION_ORDER,
    InvalidReportVersion,
    ReportNotFound,
    assemble_report,
    build_report,
)
from tests.fixtures.reports.fixtures import GENERATED_AT, IDEA_ID, VERSION_ID, make_result

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)


class _FakeResult:
    def scalar_one_or_none(self) -> None:
        return None


class _FakeSession:
    """Session that reports "no rows" for any query."""

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def execute(self, *args: object, **kwargs: object) -> _FakeResult:
        return _FakeResult()


def _factory() -> Any:
    return _FakeSession()


def _detail(numbers: tuple[int, ...] = (1,)) -> IdeaDetail:
    versions = [
        IdeaVersionRead(
            id=VERSION_ID if number == 1 else uuid.uuid4(),
            number=number,
            raw_input="A smart collar for senior dogs.",
            context=None,
            brief=None,
            created_at=NOW,
        )
        for number in numbers
    ]
    return IdeaDetail(
        id=IDEA_ID,
        title="PetPulse",
        status=IdeaStatus.done,
        verdict=None,
        category=None,
        overall_score=None,
        pinned=False,
        archived_at=None,
        created_at=NOW,
        updated_at=NOW,
        latest_version=versions[-1],
        versions=versions,
        tags=[],
    )


class _FakeService:
    def __init__(self, *, detail: IdeaDetail | None = None, error: Exception | None = None) -> None:
        self._detail = detail
        self._error = error

    async def get(self, idea_id: uuid.UUID) -> IdeaDetail:
        if self._error is not None:
            raise self._error
        assert self._detail is not None
        return self._detail


def _patch_service(
    monkeypatch: pytest.MonkeyPatch,
    *,
    detail: IdeaDetail | None = None,
    error: Exception | None = None,
) -> None:
    service = _FakeService(detail=detail, error=error)
    monkeypatch.setattr(assembler, "IdeaService", lambda session, embedder: service)


def test_assemble_report_shape_and_ordering() -> None:
    report = assemble_report(
        make_result(),
        run_date=GENERATED_AT,
        cost_usd=0.42,
        is_partial=False,
    )
    assert report.idea_id == make_result().idea_id
    assert report.run_id == make_result().run_id
    assert report.header.overall_score == 75.9
    assert report.header.score_basis == "partial"
    assert report.header.verdict == "refine"
    assert report.run_date == GENERATED_AT
    assert report.cost_usd == 0.42
    assert report.is_partial is False
    assert [section.name for section in report.sections] == list(SECTION_ORDER)
    assert all(section.status == "complete" for section in report.sections)
    assert [entry.dimension for entry in report.scorecard] == [
        score.dimension for score in make_result().scorecard.dimensions
    ]
    assert len(report.next_steps) == 3
    assert [source.number for source in report.sources] == [1, 2, 3]


def test_assemble_report_marks_missing_sections_partial() -> None:
    report = assemble_report(
        make_result(drop_sections=("market", "feasibility")),
        run_date=GENERATED_AT,
        cost_usd=0.0,
    )
    assert report.is_partial is True
    by_name = {section.name: section for section in report.sections}
    assert by_name["market"].status == "not_completed"
    assert by_name["feasibility"].status == "not_completed"
    assert by_name["competitors"].status == "complete"


async def test_build_report_raises_not_found_for_missing_idea(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_service(monkeypatch, error=IdeaNotFound("nope"))
    with pytest.raises(ReportNotFound):
        await build_report(_factory, IDEA_ID)


async def test_build_report_raises_invalid_version_for_unknown_number(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_service(monkeypatch, detail=_detail((1, 2)))
    with pytest.raises(InvalidReportVersion):
        await build_report(_factory, IDEA_ID, 99)


async def test_build_report_raises_not_found_when_no_completed_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_service(monkeypatch, detail=_detail((1,)))
    with pytest.raises(ReportNotFound):
        await build_report(_factory, IDEA_ID)
    with pytest.raises(ReportNotFound):
        await build_report(_factory, IDEA_ID, 1)
