"""FastAPI router for reports: JSON, Markdown, PDF, and side-by-side compare."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import get_database
from app.ideas import IdeaDetail, IdeaNotFound, IdeaService
from app.obs import get_logger
from app.reports.assembler import (
    DIMENSION_ORDER,
    InvalidReportVersion,
    NoopEmbedder,
    ReportNotFound,
    build_report,
)
from app.reports.models import CompareEntry, CompareIdeaReport, CompareReport, Report
from app.reports.render import render_markdown, render_pdf

logger = get_logger(__name__)

router = APIRouter()

COMPARE_MIN_IDS = 2
COMPARE_MAX_IDS = 3


def get_reports_session_factory() -> async_sessionmaker[AsyncSession]:
    """Session factory used to load runs and assemble reports."""
    return get_database().session_factory


SessionFactoryDep = Annotated[
    async_sessionmaker[AsyncSession], Depends(get_reports_session_factory)
]
VersionDep = Annotated[int | None, Query(ge=1)]


def parse_compare_ids(raw: str) -> list[uuid.UUID]:
    """Parse the ``ids`` query into 2-3 unique UUIDs; raises ``ValueError`` otherwise."""
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if not (COMPARE_MIN_IDS <= len(parts) <= COMPARE_MAX_IDS):
        raise ValueError(f"compare requires {COMPARE_MIN_IDS}-{COMPARE_MAX_IDS} idea ids")
    ids: list[uuid.UUID] = []
    for part in parts:
        try:
            ids.append(uuid.UUID(part))
        except ValueError as exc:
            raise ValueError(f"invalid idea id: {part}") from exc
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate idea ids are not allowed")
    return ids


async def _load_report(
    session_factory: async_sessionmaker[AsyncSession],
    idea_id: uuid.UUID,
    version_number: int | None,
) -> Report:
    try:
        return await build_report(session_factory, idea_id, version_number)
    except ReportNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidReportVersion as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/ideas/{idea_id}/report")
async def get_report(
    idea_id: uuid.UUID,
    session_factory: SessionFactoryDep,
    version: VersionDep = None,
) -> Report:
    """Assemble the report for the idea's latest (or the given) version."""
    return await _load_report(session_factory, idea_id, version)


@router.get("/ideas/{idea_id}/report.md")
async def get_report_markdown(
    idea_id: uuid.UUID,
    session_factory: SessionFactoryDep,
    version: VersionDep = None,
) -> Response:
    """Download the report as a Markdown attachment."""
    report = await _load_report(session_factory, idea_id, version)
    return Response(
        content=render_markdown(report),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="report-{idea_id}.md"'},
    )


@router.get("/ideas/{idea_id}/report.pdf")
async def get_report_pdf(
    idea_id: uuid.UUID,
    session_factory: SessionFactoryDep,
    version: VersionDep = None,
) -> Response:
    """Download the report as a PDF attachment; 503 when rendering fails."""
    report = await _load_report(session_factory, idea_id, version)
    try:
        payload = await render_pdf(report)
    except Exception as exc:
        logger.warning("PDF rendering failed for idea %s", idea_id, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"PDF rendering failed: {type(exc).__name__}",
        ) from exc
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report-{idea_id}.pdf"'},
    )


async def _idea_detail(
    session_factory: async_sessionmaker[AsyncSession], idea_id: uuid.UUID
) -> IdeaDetail | None:
    async with session_factory() as session:
        service = IdeaService(session, NoopEmbedder())
        try:
            return await service.get(idea_id)
        except IdeaNotFound:
            return None


def _detail_verdict(detail: IdeaDetail | None) -> str | None:
    if detail is None or detail.verdict is None:
        return None
    return detail.verdict.value


async def _compare_entry(
    session_factory: async_sessionmaker[AsyncSession], idea_id: uuid.UUID
) -> CompareEntry:
    detail = await _idea_detail(session_factory, idea_id)
    try:
        report: Report | None = await build_report(session_factory, idea_id)
        reason: str | None = None
    except ReportNotFound as exc:
        report = None
        reason = str(exc)
    if report is None:
        return CompareEntry(
            idea_id=idea_id,
            title=detail.title if detail is not None else None,
            verdict=_detail_verdict(detail),
            overall_score=detail.overall_score if detail is not None else None,
            category=detail.category if detail is not None else None,
            report=None,
            reason=reason or "no completed report",
        )
    header = report.header
    overall = (
        detail.overall_score
        if detail is not None and detail.overall_score is not None
        else header.overall_score
    )
    return CompareEntry(
        idea_id=idea_id,
        title=detail.title if detail is not None else header.title,
        one_liner=header.one_liner,
        verdict=_detail_verdict(detail) or header.verdict,
        verdict_confidence=header.verdict_confidence,
        overall_score=overall,
        category=detail.category if detail is not None else None,
        report=CompareIdeaReport(header=header, scorecard=report.scorecard),
        reason=None,
    )


@router.get("/compare")
async def compare(
    session_factory: SessionFactoryDep,
    ids: Annotated[str, Query()],
) -> CompareReport:
    """Compare 2-3 ideas side by side, aligned by scorecard dimension."""
    try:
        idea_ids = parse_compare_ids(ids)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    entries = [await _compare_entry(session_factory, idea_id) for idea_id in idea_ids]
    return CompareReport(dimensions=list(DIMENSION_ORDER), entries=entries)
