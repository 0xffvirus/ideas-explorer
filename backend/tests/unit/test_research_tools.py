"""Tests for the composed tools: keys, config errors, and resilience."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from tenacity import wait_none

import app.research.adapters as adapters
from app.config import Settings, settings_as_test_overrides
from app.research import ResearchUnavailable, ToolDisabled, build_default_tools

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "research"
HACKERNEWS_JSON = json.loads((FIXTURES / "hackernews_search.json").read_text())

SETTINGS_DEFAULTS: dict[str, object] = {
    "tavily_api_key": "test-tavily-key",
    "reddit_client_id": "test-client-id",
    "reddit_client_secret": "test-client-secret",
    "research_timeout_seconds": 1.0,
    "research_max_retries": 2,
}


def make_settings(**overrides: object) -> Settings:
    return settings_as_test_overrides(**{**SETTINGS_DEFAULTS, **overrides})


def test_build_default_tools_always_returns_four_keys() -> None:
    tools = build_default_tools(make_settings())
    assert set(tools) == {"web", "reddit", "hn", "leads"}
    assert tools["web"].name == "web"
    assert tools["reddit"].name == "reddit"
    assert tools["hn"].name == "hn"
    assert tools["leads"].name == "leads"


async def test_misconfigured_tools_raise_their_config_error_at_search_time() -> None:
    tools = build_default_tools(
        make_settings(tavily_api_key="", reddit_client_id="", reddit_client_secret="")
    )
    with pytest.raises(ResearchUnavailable):
        await tools["web"].search("query")
    with pytest.raises(ResearchUnavailable):
        await tools["reddit"].search("query")
    with pytest.raises(ToolDisabled):
        await tools["leads"].search("query")


async def test_tool_without_a_session_factory_still_searches() -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get("https://hn.algolia.com/api/v1/search").mock(
            return_value=httpx.Response(200, json=HACKERNEWS_JSON)
        )
        tools = build_default_tools(make_settings())
        items = await tools["hn"].search("dog walking scheduler")

    assert items
    assert items[0].source == "hn"


async def test_transient_failure_never_escapes_a_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(adapters, "RETRY_WAIT", wait_none())
    with respx.mock(assert_all_called=False) as router:
        route = router.get("https://hn.algolia.com/api/v1/search").mock(
            return_value=httpx.Response(500, text="boom")
        )
        tools = build_default_tools(make_settings())
        assert await tools["hn"].search("query") == []

    assert route.call_count == 3
