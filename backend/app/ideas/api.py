"""FastAPI router for the idea-core module."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db_session
from app.ideas.embedder import Embedder, OpenAIEmbedder
from app.ideas.models import IdeaStatus, IdeaVerdict
from app.ideas.schemas import (
    IdeaCreate,
    IdeaDetail,
    IdeaListResponse,
    IdeaUpdate,
    IdeaVersionCreate,
    SearchMode,
    SimilarIdea,
    SortField,
    TagCount,
)
from app.ideas.search import InvalidCursorError
from app.ideas.service import AnalysisEnqueuer, IdeaNotFound, IdeaService

router = APIRouter()


def get_embedder() -> Embedder:
    """Build the production OpenAI embedder from settings."""
    settings = get_settings()
    return OpenAIEmbedder(
        api_key=settings.openai_api_key,
        model=settings.openai_embedding_model,
        dimensions=settings.embedding_dimensions,
    )


def get_analysis_enqueuer() -> AnalysisEnqueuer | None:
    """Analysis enqueuer dependency; ``app/main.py`` overrides this with the real one."""
    return None


async def get_idea_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    enqueuer: Annotated[AnalysisEnqueuer | None, Depends(get_analysis_enqueuer)],
) -> IdeaService:
    """Compose an :class:`IdeaService` from request-scoped dependencies."""
    return IdeaService(session, embedder, enqueuer)


ServiceDep = Annotated[IdeaService, Depends(get_idea_service)]


@router.post("/ideas", status_code=201)
async def create_idea(data: IdeaCreate, service: ServiceDep) -> IdeaDetail:
    """Create an idea with its first version; enqueues analysis when ``analyze`` is true."""
    return await service.create(data)


@router.get("/ideas")
async def list_ideas(
    service: ServiceDep,
    q: Annotated[str | None, Query()] = None,
    mode: Annotated[SearchMode, Query()] = SearchMode.hybrid,
    status: Annotated[IdeaStatus | None, Query()] = None,
    verdict: Annotated[IdeaVerdict | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    tag: Annotated[str | None, Query()] = None,
    pinned: Annotated[bool | None, Query()] = None,
    archived: Annotated[bool, Query()] = False,
    score_min: Annotated[float | None, Query()] = None,
    score_max: Annotated[float | None, Query()] = None,
    sort: Annotated[SortField, Query()] = SortField.recent,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> IdeaListResponse:
    """Search, filter and paginate ideas."""
    try:
        return await service.search(
            q=q,
            mode=mode,
            status=status,
            verdict=verdict,
            category=category,
            tag=tag,
            pinned=pinned,
            archived=archived,
            score_min=score_min,
            score_max=score_max,
            sort=sort,
            cursor=cursor,
            limit=limit,
        )
    except InvalidCursorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/ideas/{idea_id}")
async def get_idea(idea_id: uuid.UUID, service: ServiceDep) -> IdeaDetail:
    """Fetch one idea with all versions and tags."""
    try:
        return await service.get(idea_id)
    except IdeaNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/ideas/{idea_id}")
async def update_idea(idea_id: uuid.UUID, data: IdeaUpdate, service: ServiceDep) -> IdeaDetail:
    """Patch an idea's title, tags, pinned or archived flag."""
    try:
        return await service.update(idea_id, data)
    except IdeaNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/ideas/{idea_id}/versions", status_code=201)
async def add_version(
    idea_id: uuid.UUID,
    data: IdeaVersionCreate,
    service: ServiceDep,
) -> IdeaDetail:
    """Append a new version to an idea."""
    try:
        return await service.add_version(idea_id, data)
    except IdeaNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/ideas/{idea_id}/similar")
async def similar_ideas(idea_id: uuid.UUID, service: ServiceDep) -> list[SimilarIdea]:
    """Top 5 ideas nearest to this one by embedding cosine distance."""
    try:
        return await service.similar(idea_id)
    except IdeaNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/tags")
async def list_tags(service: ServiceDep) -> list[TagCount]:
    """All tags with their idea counts."""
    return await service.list_tags()
