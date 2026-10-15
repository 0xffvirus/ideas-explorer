"""Step graph and pure cost helpers for the pipeline engine.

Step order, dependency edges, downstream closure, and the per-step USD
estimates used by the cost-cap guard. Everything here is pure and unit-tested
without a database.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.cost import CostMeter
from app.jev import DimensionName, DimensionScore, Scorecard

STEP_ORDER: tuple[str, ...] = (
    "refine",
    "clarify",
    "market",
    "competitors",
    "customers",
    "feasibility",
    "business_model",
    "critic",
)

STEP_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "refine": (),
    "clarify": ("refine",),
    "market": ("refine",),
    "competitors": ("refine",),
    "customers": ("refine",),
    "feasibility": ("market", "competitors", "customers"),
    "business_model": ("feasibility",),
    "critic": (
        "refine",
        "clarify",
        "market",
        "competitors",
        "customers",
        "feasibility",
        "business_model",
    ),
}

RESEARCH_STEPS: tuple[str, ...] = ("market", "competitors", "customers")

SECTION_STEPS: tuple[str, ...] = (
    "market",
    "competitors",
    "customers",
    "feasibility",
    "business_model",
)

DIMENSION_OWNER_STEP: dict[DimensionName, str] = {
    "problem_severity": "refine",
    "market_evidence": "market",
    "competition_intensity": "competitors",
    "customer_reachability": "customers",
    "feasibility": "feasibility",
    "monetization_clarity": "business_model",
}

STEP_ESTIMATES_USD: dict[str, float] = {
    "refine": 0.010,
    "clarify": 0.005,
    "market": 0.030,
    "competitors": 0.030,
    "customers": 0.040,
    "feasibility": 0.030,
    "business_model": 0.030,
    "critic": 0.020,
}

STEP_ESTIMATE_TOTAL_USD = round(sum(STEP_ESTIMATES_USD.values()), 4)


def downstream_steps(step: str) -> list[str]:
    """Return the steps that transitively depend on ``step``, in step order.

    Raises ``ValueError`` for an unknown step name.
    """
    if step not in STEP_DEPENDENCIES:
        raise ValueError(f"unknown pipeline step {step!r}")
    affected: set[str] = set()
    frontier = [step]
    while frontier:
        current = frontier.pop()
        for candidate, dependencies in STEP_DEPENDENCIES.items():
            if current in dependencies and candidate not in affected:
                affected.add(candidate)
                frontier.append(candidate)
    return [name for name in STEP_ORDER if name in affected]


def estimate_for_step(step: str) -> float:
    """USD estimate for one step; unknown steps cost nothing."""
    return STEP_ESTIMATES_USD.get(step, 0.0)


def should_stop_for_cost(meter: CostMeter, next_step: str) -> bool:
    """True when starting ``next_step`` could push spend past the cap."""
    return meter.would_exceed(estimate_for_step(next_step))


def plan_research_steps(meter: CostMeter, pending: Sequence[str]) -> tuple[list[str], list[str]]:
    """Split pending research steps into runnable and blocked under the cap.

    The three research steps are launched concurrently, so each runnable step
    reserves its own estimate while walking in order. A step is blocked when
    ``spent + reserve + estimate`` would exceed the cap, keeping the promised
    bound of never overspending by more than one step's estimate.
    """
    runnable: list[str] = []
    blocked: list[str] = []
    reserve = 0.0
    for step in pending:
        estimate = estimate_for_step(step)
        if meter.cap_usd > 0 and meter.spent_usd + reserve + estimate > meter.cap_usd:
            blocked.append(step)
            continue
        runnable.append(step)
        reserve += estimate
    return runnable, blocked


def is_over_cap(meter: CostMeter) -> bool:
    """True when the meter has already spent past its cap (cap > 0 only)."""
    return meter.cap_usd > 0 and meter.spent_usd > meter.cap_usd


def merge_scorecards(
    previous: Scorecard,
    updated: Scorecard,
    dimensions: list[DimensionName],
) -> Scorecard:
    """Keep ``previous`` everywhere except the re-researched dimensions.

    The updated scores (including their fresh confidence) replace the old ones
    for exactly the flagged dimensions; every other dimension is preserved.
    """
    wanted = set(dimensions)
    updated_by: dict[DimensionName, DimensionScore] = {
        score.dimension: score for score in updated.dimensions
    }
    return Scorecard(
        dimensions=[
            updated_by.get(score.dimension, score) if score.dimension in wanted else score
            for score in previous.dimensions
        ]
    )
