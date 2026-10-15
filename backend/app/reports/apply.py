"""Write a finished analysis back onto the idea row.

The worker calls :func:`apply_analysis_to_idea` after a successful run so the
library and compare views can filter on verdict, overall score, category, and
the polished title without loading the full report.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.db import Database
from app.ideas import IdeaService, IdeaVerdict
from app.pipeline.outputs import AnalysisResult
from app.reports.assembler import NoopEmbedder, compute_overall_score

_database: Database | None = None


def _default_session_factory() -> async_sessionmaker[AsyncSession]:
    global _database
    if _database is None:
        _database = Database(get_settings().database_url)
    return _database.session_factory


def _idea_verdict(decision: str | None) -> IdeaVerdict | None:
    if decision is None:
        return None
    try:
        return IdeaVerdict(decision)
    except ValueError:
        return None


async def apply_analysis_to_idea(
    result: AnalysisResult,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Set verdict, overall score, category, and title on the analyzed idea.

    A missing or unscored verdict maps to ``None``, and an uncomputable overall
    score stays ``None`` rather than fabricating a number.
    """
    settings = get_settings()
    overall_score = compute_overall_score(result.scorecard, settings.report_score_weights)
    category = result.classification.category if result.classification is not None else None
    factory = session_factory or _default_session_factory()
    async with factory() as session:
        service = IdeaService(session, NoopEmbedder())
        await service.set_analysis_fields(
            result.idea_id,
            verdict=_idea_verdict(result.verdict.decision),
            overall_score=overall_score,
            category=category,
            title=result.brief.title,
        )
