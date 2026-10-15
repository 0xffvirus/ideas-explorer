"""Unit tests for the reports scoring, citation, and rationale helpers."""

from __future__ import annotations

from typing import Literal

from app.jev import Claim, DimensionName, DimensionScore, Scorecard
from app.pipeline.outputs import ClaimRef
from app.reports.assembler import (
    compute_overall_score,
    dimension_rationale,
    number_sources,
    score_basis,
    verdict_label,
)
from tests.fixtures.reports.fixtures import (
    URL_COMMUNITY,
    URL_MARKET,
    URL_PRICING,
    make_claim_refs,
    make_result,
    make_scorecard,
)

DEFAULT_WEIGHTS = {
    "problem_severity": 0.20,
    "market_evidence": 0.20,
    "competition_intensity": 0.15,
    "customer_reachability": 0.15,
    "feasibility": 0.15,
    "monetization_clarity": 0.15,
}


def _score(
    dimension: DimensionName,
    score: float | None,
    *,
    source: Literal["jev", "unavailable"] = "jev",
) -> DimensionScore:
    return DimensionScore(
        dimension=dimension,
        score=score,
        confidence=0.8,
        needs_review=False,
        source=source,
    )


def test_compute_overall_score_hand_computed_with_inversion_and_exclusion() -> None:
    # problem 4.0 -> 0.8, market 3.5 -> 0.7, competition 2.0 -> (6-2)/5 = 0.8,
    # customer 4.5 -> 0.9, feasibility excluded, monetization 3.0 -> 0.6.
    # Weighted sum = .8*.20 + .7*.20 + .8*.15 + .9*.15 + .6*.15 = .645
    # Denominator = .85 -> 75.8823... -> 75.9.
    assert compute_overall_score(make_scorecard(), DEFAULT_WEIGHTS) == 75.9


def test_compute_overall_score_excluded_dimension_changes_denominator_not_scale() -> None:
    scorecard = Scorecard(
        dimensions=[
            _score("problem_severity", 5.0),
            _score("competition_intensity", 1.0),
            _score("feasibility", 3.0),
        ]
    )
    weights = {
        "problem_severity": 0.2,
        "competition_intensity": 0.15,
        "feasibility": 0.15,
    }
    # (1.0*.2 + 1.0*.15 + .6*.15) / .5 -> 88.0
    assert compute_overall_score(scorecard, weights) == 88.0

    with_market = Scorecard(
        dimensions=[
            _score("problem_severity", 5.0),
            _score("competition_intensity", 1.0),
            _score("feasibility", 3.0),
            _score("market_evidence", 2.5),
        ]
    )
    full_weights = {**weights, "market_evidence": 0.2}
    # (.44 + .5*.2) / .7 -> 77.1428... -> 77.1
    assert compute_overall_score(with_market, full_weights) == 77.1


def test_compute_overall_score_none_when_no_dimension_is_scorable() -> None:
    scorecard = Scorecard(
        dimensions=[
            _score("problem_severity", None),
            _score("market_evidence", 4.0, source="unavailable"),
        ]
    )
    assert compute_overall_score(scorecard, DEFAULT_WEIGHTS) is None
    assert score_basis(scorecard, DEFAULT_WEIGHTS) == "not_scored"


def test_compute_overall_score_ignores_dimensions_without_weight() -> None:
    scorecard = Scorecard(dimensions=[_score("problem_severity", 4.0)])
    assert compute_overall_score(scorecard, {"market_evidence": 0.5}) is None


def test_score_basis_variants() -> None:
    assert score_basis(make_scorecard(), DEFAULT_WEIGHTS) == "partial"
    full = Scorecard(
        dimensions=[
            _score(dimension, 3.0)
            for dimension in (
                "problem_severity",
                "market_evidence",
                "competition_intensity",
                "customer_reachability",
                "feasibility",
                "monetization_clarity",
            )
        ]
    )
    assert score_basis(full, DEFAULT_WEIGHTS) == "all_dimensions"
    assert score_basis(Scorecard(dimensions=[]), DEFAULT_WEIGHTS) == "not_scored"


def test_number_sources_dedupes_and_numbers_by_first_appearance() -> None:
    sources, claims = number_sources(make_claim_refs())
    assert [(source.number, source.url) for source in sources] == [
        (1, URL_MARKET),
        (2, URL_PRICING),
        (3, URL_COMMUNITY),
    ]
    by_text = {claim.text: claim for claim in claims}
    assert by_text["Senior dogs need frequent health monitoring."].citation_numbers == [1]
    assert by_text["The pet health market is growing."].citation_numbers == [1]
    assert by_text["VetTrack charges 40 dollars per month."].citation_numbers == [2]
    assert by_text["Comparable subscriptions cost about 20 dollars."].citation_numbers == [2]
    assert by_text["Consumer health devices need privacy review."].citation_numbers == []
    assert by_text["Owners discuss missed symptoms online."].citation_numbers == [3]


def test_number_sources_has_no_orphans_or_duplicates() -> None:
    sources, claims = number_sources(make_claim_refs())
    numbers = {source.number for source in sources}
    urls = [source.url for source in sources]
    assert len(urls) == len(set(urls))
    assert numbers == set(range(1, len(sources) + 1))
    for claim in claims:
        assert claim.citation_numbers == sorted(claim.citation_numbers)
        assert set(claim.citation_numbers) <= numbers


def test_number_sources_collapses_duplicate_urls_within_one_claim() -> None:
    ref = ClaimRef(
        section="market",
        claim=Claim(text="Doubled source.", source_urls=[URL_MARKET, URL_MARKET]),
        status="verified",
    )
    sources, claims = number_sources([ref])
    assert len(sources) == 1
    assert claims[0].citation_numbers == [1]


def test_number_sources_keeps_ascending_numbers_for_out_of_order_urls() -> None:
    first = ClaimRef(
        section="brief",
        claim=Claim(text="First.", source_urls=[URL_MARKET]),
        status="verified",
    )
    second = ClaimRef(
        section="market",
        claim=Claim(text="Second.", source_urls=[URL_PRICING, URL_MARKET]),
        status="verified",
    )
    sources, claims = number_sources([first, second])
    assert [source.url for source in sources] == [URL_MARKET, URL_PRICING]
    assert claims[1].citation_numbers == [1, 2]


def test_dimension_rationale_falls_back_when_not_scored() -> None:
    result = make_result()
    feasibility_score = next(
        score for score in result.scorecard.dimensions if score.dimension == "feasibility"
    )
    market_score = next(
        score for score in result.scorecard.dimensions if score.dimension == "market_evidence"
    )
    assert (
        dimension_rationale("feasibility", feasibility_score, result)
        == "Not scored: Jev unavailable."
    )
    without_feasibility = make_result(drop_sections=("feasibility",))
    assert (
        dimension_rationale("feasibility", feasibility_score, without_feasibility)
        == "Not scored: section not completed."
    )
    without_market = make_result(drop_sections=("market",))
    assert (
        dimension_rationale("market_evidence", market_score, without_market)
        == "Section not completed."
    )
    assert dimension_rationale("market_evidence", None, result) == "Not scored: Jev unavailable."


def test_dimension_rationale_draws_from_owning_section() -> None:
    result = make_result()
    assert (
        dimension_rationale(
            "problem_severity",
            next(
                score
                for score in result.scorecard.dimensions
                if score.dimension == "problem_severity"
            ),
            result,
        )
        == "Owners miss early signs of illness in senior dogs until treatment is costly."
    )
    assert (
        dimension_rationale(
            "monetization_clarity",
            next(
                score
                for score in result.scorecard.dimensions
                if score.dimension == "monetization_clarity"
            ),
            result,
        )
        == "2 revenue streams; CAC $45, LTV $240."
    )


def test_verdict_label() -> None:
    assert verdict_label("pursue") == "Pursue"
    assert verdict_label("park") == "Park"
    assert verdict_label(None) == "unknown"
    assert verdict_label("mystery") == "mystery"
