"""Unit tests for the pipeline step graph and cost helpers (no DB, no network)."""

from __future__ import annotations

import pytest

from app.cost import CostMeter
from app.jev import DimensionScore, Scorecard
from app.pipeline.engine import (
    DIMENSION_OWNER_STEP,
    RESEARCH_STEPS,
    SECTION_STEPS,
    STEP_DEPENDENCIES,
    STEP_ESTIMATE_TOTAL_USD,
    STEP_ESTIMATES_USD,
    STEP_ORDER,
    downstream_steps,
    estimate_for_step,
    is_over_cap,
    merge_scorecards,
    plan_research_steps,
    should_stop_for_cost,
)


def test_step_order_and_dependencies_are_consistent() -> None:
    assert STEP_ORDER[0] == "refine"
    assert STEP_ORDER[-1] == "critic"
    assert set(STEP_DEPENDENCIES) == set(STEP_ORDER)
    for step, dependencies in STEP_DEPENDENCIES.items():
        for dependency in dependencies:
            assert STEP_ORDER.index(dependency) < STEP_ORDER.index(step)
    assert RESEARCH_STEPS == ("market", "competitors", "customers")
    assert set(SECTION_STEPS) <= set(STEP_ORDER)
    assert set(DIMENSION_OWNER_STEP.values()) <= set(STEP_ORDER)


def test_downstream_steps_closure() -> None:
    assert downstream_steps("refine") == [
        "clarify",
        "market",
        "competitors",
        "customers",
        "feasibility",
        "business_model",
        "critic",
    ]
    assert downstream_steps("clarify") == ["critic"]
    assert downstream_steps("market") == ["feasibility", "business_model", "critic"]
    assert downstream_steps("competitors") == ["feasibility", "business_model", "critic"]
    assert downstream_steps("customers") == ["feasibility", "business_model", "critic"]
    assert downstream_steps("feasibility") == ["business_model", "critic"]
    assert downstream_steps("business_model") == ["critic"]
    assert downstream_steps("critic") == []


def test_downstream_steps_rejects_unknown_step() -> None:
    with pytest.raises(ValueError):
        downstream_steps("not-a-step")


def test_step_estimates_are_sane_and_under_the_default_cap() -> None:
    assert set(STEP_ESTIMATES_USD) == set(STEP_ORDER)
    assert all(estimate > 0 for estimate in STEP_ESTIMATES_USD.values())
    assert round(sum(STEP_ESTIMATES_USD.values()), 4) == STEP_ESTIMATE_TOTAL_USD
    assert STEP_ESTIMATE_TOTAL_USD < 0.75
    assert estimate_for_step("market") == STEP_ESTIMATES_USD["market"]
    assert estimate_for_step("unknown") == 0.0


def test_should_stop_for_cost_respects_the_meter_and_the_cap() -> None:
    meter = CostMeter(cap_usd=0.10)
    assert not should_stop_for_cost(meter, "market")
    meter.add(0.08, category="test")
    assert should_stop_for_cost(meter, "market")
    assert not should_stop_for_cost(meter, "unknown")

    uncapped = CostMeter()
    uncapped.add(10.0, category="test")
    assert not should_stop_for_cost(uncapped, "market")
    assert not is_over_cap(uncapped)


def test_is_over_cap_flags_only_real_overspend() -> None:
    assert not is_over_cap(CostMeter(cap_usd=0.10, spent_usd=0.10))
    assert is_over_cap(CostMeter(cap_usd=0.10, spent_usd=0.100001))
    assert not is_over_cap(CostMeter(cap_usd=0.0, spent_usd=99.0))


def test_plan_research_steps_reserves_concurrent_estimates_in_order() -> None:
    roomy = CostMeter(cap_usd=0.2)
    runnable, blocked = plan_research_steps(roomy, RESEARCH_STEPS)
    assert runnable == list(RESEARCH_STEPS)
    assert blocked == []

    two_steps = CostMeter(cap_usd=0.061)
    runnable, blocked = plan_research_steps(two_steps, RESEARCH_STEPS)
    assert runnable == ["market", "competitors"]
    assert blocked == ["customers"]

    one_step = CostMeter(cap_usd=0.035)
    runnable, blocked = plan_research_steps(one_step, RESEARCH_STEPS)
    assert runnable == ["market"]
    assert blocked == ["competitors", "customers"]

    already_spent = CostMeter(cap_usd=0.04, spent_usd=0.02)
    runnable, blocked = plan_research_steps(already_spent, RESEARCH_STEPS)
    assert runnable == []
    assert blocked == list(RESEARCH_STEPS)

    uncapped = CostMeter()
    runnable, blocked = plan_research_steps(uncapped, RESEARCH_STEPS)
    assert runnable == list(RESEARCH_STEPS)
    assert blocked == []


def _scorecard(confidence: float, score: float = 4.0) -> Scorecard:
    return Scorecard(
        dimensions=[
            DimensionScore(dimension="problem_severity", score=3.0, confidence=0.9, source="jev"),
            DimensionScore(
                dimension="market_evidence", score=score, confidence=confidence, source="jev"
            ),
            DimensionScore(
                dimension="competition_intensity", score=2.0, confidence=0.9, source="jev"
            ),
            DimensionScore(
                dimension="customer_reachability", score=2.0, confidence=0.9, source="jev"
            ),
            DimensionScore(dimension="feasibility", score=2.0, confidence=0.9, source="jev"),
            DimensionScore(
                dimension="monetization_clarity", score=2.0, confidence=0.9, source="jev"
            ),
        ]
    )


def test_merge_scorecards_keeps_new_scores_only_for_flagged_dimensions() -> None:
    previous = _scorecard(0.2, score=2.0)
    updated = _scorecard(0.9, score=5.0)
    merged = merge_scorecards(previous, updated, ["market_evidence"])
    by_dimension = {score.dimension: score for score in merged.dimensions}
    assert by_dimension["market_evidence"].confidence == 0.9
    assert by_dimension["market_evidence"].score == 5.0
    assert by_dimension["problem_severity"] == previous.dimensions[0]

    untouched = merge_scorecards(previous, updated, [])
    assert untouched == previous


def test_merge_scorecards_keeps_order_and_completeness() -> None:
    merged = merge_scorecards(_scorecard(0.2), _scorecard(0.9), ["market_evidence"])
    assert [score.dimension for score in merged.dimensions] == [
        "problem_severity",
        "market_evidence",
        "competition_intensity",
        "customer_reachability",
        "feasibility",
        "monetization_clarity",
    ]
