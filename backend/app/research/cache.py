"""Postgres-backed research cache with per-adapter TTLs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.dialects.postgresql import Insert as PgInsert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.research.evidence import Evidence
from app.research.models import ResearchCache as ResearchCacheRow


def normalize_query(query: str) -> str:
    """Lowercase and collapse whitespace so equivalent queries share a key."""
    return " ".join(query.lower().split())


def cache_key(adapter_name: str, query: str, limit: int) -> str:
    """Cache key contract: ``adapter_name:normalized_query:limit=N``.

    The effective limit is part of the key so a small-limit response never
    poisons a later request for more results.
    """
    return f"{adapter_name}:{normalize_query(query)}:limit={limit}"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class ResearchCache:
    """Payload store for one adapter's results.

    ``session_factory=None`` disables caching entirely: reads miss and writes
    are no-ops, which keeps unit tests and unconfigured runs working.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock if clock is not None else _utcnow

    @property
    def enabled(self) -> bool:
        return self._session_factory is not None

    async def get(self, key: str) -> list[Evidence] | None:
        """Return the cached evidence, or ``None`` when absent or expired."""
        if self._session_factory is None:
            return None
        async with self._session_factory() as session:
            row = await session.get(ResearchCacheRow, key)
        if row is None or _as_aware(row.expires_at) <= self._clock():
            return None
        return [Evidence.model_validate(item) for item in row.payload]

    async def set(self, key: str, items: list[Evidence], ttl: timedelta) -> None:
        """Insert or refresh one cache entry for ``ttl``."""
        if self._session_factory is None:
            return
        payload = [item.model_dump(mode="json") for item in items]
        expires_at = self._clock() + ttl
        statement = PgInsert(ResearchCacheRow).values(
            key=key, payload=payload, expires_at=expires_at
        )
        statement = statement.on_conflict_do_update(
            index_elements=["key"],
            set_={
                "payload": statement.excluded.payload,
                "expires_at": statement.excluded.expires_at,
            },
        )
        async with self._session_factory() as session:
            await session.execute(statement)
            await session.commit()
