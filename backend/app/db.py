"""Database engine, session factory, and the declarative base.

Modules must not create their own engines. Tests build their own
:class:`Database` against a test URL.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for every table in the app."""


class Database:
    """Owns one async engine and a session factory bound to it."""

    def __init__(self, url: str, *, echo: bool = False) -> None:
        self.url = url
        self.engine: AsyncEngine = create_async_engine(url, echo=echo, pool_pre_ping=True)
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine, expire_on_commit=False, autoflush=False
        )

    async def dispose(self) -> None:
        await self.engine.dispose()


@lru_cache(maxsize=1)
def get_database() -> Database:
    return Database(get_settings().database_url)


def reset_database_cache() -> None:
    get_database.cache_clear()


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session; services own commits."""
    database = get_database()
    async with database.session_factory() as session:
        yield session
