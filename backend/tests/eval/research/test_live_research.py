"""Live checks against real providers. Run with ``uv run pytest -m eval`` (network).

These tests cost money (Tavily) or hit external services. They are excluded
from the default suite by the ``eval`` marker.
"""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.research import build_research_tools

pytestmark = pytest.mark.eval


async def test_live_tavily_returns_sourced_evidence() -> None:
    settings = get_settings()
    if not settings.tavily_api_key:
        pytest.skip("TAVILY_API_KEY is not configured")
    toolkit = build_research_tools(settings)
    try:
        items = await toolkit.web.search("pet sitting market size", limit=5)
    finally:
        await toolkit.aclose()
    assert items, "expected at least one result"
    assert all(item.source == "web" for item in items)
    assert all(str(item.url).startswith("http") for item in items)
    assert all(len(item.snippet) <= 1500 for item in items)


async def test_live_reddit_returns_sourced_evidence() -> None:
    settings = get_settings()
    if not (settings.reddit_client_id and settings.reddit_client_secret):
        pytest.skip("REDDIT_CLIENT_ID/SECRET are not configured")
    toolkit = build_research_tools(settings)
    try:
        items = await toolkit.reddit.search("pet sitter pain points", limit=5)
    finally:
        await toolkit.aclose()
    assert items, "expected at least one result"
    assert all(item.source == "reddit" for item in items)
    assert all("reddit.com" in str(item.url) for item in items)


async def test_live_hn_returns_sourced_evidence() -> None:
    toolkit = build_research_tools(get_settings())
    try:
        items = await toolkit.hn.search("pet sitting", limit=5)
    finally:
        await toolkit.aclose()
    assert items, "expected at least one result"
    assert all(item.source == "hn" for item in items)
    assert all(str(item.url).startswith(("http://", "https://")) for item in items)
    assert all(len(item.snippet) <= 1500 for item in items)
