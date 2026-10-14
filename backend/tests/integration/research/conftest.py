"""Integration test fixtures: every test starts with a clean database."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest


@pytest.fixture(autouse=True)
async def _clean_database(db_session) -> AsyncIterator[None]:
    yield
