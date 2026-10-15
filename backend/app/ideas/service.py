"""IdeaService: all reads and writes of the idea tables, with no HTTP concerns."""

from __future__ import annotations

import uuid
from collections import OrderedDict
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.ideas.embedder import Embedder
from app.ideas.models import (
    Idea,
    IdeaSearch,
    IdeaStatus,
    IdeaTag,
    IdeaVerdict,
    IdeaVersion,
    Tag,
)
from app.ideas.schemas import (
    IdeaCreate,
    IdeaDetail,
    IdeaListResponse,
    IdeaSummary,
    IdeaUpdate,
    IdeaVersionCreate,
    ParsedCursor,
    SearchMode,
    SimilarIdea,
    SortField,
    TagCount,
)
from app.ideas.search import (
    MAX_LIMIT,
    SearchFilters,
    build_conditions,
    build_fts_candidates,
    build_list_query,
    build_search_index_upsert,
    build_search_text,
    build_vector_candidates,
    decode_cursor,
    encode_cursor,
    paginate_ranked,
    rrf_fuse,
)
from app.obs import get_logger

logger = get_logger(__name__)

QUERY_EMBEDDING_CACHE_SIZE = 256

_QUERY_EMBEDDING_CACHE: OrderedDict[str, list[float]] = OrderedDict()


def _normalize_query_text(query: str) -> str:
    return " ".join(query.lower().split())


async def cached_query_embedding(embedder: Embedder, query: str) -> list[float] | None:
    """Embed a search query once per normalized text, with a bounded LRU cache.

    Repeated identical searches skip the paid embedding call. Only successful
    embeddings are cached and the cache holds at most
    :data:`QUERY_EMBEDDING_CACHE_SIZE` entries; idea-document embeddings are
    unaffected.
    """
    key = _normalize_query_text(query)
    cached = _QUERY_EMBEDDING_CACHE.get(key)
    if cached is not None:
        _QUERY_EMBEDDING_CACHE.move_to_end(key)
        return cached
    try:
        vectors = await embedder.embed([query])
    except Exception:
        logger.warning("embedding call failed", exc_info=True)
        return None
    if not vectors:
        return None
    _QUERY_EMBEDDING_CACHE[key] = vectors[0]
    while len(_QUERY_EMBEDDING_CACHE) > QUERY_EMBEDDING_CACHE_SIZE:
        _QUERY_EMBEDDING_CACHE.popitem(last=False)
    return vectors[0]


class IdeaNotFound(Exception):
    """Raised when an idea (or one of its versions) does not exist."""


class AnalysisEnqueuer(Protocol):
    """Port for enqueueing analysis jobs; agent-pipeline implements it.

    ``enqueue_analysis`` runs in the caller's session and transaction so the
    idea row and its job commit atomically.
    """

    async def enqueue_analysis(
        self,
        session: AsyncSession,
        idea_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> None:
        """Persist an analysis job for one idea version."""
        ...


def placeholder_title(raw_input: str) -> str:
    """First 60 characters of the input on a single line; used until the pipeline names it."""
    normalized = " ".join(raw_input.split())
    return normalized[:60].strip() or "Untitled idea"


class IdeaService:
    """Owns the idea lifecycle: create, version, tag, search, archive.

    A service instance is bound to one :class:`AsyncSession` and commits its own
    transactions (the session factory does not autocommit).
    """

    def __init__(
        self,
        session: AsyncSession,
        embedder: Embedder,
        enqueuer: AnalysisEnqueuer | None = None,
    ) -> None:
        self._session = session
        self._embedder = embedder
        self._enqueuer = enqueuer

    async def create(self, data: IdeaCreate) -> IdeaDetail:
        """Create an idea with version 1, tags, and its search row.

        An embedding failure never fails the create: the idea is saved with a
        NULL embedding and the worker retries via :meth:`refresh_search_index`.
        """
        title = (data.title or "").strip() or placeholder_title(data.raw_input)
        idea = Idea(
            title=title,
            status=IdeaStatus.queued if data.analyze else IdeaStatus.draft,
            tags=[],
            versions=[],
        )
        self._session.add(idea)
        await self._session.flush()
        version = IdeaVersion(
            number=1,
            raw_input=data.raw_input,
            context=data.context,
        )
        idea.versions.append(version)
        await self._session.flush()
        await self._reindex(idea, version)
        await self._sync_tags(idea, data.tags)
        if data.analyze and self._enqueuer is not None:
            await self._enqueuer.enqueue_analysis(self._session, idea.id, version.id)
        await self._session.commit()
        return await self.get(idea.id)

    async def get(self, idea_id: uuid.UUID) -> IdeaDetail:
        """Return the full idea detail including every version and tag."""
        idea = await self._load_idea(idea_id)
        return IdeaDetail.from_idea(idea)

    async def list(
        self,
        *,
        q: str | None = None,
        mode: SearchMode = SearchMode.hybrid,
        status: IdeaStatus | None = None,
        verdict: IdeaVerdict | None = None,
        category: str | None = None,
        tag: str | None = None,
        pinned: bool | None = None,
        archived: bool = False,
        score_min: float | None = None,
        score_max: float | None = None,
        sort: SortField = SortField.recent,
        cursor: str | None = None,
        limit: int = 30,
    ) -> IdeaListResponse:
        """List ideas with the same semantics as :meth:`search`."""
        return await self.search(
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

    async def search(
        self,
        *,
        q: str | None = None,
        mode: SearchMode = SearchMode.hybrid,
        status: IdeaStatus | None = None,
        verdict: IdeaVerdict | None = None,
        category: str | None = None,
        tag: str | None = None,
        pinned: bool | None = None,
        archived: bool = False,
        score_min: float | None = None,
        score_max: float | None = None,
        sort: SortField = SortField.recent,
        cursor: str | None = None,
        limit: int = 30,
    ) -> IdeaListResponse:
        """Search, filter and keyset-paginate ideas.

        With a non-empty ``q`` the result is ranked (RRF in hybrid mode, FTS in
        keyword mode, cosine in semantic mode with keyword fallback). Without a
        ``q`` this is a plain filtered list ordered by ``sort``.
        """
        limit = max(1, min(limit, MAX_LIMIT))
        filters = SearchFilters(
            status=status,
            verdict=verdict,
            category=category,
            tag=tag,
            pinned=pinned,
            archived=archived,
            score_min=score_min,
            score_max=score_max,
        )
        parsed = decode_cursor(cursor) if cursor else None
        query = (q or "").strip()
        if query:
            return await self._search_ranked(query, mode, filters, parsed, limit)
        return await self._list_plain(filters, sort, parsed, limit)

    async def _search_ranked(
        self,
        q: str,
        mode: SearchMode,
        filters: SearchFilters,
        cursor: ParsedCursor | None,
        limit: int,
    ) -> IdeaListResponse:
        embedding = await self._query_embedding(q, mode)
        conditions = build_conditions(filters)
        rankings: list[list[uuid.UUID]] = []
        if mode is not SearchMode.semantic or embedding is None:
            rankings.append(await self._candidate_ids(build_fts_candidates(q, conditions)))
        if embedding is not None and mode in (SearchMode.hybrid, SearchMode.semantic):
            rankings.append(
                await self._candidate_ids(build_vector_candidates(embedding, conditions))
            )
        fused = rrf_fuse(rankings)
        page, next_cursor = paginate_ranked(fused, cursor=cursor, limit=limit)
        ideas = await self._load_ideas([idea_id for idea_id, _ in page])
        return IdeaListResponse(
            items=[IdeaSummary.from_idea(idea) for idea in ideas],
            next_cursor=next_cursor,
        )

    async def _candidate_ids(self, stmt: Select[uuid.UUID, float]) -> list[uuid.UUID]:
        rows = (await self._session.execute(stmt)).all()
        return [row[0] for row in rows]

    async def _list_plain(
        self,
        filters: SearchFilters,
        sort: SortField,
        cursor: ParsedCursor | None,
        limit: int,
    ) -> IdeaListResponse:
        stmt = build_list_query(filters=filters, sort=sort, cursor=cursor, limit=limit)
        result = await self._session.execute(stmt)
        ideas = list(result.scalars().all())
        has_more = len(ideas) > limit
        page = ideas[:limit]
        next_cursor: str | None = None
        if has_more and page:
            next_cursor = encode_cursor(sort.value, _sort_key(sort, page[-1]), page[-1].id)
        return IdeaListResponse(
            items=[IdeaSummary.from_idea(idea) for idea in page],
            next_cursor=next_cursor,
        )

    async def update(self, idea_id: uuid.UUID, data: IdeaUpdate) -> IdeaDetail:
        """Patch title, tags (full replace), pinned and archived."""
        idea = await self._load_idea(idea_id)
        title_changed = False
        if data.title is not None:
            new_title = data.title.strip()
            if new_title and new_title != idea.title:
                idea.title = new_title
                title_changed = True
        if data.pinned is not None:
            idea.pinned = data.pinned
        if data.archived is not None:
            idea.archived_at = datetime.now(UTC) if data.archived else None
        if data.tags is not None:
            await self._sync_tags(idea, data.tags)
        if title_changed:
            await self._refresh_tsv(idea)
        await self._session.commit()
        return await self.get(idea_id)

    async def add_version(self, idea_id: uuid.UUID, data: IdeaVersionCreate) -> IdeaDetail:
        """Append a gapless new version, re-index the search row, enqueue if asked."""
        idea = await self._load_idea(idea_id)
        max_number = await self._session.scalar(
            select(func.max(IdeaVersion.number)).where(IdeaVersion.idea_id == idea_id)
        )
        version = IdeaVersion(
            number=int(max_number or 0) + 1,
            raw_input=data.raw_input,
            context=data.context,
        )
        idea.versions.append(version)
        await self._session.flush()
        await self._reindex(idea, version)
        if data.analyze and self._enqueuer is not None:
            await self._enqueuer.enqueue_analysis(self._session, idea_id, version.id)
        await self._session.commit()
        return await self.get(idea_id)

    async def set_analysis_fields(
        self,
        idea_id: uuid.UUID,
        *,
        verdict: IdeaVerdict | None,
        overall_score: float | None,
        category: str | None,
        title: str | None = None,
    ) -> None:
        """Write pipeline-owned score fields; refreshes the tsv when the title changes."""
        idea = await self._load_idea(idea_id)
        idea.verdict = verdict
        idea.overall_score = overall_score
        idea.category = category
        if title is not None:
            new_title = title.strip()
            if new_title and new_title != idea.title:
                idea.title = new_title
                await self._refresh_tsv(idea)
        await self._session.commit()

    async def set_status(self, idea_id: uuid.UUID, status: IdeaStatus) -> None:
        """Set the lifecycle status (written by the pipeline and worker)."""
        idea = await self._load_idea(idea_id)
        idea.status = status
        await self._session.commit()

    async def set_version_brief(
        self,
        idea_id: uuid.UUID,
        version_number: int,
        brief: dict[str, Any],
    ) -> None:
        """Store a version's polished brief and refresh the search text from it."""
        idea = await self._load_idea(idea_id)
        version = next(
            (item for item in idea.versions if item.number == version_number),
            None,
        )
        if version is None:
            raise IdeaNotFound(f"version {version_number} of idea {idea_id} not found")
        version.brief = brief
        text = build_search_text(idea.title, version.raw_input, version.brief)
        await self._session.execute(
            build_search_index_upsert(idea_id=idea.id, text=text, embedding=None)
        )
        await self._session.commit()

    async def archive(self, idea_id: uuid.UUID, archived: bool = True) -> IdeaDetail:
        """Archive or restore an idea."""
        idea = await self._load_idea(idea_id)
        idea.archived_at = datetime.now(UTC) if archived else None
        await self._session.commit()
        return await self.get(idea_id)

    async def refresh_search_index(self, idea_id: uuid.UUID) -> bool:
        """Rebuild tsv and embedding for the latest version.

        Returns ``False`` when the embedding call failed so the worker can retry;
        the tsv is still rebuilt and committed in that case.
        """
        idea = await self._load_idea(idea_id)
        version = idea.versions[-1]
        embedded = await self._reindex(idea, version)
        await self._session.commit()
        return embedded

    async def similar(self, idea_id: uuid.UUID, limit: int = 5) -> list[SimilarIdea]:
        """Nearest other ideas by cosine distance; empty when the idea has no embedding."""
        await self._load_idea(idea_id)
        search_row = await self._session.get(IdeaSearch, idea_id)
        if search_row is None or search_row.embedding is None:
            return []
        distance = IdeaSearch.embedding.cosine_distance(search_row.embedding)
        stmt = (
            select(Idea.id, Idea.title, distance.label("distance"))
            .join(IdeaSearch, IdeaSearch.idea_id == Idea.id)
            .where(IdeaSearch.idea_id != idea_id, IdeaSearch.embedding.is_not(None))
            .order_by(distance, Idea.id)
            .limit(max(1, min(limit, 50)))
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            SimilarIdea(id=row_id, title=title, distance=float(row_distance))
            for row_id, title, row_distance in rows
        ]

    async def list_tags(self) -> list[TagCount]:
        """All tag names with their idea counts, most used first."""
        count = func.count(IdeaTag.idea_id)
        stmt = (
            select(Tag.name, count)
            .join(IdeaTag, IdeaTag.tag_id == Tag.id)
            .group_by(Tag.name)
            .order_by(count.desc(), Tag.name.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [TagCount(name=name, count=int(total)) for name, total in rows]

    async def _load_idea(self, idea_id: uuid.UUID) -> Idea:
        result = await self._session.execute(select(Idea).where(Idea.id == idea_id))
        idea = result.scalar_one_or_none()
        if idea is None:
            raise IdeaNotFound(f"idea {idea_id} not found")
        return idea

    async def _load_ideas(self, idea_ids: Sequence[uuid.UUID]) -> list[Idea]:
        if not idea_ids:
            return []
        result = await self._session.execute(select(Idea).where(Idea.id.in_(idea_ids)))
        by_id = {idea.id: idea for idea in result.scalars().all()}
        return [by_id[idea_id] for idea_id in idea_ids if idea_id in by_id]

    async def _safe_embed(self, texts: list[str]) -> list[list[float]] | None:
        try:
            vectors = await self._embedder.embed(texts)
        except Exception:
            logger.warning("embedding call failed", exc_info=True)
            return None
        return vectors or None

    async def _query_embedding(self, q: str, mode: SearchMode) -> list[float] | None:
        if mode is SearchMode.keyword:
            return None
        return await cached_query_embedding(self._embedder, q)

    async def _reindex(self, idea: Idea, version: IdeaVersion) -> bool:
        text = build_search_text(idea.title, version.raw_input, version.brief)
        vectors = await self._safe_embed([text])
        embedding = vectors[0] if vectors is not None else None
        await self._session.execute(
            build_search_index_upsert(idea_id=idea.id, text=text, embedding=embedding)
        )
        return embedding is not None

    async def _refresh_tsv(self, idea: Idea) -> None:
        version = idea.versions[-1]
        text = build_search_text(idea.title, version.raw_input, version.brief)
        await self._session.execute(
            build_search_index_upsert(idea_id=idea.id, text=text, embedding=None)
        )

    async def _sync_tags(self, idea: Idea, names: Sequence[str]) -> None:
        normalized = sorted({name.strip() for name in names if name.strip()})
        if not normalized:
            idea.tags = []
            return
        result = await self._session.execute(select(Tag).where(Tag.name.in_(normalized)))
        existing = {tag.name: tag for tag in result.scalars().all()}
        tags: list[Tag] = []
        for name in normalized:
            tag = existing.get(name)
            if tag is None:
                tag = Tag(name=name)
                self._session.add(tag)
                await self._session.flush()
                existing[name] = tag
            tags.append(tag)
        idea.tags = tags


def _sort_key(sort: SortField, idea: Idea) -> str | None:
    match sort:
        case SortField.recent:
            return idea.created_at.isoformat()
        case SortField.score:
            return None if idea.overall_score is None else repr(float(idea.overall_score))
        case SortField.title:
            return idea.title.lower()
