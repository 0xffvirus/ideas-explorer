"""Unit tests for the shared CostMeter used by research adapters."""

from __future__ import annotations

import pytest

from app.config import ModelPrice
from app.cost import CostMeter


def test_add_tracks_total_and_categories() -> None:
    meter = CostMeter(cap_usd=1.0)
    meter.add(0.25, category="research:web")
    meter.add(0.10, category="llm")
    assert meter.spent_usd == pytest.approx(0.35)
    assert meter.by_category["research:web"] == pytest.approx(0.25)
    assert meter.remaining_usd == pytest.approx(0.65)


def test_would_exceed_and_uncapped_meter() -> None:
    meter = CostMeter(cap_usd=0.5)
    assert not meter.would_exceed(0.5)
    assert meter.would_exceed(0.51)
    uncapped = CostMeter(cap_usd=0)
    assert not uncapped.would_exceed(1_000_000.0)
    assert uncapped.remaining_usd == float("inf")


def test_charge_tokens_uses_pricing_table() -> None:
    meter = CostMeter()
    pricing = {"openai:gpt-4o": ModelPrice(input=2.5, output=10.0)}
    usd = meter.charge_tokens(
        model="openai:gpt-4o",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        category="llm",
        pricing=pricing,
    )
    assert usd == pytest.approx(12.5)
    assert meter.spent_usd == pytest.approx(12.5)


def test_negative_cost_is_rejected() -> None:
    with pytest.raises(ValueError):
        CostMeter().add(-0.1, category="x")
