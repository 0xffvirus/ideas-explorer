"""Cache implementations behind the :class:`~app.research.contract.Cache` protocol."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.obs import get_logger
from app.research.contract import Evidence
from app.research.models import ResearchCache

logger = get_logger(__name__)

_payload_adapter: TypeAdapter[list[dict[str, Any]]] = TypeAdapter(list[dict[str, Any]])


class NullCache:
    """Cache that stores nothing; used when no database is wired in."""

    async def get(self, key: str) -> list[Evidence] | None:
        return None

    async def set(self, key: str, items: Sequence[Evidence], *, ttl_seconds: int) -> None:
        return None


class InMemoryCache:
    """Process-local cache for tests and runs without Postgres."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._entries: dict[str, tuple[float, list[Evidence]]] = {}

    async def get(self, key: str) -> list[Evidence] | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, items = entry
        if self._clock() >= expires_at:
            self._entries.pop(key, None)
            return None
        return list(items)

    async def set(self, key: str, items: Sequence[Evidence], *, ttl_seconds: int) -> None:
        self._entries[key] = (self._clock() + ttl_seconds, list(items))


class PostgresCache:
    """Shared cache backed by the ``research_cache`` table."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get(self, key: str) -> list[Evidence] | None:
        try:
            async with self._session_factory() as session:
                row = await session.get(ResearchCache, key)
                if row is None:
                    return None
                if row.expires_at <= datetime.now(UTC):
                    await session.execute(
                        delete(ResearchCache).where(
                            ResearchCache.key == key,
                            ResearchCache.expires_at <= datetime.now(UTC),
                        )
                    )
                    await session.commit()
                    return None
                payload = row.payload
        except SQLAlchemyError as exc:
            logger.warning("research cache read failed key=%r error=%s", key, exc)
            return None
        try:
            entries = _payload_adapter.validate_python(payload)
        except ValidationError:
            logger.warning("research cache payload invalid key=%r; treating as a miss", key)
            return None
        items: list[Evidence] = []
        for entry in entries:
            try:
                items.append(Evidence.model_validate(entry))
            except ValidationError:
                logger.warning("research cache entry invalid key=%r; treating as a miss", key)
                return None
        return items

    async def set(self, key: str, items: Sequence[Evidence], *, ttl_seconds: int) -> None:
        if not items:
            return
        payload = [item.model_dump(mode="json") for item in items]
        expires_at = datetime.now(UTC) + timedelta(seconds=max(1, ttl_seconds))
        statement = (
            pg_insert(ResearchCache)
            .values(key=key, payload=payload, expires_at=expires_at)
            .on_conflict_do_update(
                index_elements=[ResearchCache.key],
                set_={"payload": payload, "expires_at": expires_at},
            )
        )
        try:
            async with self._session_factory() as session:
                await session.execute(statement)
                await session.execute(
                    delete(ResearchCache).where(ResearchCache.expires_at <= datetime.now(UTC))
                )
                await session.commit()
        except SQLAlchemyError as exc:
            logger.warning("research cache write failed key=%r error=%s", key, exc)
