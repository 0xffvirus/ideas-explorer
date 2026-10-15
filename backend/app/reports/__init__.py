"""Public surface of the reports module. Other modules import only from here."""

from __future__ import annotations

from app.reports.api import router
from app.reports.apply import apply_analysis_to_idea
from app.reports.assembler import ReportNotFound, build_report
from app.reports.models import CompareReport, Report
from app.reports.render import render_html, render_markdown, render_pdf

__all__ = [
    "CompareReport",
    "Report",
    "ReportNotFound",
    "apply_analysis_to_idea",
    "build_report",
    "render_html",
    "render_markdown",
    "render_pdf",
    "router",
]
