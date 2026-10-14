"""Unit tests for the toolkit factory and lifecycle."""

from __future__ import annotations

import httpx
import pytest

from app.config import settings_as_test_overrides
from app.research import ToolDisabled, build_research_tools


async def test_builds_all_four_tools() -> None:
    toolkit = build_research_tools(settings_as_test_overrides())
    try:
        assert {tool.name for tool in toolkit.all()} == {"web", "reddit", "hn", "leads"}
        assert toolkit.by_name("hn") is toolkit.hn
        with pytest.raises(KeyError):
            toolkit.by_name("nope")
    finally:
        await toolkit.aclose()


async def test_injected_client_is_not_closed() -> None:
    async with httpx.AsyncClient() as client:
        toolkit = build_research_tools(settings_as_test_overrides(), client=client)
        await toolkit.aclose()
        assert not client.is_closed


async def test_owned_client_is_closed() -> None:
    toolkit = build_research_tools(settings_as_test_overrides())
    client = toolkit._owned_client
    assert client is not None
    assert not client.is_closed
    await toolkit.aclose()
    assert client.is_closed


async def test_leads_disabled_by_default_and_enabled_via_settings() -> None:
    disabled = build_research_tools(settings_as_test_overrides())
    try:
        assert disabled.leads.enabled is False
        with pytest.raises(ToolDisabled):
            await disabled.leads.search("vets")
    finally:
        await disabled.aclose()

    enabled = build_research_tools(settings_as_test_overrides(leads_enabled=True))
    try:
        assert enabled.leads.enabled is True
    finally:
        await enabled.aclose()


async def test_ttls_come_from_settings() -> None:
    settings = settings_as_test_overrides(research_web_ttl_hours=1, research_community_ttl_hours=2)
    toolkit = build_research_tools(settings)
    try:
        assert toolkit.web.ttl_seconds == 3600
        assert toolkit.reddit.ttl_seconds == 7200
        assert toolkit.hn.ttl_seconds == 7200
        assert toolkit.leads.ttl_seconds == 3600
    finally:
        await toolkit.aclose()


async def test_leads_limiter_and_meter_are_wired() -> None:
    from app.cost import CostMeter

    meter = CostMeter(cap_usd=1.0)
    toolkit = build_research_tools(settings_as_test_overrides(leads_enabled=True), meter=meter)
    try:
        assert toolkit.leads._rate_limiter is not None
        assert toolkit.leads._meter is meter
        assert toolkit.web._rate_limiter is not toolkit.leads._rate_limiter
    finally:
        await toolkit.aclose()


async def test_lead_provider_can_be_wired() -> None:
    from app.research.contract import CompanyLead

    class Provider:
        async def find(self, query: str, *, limit: int) -> list[CompanyLead]:
            return [CompanyLead(name="Acme", domain="acme.example.com")]

    toolkit = build_research_tools(
        settings_as_test_overrides(leads_enabled=True), lead_provider=Provider()
    )
    try:
        leads = await toolkit.leads.find_companies("vets")
        assert [lead.name for lead in leads] == ["Acme"]
    finally:
        await toolkit.aclose()
