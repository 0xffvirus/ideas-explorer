"""Unit tests for the lead DB adapter (disabled by default)."""

from __future__ import annotations

import pytest

from app.cost import CostMeter
from app.research.adapters.leads import LeadFinder
from app.research.cache import InMemoryCache
from app.research.contract import CompanyLead, ToolDisabled

LEAD = CompanyLead(
    name="Acme Pet Co",
    domain="acmepet.com",
    industry="Pet services",
    size_band="11-50",
    country="US",
    why_fit="Expanding into on-demand care",
)

LEAD_WITH_URL = CompanyLead(
    name="Beta Vets",
    domain=None,
    url="https://beta-vets.example.com",
    why_fit=None,
)


class FakeLeadProvider:
    def __init__(self, leads: list[CompanyLead], *, error: Exception | None = None) -> None:
        self.leads = leads
        self.error = error
        self.calls = 0

    async def find(self, query: str, *, limit: int) -> list[CompanyLead]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.leads[:limit]


class RecordingLimiter:
    def __init__(self) -> None:
        self.acquires = 0

    async def acquire(self, tokens: float = 1.0) -> None:
        self.acquires += 1


def make_tool(
    provider: FakeLeadProvider | None,
    *,
    enabled: bool = True,
    limiter: RecordingLimiter | None = None,
    meter: CostMeter | None = None,
    cost_per_search_usd: float = 0.0,
) -> LeadFinder:
    return LeadFinder(
        enabled=enabled,
        cache=InMemoryCache(),
        provider=provider,
        rate_limiter=limiter,
        meter=meter,
        cost_per_search_usd=cost_per_search_usd,
    )


async def test_disabled_adapter_raises_tool_disabled() -> None:
    tool = make_tool(None, enabled=False)
    assert tool.enabled is False
    with pytest.raises(ToolDisabled):
        await tool.search("vets")
    with pytest.raises(ToolDisabled):
        await tool.find_companies("vets")


async def test_enabled_adapter_maps_leads_to_evidence() -> None:
    tool = make_tool(FakeLeadProvider([LEAD, LEAD_WITH_URL]))
    items = await tool.search("vets")

    assert len(items) == 2
    first, second = items
    assert first.source == "leads"
    assert str(first.url) == "https://acmepet.com/"
    assert first.title == "Acme Pet Co"
    assert first.snippet == "Expanding into on-demand care"
    assert first.score is None
    assert first.published_at is None

    assert str(second.url) == "https://beta-vets.example.com/"
    assert second.snippet == "Beta Vets"


async def test_search_is_cached_per_query() -> None:
    provider = FakeLeadProvider([LEAD])
    tool = make_tool(provider)
    first = await tool.search("vets")
    second = await tool.search("vets")

    assert provider.calls == 1
    assert [str(item.url) for item in first] == [str(item.url) for item in second]


async def test_enabled_without_provider_returns_no_leads() -> None:
    tool = make_tool(None)
    assert await tool.search("vets") == []
    assert await tool.find_companies("vets") == []


async def test_leads_without_url_or_domain_are_skipped() -> None:
    provider = FakeLeadProvider([CompanyLead(name="No Web Presence")])
    tool = make_tool(provider)
    assert await tool.search("vets") == []
    assert await tool.find_companies("vets") == [CompanyLead(name="No Web Presence")]


async def test_snippet_falls_back_to_company_details() -> None:
    lead = CompanyLead(
        name="Gamma Vets",
        domain="gamma.example.com",
        industry="Vet",
        size_band="1-10",
        country="UK",
    )
    tool = make_tool(FakeLeadProvider([lead]))
    items = await tool.search("vets")
    assert items[0].snippet == "Vet · 1-10 · UK"


async def test_find_companies_returns_typed_leads() -> None:
    provider = FakeLeadProvider([LEAD, LEAD_WITH_URL])
    tool = make_tool(provider)
    leads = await tool.find_companies("vets")
    assert leads == [LEAD, LEAD_WITH_URL]


async def test_blank_query_and_non_positive_limit_skip_provider() -> None:
    provider = FakeLeadProvider([LEAD])
    tool = make_tool(provider)
    assert await tool.search("   ") == []
    assert await tool.search("vets", limit=0) == []
    assert await tool.find_companies("vets", limit=-1) == []
    assert provider.calls == 0


async def test_rate_limiter_is_acquired_per_provider_call() -> None:
    limiter = RecordingLimiter()
    provider = FakeLeadProvider([LEAD])
    tool = make_tool(provider, limiter=limiter)

    await tool.search("vets")
    await tool.find_companies("vets")

    assert provider.calls == 2
    assert limiter.acquires == 2


async def test_provider_calls_are_charged() -> None:
    meter = CostMeter(cap_usd=1.0)
    tool = make_tool(FakeLeadProvider([LEAD]), meter=meter, cost_per_search_usd=0.05)

    await tool.search("vets")
    assert meter.spent_usd == pytest.approx(0.05)
    assert meter.by_category["research:leads"] == pytest.approx(0.05)


async def test_provider_failure_returns_empty_without_raising() -> None:
    provider = FakeLeadProvider([LEAD], error=RuntimeError("provider down"))
    tool = make_tool(provider)
    assert await tool.search("vets") == []
    assert await tool.find_companies("vets") == []


async def test_provider_failure_still_raises_when_disabled() -> None:
    provider = FakeLeadProvider([LEAD], error=RuntimeError("provider down"))
    tool = make_tool(provider, enabled=False)
    with pytest.raises(ToolDisabled):
        await tool.search("vets")
