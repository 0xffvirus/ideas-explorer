"""Adapter tests against recorded provider fixtures, with no network access."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx
from tenacity import wait_none

import app.research.adapters as adapters
from app.config import Settings, settings_as_test_overrides
from app.cost import CostMeter
from app.research import CompanyLead, LeadFinder, ResearchUnavailable, ToolDisabled
from app.research.adapters.hackernews import HackerNewsProvider, normalize_points
from app.research.adapters.reddit import RedditProvider, normalize_upvotes
from app.research.adapters.tavily import TavilyProvider

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "research"

TAVILY_JSON = json.loads((FIXTURES / "tavily_search.json").read_text())
REDDIT_TOKEN_JSON = json.loads((FIXTURES / "reddit_token.json").read_text())
REDDIT_SEARCH_JSON = json.loads((FIXTURES / "reddit_search.json").read_text())
HACKERNEWS_JSON = json.loads((FIXTURES / "hackernews_search.json").read_text())

SETTINGS_DEFAULTS: dict[str, object] = {
    "tavily_api_key": "test-tavily-key",
    "reddit_client_id": "test-client-id",
    "reddit_client_secret": "test-client-secret",
    "reddit_user_agent": "idea-forge-tests/0.1",
    "research_timeout_seconds": 1.0,
    "research_max_retries": 2,
}


def make_settings(**overrides: object) -> Settings:
    return settings_as_test_overrides(**{**SETTINGS_DEFAULTS, **overrides})


async def test_tavily_maps_recorded_results_to_evidence() -> None:
    with respx.mock(assert_all_called=False) as router:
        route = router.post("https://api.tavily.com/search").mock(
            return_value=httpx.Response(200, json=TAVILY_JSON)
        )
        provider = TavilyProvider(make_settings(), http_client=httpx.AsyncClient())
        items = await provider.search("pet care market size", limit=5)

    assert route.call_count == 1
    assert len(items) == 3

    first = items[0]
    assert first.source == "web"
    assert str(first.url) == "https://www.grandviewresearch.com/industry-analysis/pet-care-market"
    assert first.title == "Pet Care Market Size, Share & Trends Analysis"
    assert first.snippet == (
        "Pet care market size was estimated at USD 246.66 billion in 2023 & is expected to "
        "grow at a CAGR of 6.1% from 2024 to 2030. Source: Grand View Research."
    )
    assert first.score == pytest.approx(0.94)
    assert first.published_at == datetime(2024, 1, 15, tzinfo=UTC)

    assert items[1].published_at == datetime(2024, 3, 14, 9, 30, tzinfo=UTC)
    assert items[1].score == pytest.approx(0.81)

    assert items[2].published_at is None
    assert items[2].score == pytest.approx(0.55)


async def test_tavily_sends_the_documented_request_body() -> None:
    with respx.mock(assert_all_called=False) as router:
        route = router.post("https://api.tavily.com/search").mock(
            return_value=httpx.Response(200, json=TAVILY_JSON)
        )
        provider = TavilyProvider(make_settings(), http_client=httpx.AsyncClient())
        await provider.search("query text", limit=3)

    body = json.loads(route.calls[0].request.content)
    assert body == {
        "api_key": "test-tavily-key",
        "query": "query text",
        "max_results": 3,
        "include_answer": False,
    }


async def test_tavily_without_api_key_raises_research_unavailable() -> None:
    provider = TavilyProvider(make_settings(tavily_api_key=""), http_client=httpx.AsyncClient())
    with pytest.raises(ResearchUnavailable):
        await provider.search("query")


async def test_tavily_charges_the_meter_on_successful_http_searches() -> None:
    meter = CostMeter()
    with respx.mock(assert_all_called=False) as router:
        router.post("https://api.tavily.com/search").mock(
            return_value=httpx.Response(200, json=TAVILY_JSON)
        )
        provider = TavilyProvider(
            make_settings(tavily_cost_per_search_usd=0.008),
            http_client=httpx.AsyncClient(),
            meter=meter,
        )
        await provider.search("query")
    assert meter.by_category["web"] == pytest.approx(0.008)
    assert meter.spent_usd == pytest.approx(0.008)


async def test_tavily_429_storm_runs_bounded_attempts_then_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(adapters, "RETRY_WAIT", wait_none())
    with respx.mock(assert_all_called=False) as router:
        route = router.post("https://api.tavily.com/search").mock(
            return_value=httpx.Response(429, text="slow down")
        )
        provider = TavilyProvider(
            make_settings(research_max_retries=2), http_client=httpx.AsyncClient()
        )
        items = await provider.search("query")

    assert items == []
    assert route.call_count == 3


async def test_tavily_5xx_storm_returns_empty_and_does_not_charge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(adapters, "RETRY_WAIT", wait_none())
    meter = CostMeter()
    with respx.mock(assert_all_called=False) as router:
        route = router.post("https://api.tavily.com/search").mock(
            return_value=httpx.Response(503, text="upstream down")
        )
        provider = TavilyProvider(make_settings(), http_client=httpx.AsyncClient(), meter=meter)
        assert await provider.search("query") == []

    assert route.call_count == 3
    assert meter.by_category == {}


async def test_tavily_non_retryable_4xx_returns_empty_without_retrying(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(adapters, "RETRY_WAIT", wait_none())
    with respx.mock(assert_all_called=False) as router:
        route = router.post("https://api.tavily.com/search").mock(
            return_value=httpx.Response(403, text="forbidden")
        )
        provider = TavilyProvider(make_settings(), http_client=httpx.AsyncClient())
        assert await provider.search("query") == []

    assert route.call_count == 1


async def test_tavily_transport_error_returns_empty_after_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(adapters, "RETRY_WAIT", wait_none())
    with respx.mock(assert_all_called=False) as router:
        route = router.post("https://api.tavily.com/search").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        provider = TavilyProvider(make_settings(), http_client=httpx.AsyncClient())
        assert await provider.search("query") == []

    assert route.call_count == 3


async def test_reddit_fetches_a_token_then_maps_search_results() -> None:
    with respx.mock(assert_all_called=False) as router:
        token_route = router.post("https://www.reddit.com/api/v1/access_token").mock(
            return_value=httpx.Response(200, json=REDDIT_TOKEN_JSON)
        )
        search_route = router.get("https://oauth.reddit.com/search").mock(
            return_value=httpx.Response(200, json=REDDIT_SEARCH_JSON)
        )
        provider = RedditProvider(make_settings(), http_client=httpx.AsyncClient())
        items = await provider.search("dog walker", limit=10)

    assert token_route.call_count == 1
    assert search_route.call_count == 1

    token_request = token_route.calls[0].request
    assert token_request.headers["authorization"].startswith("Basic ")
    assert token_request.headers["user-agent"] == "idea-forge-tests/0.1"
    assert token_request.content == b"grant_type=client_credentials"

    search_request = search_route.calls[0].request
    assert search_request.headers["authorization"] == "bearer fake-token"
    assert search_request.headers["user-agent"] == "idea-forge-tests/0.1"
    assert search_request.url.params["q"] == "dog walker"
    assert search_request.url.params["limit"] == "10"
    assert search_request.url.params["sort"] == "relevance"
    assert search_request.url.params["raw_json"] == "1"

    first = items[0]
    assert first.source == "reddit"
    assert str(first.url) == (
        "https://www.reddit.com/r/dogs/comments/abc123/i_can_never_find_a_reliable_dog_walker/"
    )
    assert first.title == "I can never find a reliable dog walker"
    assert first.snippet == "Every app I try is flaky & expensive. I just want someone trustworthy."
    assert first.published_at == datetime.fromtimestamp(1710000000, tz=UTC)
    assert first.score == pytest.approx(0.75)

    second = items[1]
    assert second.snippet == "What do you use to track vet appointments?"
    assert second.score == pytest.approx(3 / 28)


async def test_reddit_reuses_the_token_across_searches() -> None:
    with respx.mock(assert_all_called=False) as router:
        token_route = router.post("https://www.reddit.com/api/v1/access_token").mock(
            return_value=httpx.Response(200, json=REDDIT_TOKEN_JSON)
        )
        search_route = router.get("https://oauth.reddit.com/search").mock(
            return_value=httpx.Response(200, json=REDDIT_SEARCH_JSON)
        )
        provider = RedditProvider(make_settings(), http_client=httpx.AsyncClient())
        await provider.search("first query")
        await provider.search("second query")

    assert token_route.call_count == 1
    assert search_route.call_count == 2
    assert search_route.calls[0].request.headers["authorization"] == "bearer fake-token"
    assert search_route.calls[1].request.headers["authorization"] == "bearer fake-token"


async def test_reddit_refetches_the_token_when_search_rejects_it() -> None:
    with respx.mock(assert_all_called=False) as router:
        token_route = router.post("https://www.reddit.com/api/v1/access_token").mock(
            side_effect=[
                httpx.Response(200, json={"access_token": "stale-token", "expires_in": 3600}),
                httpx.Response(200, json={"access_token": "fresh-token", "expires_in": 3600}),
            ]
        )
        search_route = router.get("https://oauth.reddit.com/search").mock(
            side_effect=[
                httpx.Response(401, json={"message": "Unauthorized"}),
                httpx.Response(200, json=REDDIT_SEARCH_JSON),
            ]
        )
        provider = RedditProvider(make_settings(), http_client=httpx.AsyncClient())
        items = await provider.search("dog walker")

    assert token_route.call_count == 2
    assert search_route.call_count == 2
    assert search_route.calls[0].request.headers["authorization"] == "bearer stale-token"
    assert search_route.calls[1].request.headers["authorization"] == "bearer fresh-token"
    assert items
    assert items[0].source == "reddit"


class _FakeClock:
    """Stand-in for the ``time`` module with a controllable monotonic clock."""

    def __init__(self, now: float) -> None:
        self.now = now

    def monotonic(self) -> float:
        return self.now


async def test_reddit_refreshes_the_token_only_after_its_expiry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _FakeClock(1000.0)
    monkeypatch.setattr("app.research.adapters.reddit.time", clock)
    with respx.mock(assert_all_called=False) as router:
        token_route = router.post("https://www.reddit.com/api/v1/access_token").mock(
            side_effect=[
                httpx.Response(200, json={**REDDIT_TOKEN_JSON, "access_token": "first-token"}),
                httpx.Response(200, json={**REDDIT_TOKEN_JSON, "access_token": "second-token"}),
            ]
        )
        search_route = router.get("https://oauth.reddit.com/search").mock(
            return_value=httpx.Response(200, json=REDDIT_SEARCH_JSON)
        )
        provider = RedditProvider(make_settings(), http_client=httpx.AsyncClient())
        await provider.search("first query")

        clock.now = 1000.0 + 3600.0 - 60.0 - 1.0
        await provider.search("second query")

        clock.now = 1000.0 + 3600.0 - 60.0 + 1.0
        await provider.search("third query")

    assert token_route.call_count == 2
    assert [call.request.headers["authorization"] for call in search_route.calls] == [
        "bearer first-token",
        "bearer first-token",
        "bearer second-token",
    ]


async def test_reddit_refetches_the_token_after_a_rejected_token_response() -> None:
    with respx.mock(assert_all_called=False) as router:
        token_route = router.post("https://www.reddit.com/api/v1/access_token").mock(
            side_effect=[
                httpx.Response(401, text="invalid credentials"),
                httpx.Response(200, json=REDDIT_TOKEN_JSON),
            ]
        )
        search_route = router.get("https://oauth.reddit.com/search").mock(
            return_value=httpx.Response(200, json=REDDIT_SEARCH_JSON)
        )
        provider = RedditProvider(make_settings(), http_client=httpx.AsyncClient())
        assert await provider.search("first query") == []
        items = await provider.search("second query")

    assert token_route.call_count == 2
    assert search_route.call_count == 1
    assert items


async def test_reddit_429_storm_runs_bounded_attempts_then_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(adapters, "RETRY_WAIT", wait_none())
    with respx.mock(assert_all_called=False) as router:
        token_route = router.post("https://www.reddit.com/api/v1/access_token").mock(
            return_value=httpx.Response(200, json=REDDIT_TOKEN_JSON)
        )
        search_route = router.get("https://oauth.reddit.com/search").mock(
            return_value=httpx.Response(429, text="slow down")
        )
        provider = RedditProvider(
            make_settings(research_max_retries=2), http_client=httpx.AsyncClient()
        )
        items = await provider.search("query")

    assert items == []
    assert token_route.call_count == 1
    assert search_route.call_count == 3


async def test_reddit_without_credentials_raises_research_unavailable() -> None:
    provider = RedditProvider(
        make_settings(reddit_client_id="", reddit_client_secret=""),
        http_client=httpx.AsyncClient(),
    )
    with pytest.raises(ResearchUnavailable):
        await provider.search("query")


async def test_hackernews_maps_recorded_hits() -> None:
    with respx.mock(assert_all_called=False) as router:
        route = router.get("https://hn.algolia.com/api/v1/search").mock(
            return_value=httpx.Response(200, json=HACKERNEWS_JSON)
        )
        provider = HackerNewsProvider(make_settings(), http_client=httpx.AsyncClient())
        items = await provider.search("dog walking scheduler", limit=2)

    assert route.call_count == 1
    params = route.calls[0].request.url.params
    assert params["query"] == "dog walking scheduler"
    assert params["tags"] == "story"
    assert params["hitsPerPage"] == "2"
    assert "authorization" not in route.calls[0].request.headers

    first = items[0]
    assert first.source == "hn"
    assert str(first.url) == "https://example.com/show-hn-dog-walker"
    assert first.title == "Show HN: I built a dog walking scheduler"
    assert first.snippet == "We got tired of spreadsheets & built this."
    assert first.published_at == datetime(2024, 2, 1, 15, 0, tzinfo=UTC)
    assert first.score == pytest.approx(0.5)

    second = items[1]
    assert str(second.url) == "https://news.ycombinator.com/item?id=39000002"
    assert second.snippet == "Ask HN: How do you vet pet sitters?"
    assert second.score == pytest.approx(0.15)


async def test_hackernews_missing_fields_and_bad_dates_map_gracefully() -> None:
    payload = {
        "hits": [
            {"objectID": "1", "title": "No url, no points", "created_at": "not-a-date"},
            {
                "objectID": "2",
                "story_text": "Body only",
                "created_at": "2024-02-01T15:00:00.000Z",
            },
            {"objectID": "3"},
            "not-a-mapping",
        ]
    }
    with respx.mock(assert_all_called=False) as router:
        route = router.get("https://hn.algolia.com/api/v1/search").mock(
            return_value=httpx.Response(200, json=payload)
        )
        provider = HackerNewsProvider(make_settings(), http_client=httpx.AsyncClient())
        items = await provider.search("sparse hits", limit=10)

    assert route.call_count == 1
    assert len(items) == 3

    assert items[0].title == "No url, no points"
    assert str(items[0].url) == "https://news.ycombinator.com/item?id=1"
    assert items[0].published_at is None
    assert items[0].score is None

    assert items[1].title == ""
    assert str(items[1].url) == "https://news.ycombinator.com/item?id=2"
    assert items[1].snippet == "Body only"
    assert items[1].published_at == datetime(2024, 2, 1, 15, 0, tzinfo=UTC)

    assert items[2].title == ""
    assert items[2].snippet == ""
    assert str(items[2].url) == "https://news.ycombinator.com/item?id=3"


async def test_hackernews_non_list_hits_returns_empty() -> None:
    with respx.mock(assert_all_called=False) as router:
        route = router.get("https://hn.algolia.com/api/v1/search").mock(
            return_value=httpx.Response(200, json={"hits": "not-a-list"})
        )
        provider = HackerNewsProvider(make_settings(), http_client=httpx.AsyncClient())
        assert await provider.search("query") == []
    assert route.call_count == 1


class RecordingLimiter:
    """Rate-limiter double that counts the acquisitions it saw."""

    def __init__(self) -> None:
        self.calls = 0

    async def acquire(self, tokens: float = 1.0) -> None:
        self.calls += 1


async def test_hackernews_acquires_the_rate_limiter_once_per_http_call() -> None:
    limiter = RecordingLimiter()
    with respx.mock(assert_all_called=False) as router:
        route = router.get("https://hn.algolia.com/api/v1/search").mock(
            return_value=httpx.Response(200, json=HACKERNEWS_JSON)
        )
        provider = HackerNewsProvider(
            make_settings(), http_client=httpx.AsyncClient(), limiter=limiter
        )
        await provider.search("first query")
        await provider.search("second query")

    assert route.call_count == 2
    assert limiter.calls == 2


def test_score_normalization_formulas() -> None:
    assert normalize_upvotes(75) == pytest.approx(0.75)
    assert normalize_upvotes(0) == 0.0
    assert normalize_upvotes(-10) == 0.0
    assert 0.99 < normalize_upvotes(1_000_000) < 1.0
    assert normalize_points(150) == pytest.approx(0.5)
    assert normalize_points(600) == 1.0
    assert normalize_points(0) == 0.0


class FakeLeadProvider:
    name = "fake-leads"

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def find(self, query: str, *, limit: int = 8) -> list[CompanyLead]:
        self.calls.append((query, limit))
        return [
            CompanyLead(
                name="Acme Robotics",
                domain="acme.example",
                industry="Industrial automation",
                size_band="51-200",
                country="US",
                why_fit="Integrates robot arms for mid-size manufacturers.",
                url="https://acme.example/about",
            )
        ]


async def test_lead_finder_is_disabled_by_default() -> None:
    finder = LeadFinder(make_settings(leads_enabled=False))
    with pytest.raises(ToolDisabled):
        await finder.search("robot arm buyers")
    with pytest.raises(ToolDisabled):
        await finder.find_leads("robot arm buyers")


async def test_lead_finder_enabled_without_a_provider_raises_unavailable() -> None:
    finder = LeadFinder(make_settings(leads_enabled=True))
    with pytest.raises(ResearchUnavailable):
        await finder.search("robot arm buyers")
    with pytest.raises(ResearchUnavailable):
        await finder.find_leads("robot arm buyers")


async def test_lead_finder_maps_company_leads_to_evidence() -> None:
    provider = FakeLeadProvider()
    finder = LeadFinder(make_settings(leads_enabled=True), provider)

    leads = await finder.find_leads("robot arm buyers", limit=5)
    assert [lead.name for lead in leads] == ["Acme Robotics"]
    assert provider.calls == [("robot arm buyers", 5)]

    items = await finder.search("robot arm buyers")
    assert items[0].source == "leads"
    assert str(items[0].url) == "https://acme.example/about"
    assert items[0].title == "Acme Robotics"
    assert "Industrial automation" in items[0].snippet
    assert "51-200" in items[0].snippet
    assert "US" in items[0].snippet
