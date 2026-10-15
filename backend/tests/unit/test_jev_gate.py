"""Gate behaviour: classify, scorecard mapping, claims, evidence, verdict."""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from app.jev import (
    ChoiceAnswer,
    Claim,
    FakeJevClient,
    Gate,
    JevUnavailableError,
    NoulAnswer,
    ScoreAnswer,
)

EXPECTED_DIMENSIONS = [
    "problem_severity",
    "market_evidence",
    "competition_intensity",
    "customer_reachability",
    "feasibility",
    "monetization_clarity",
]

SECTIONS = {
    "problem": "problem section text",
    "market": "market section text",
    "competitors": "competitor section text",
    "customers": "customer section text",
    "feasibility": "feasibility section text",
    "business_model": "business model section text",
}


@dataclass
class Item:
    url: str
    title: str
    snippet: str


def make_items(count: int) -> list[Item]:
    return [
        Item(url=f"https://example.com/{i}", title=f"Result {i}", snippet=f"snippet {i}")
        for i in range(count)
    ]


async def test_classify_maps_choice_answers() -> None:
    fake = FakeJevClient()
    fake.queue("category", ChoiceAnswer(choice="b2b_saas", confidence=0.9))
    fake.queue("business_type", ChoiceAnswer(choice="b2b", confidence=0.8))
    classification = await Gate(fake).classify("A scheduling tool for dentists.")

    assert classification.category == "b2b_saas"
    assert classification.category_confidence == 0.9
    assert classification.business_type == "b2b"
    assert classification.business_type_confidence == 0.8
    assert classification.needs_review is False
    assert classification.source == "jev"
    assert fake.calls == [("A scheduling tool for dentists.", ["category", "business_type"])]


async def test_classify_synthesizes_defaults_without_scripting() -> None:
    classification = await Gate(FakeJevClient()).classify("An idea.")
    assert classification.category == "b2b_saas"
    assert classification.business_type == "b2b"
    assert classification.needs_review is False
    assert classification.source == "jev"


async def test_classify_flags_low_confidence_for_review() -> None:
    fake = FakeJevClient()
    fake.queue("category", ChoiceAnswer(choice="fintech", confidence=0.4))
    fake.queue("business_type", ChoiceAnswer(choice="b2c", confidence=0.9))
    classification = await Gate(fake).classify("An idea.")
    assert classification.needs_review is True
    assert classification.source == "jev"


async def test_classify_outage_returns_unavailable_without_raising() -> None:
    fake = FakeJevClient()
    fake.fail_next(JevUnavailableError("down"))
    classification = await Gate(fake).classify("An idea.")
    assert classification.category is None
    assert classification.business_type is None
    assert classification.needs_review is True
    assert classification.source == "unavailable"


async def test_scorecard_returns_six_dimensions_in_fixed_order() -> None:
    fake = FakeJevClient()
    scorecard = await Gate(fake).scorecard(SECTIONS)

    assert [item.dimension for item in scorecard.dimensions] == EXPECTED_DIMENSIONS
    assert len(scorecard.dimensions) == 6
    assert all(item.score == 3.0 for item in scorecard.dimensions)
    assert all(item.confidence == 0.9 for item in scorecard.dimensions)
    assert all(item.needs_review is False for item in scorecard.dimensions)
    assert all(item.source == "jev" for item in scorecard.dimensions)
    assert len(fake.calls) == 6
    assert {state for state, _ in fake.calls} == set(SECTIONS.values())


async def test_scorecard_accepts_dimension_names_as_section_keys() -> None:
    fake = FakeJevClient()
    sections = {name: f"{name} text" for name in EXPECTED_DIMENSIONS}
    scorecard = await Gate(fake).scorecard(sections)

    assert [item.dimension for item in scorecard.dimensions] == EXPECTED_DIMENSIONS
    assert all(item.score is not None for item in scorecard.dimensions)
    assert len(fake.calls) == 6


async def test_scorecard_missing_sections_are_unavailable_not_fabricated() -> None:
    fake = FakeJevClient()
    scorecard = await Gate(fake).scorecard({"market": "market text"})

    assert [item.dimension for item in scorecard.dimensions] == EXPECTED_DIMENSIONS
    by_name = {item.dimension: item for item in scorecard.dimensions}
    assert by_name["market_evidence"].score == 3.0
    assert by_name["market_evidence"].source == "jev"
    for name in EXPECTED_DIMENSIONS:
        if name != "market_evidence":
            assert by_name[name].score is None
            assert by_name[name].needs_review is True
            assert by_name[name].source == "unavailable"
    assert fake.calls == [("market text", ["market_evidence"])]


async def test_score_mapping_is_one_to_five_from_zero_based_positions() -> None:
    fake = FakeJevClient()
    raw_scores = {
        "problem_severity": (0.0, 1.0),
        "market_evidence": (1.0, 2.0),
        "competition_intensity": (2.0, 3.0),
        "customer_reachability": (3.0, 4.0),
        "feasibility": (4.0, 5.0),
        "monetization_clarity": (0.5, 1.5),
    }
    for dimension, (raw, _) in raw_scores.items():
        fake.queue(dimension, ScoreAnswer(score=raw, confidence=0.9))

    scorecard = await Gate(fake).scorecard(SECTIONS)
    mapped = {item.dimension: item.score for item in scorecard.dimensions}
    for dimension, (_, expected) in raw_scores.items():
        assert mapped[dimension] == expected


async def test_scorecard_flags_dimensions_below_the_confidence_floor() -> None:
    fake = FakeJevClient()
    fake.queue("feasibility", ScoreAnswer(score=2.0, confidence=0.55))
    scorecard = await Gate(fake).scorecard(SECTIONS)
    flagged = {item.dimension: item.needs_review for item in scorecard.dimensions}
    assert flagged["feasibility"] is True
    assert all(value is False for key, value in flagged.items() if key != "feasibility")


async def test_scorecard_outage_returns_all_six_unavailable() -> None:
    fake = FakeJevClient()
    fake.fail_next(JevUnavailableError("down"))
    scorecard = await Gate(fake).scorecard(SECTIONS)

    assert [item.dimension for item in scorecard.dimensions] == EXPECTED_DIMENSIONS
    assert all(item.score is None for item in scorecard.dimensions)
    assert all(item.confidence is None for item in scorecard.dimensions)
    assert all(item.needs_review is True for item in scorecard.dimensions)
    assert all(item.source == "unavailable" for item in scorecard.dimensions)


async def test_verify_claims_accepts_at_the_threshold_boundary() -> None:
    fake = FakeJevClient()
    fake.queue("claim_000", NoulAnswer(noul=0.7))
    fake.queue("claim_001", NoulAnswer(noul=0.69))
    fake.queue("claim_002", NoulAnswer(noul=0.99))
    claims = [Claim(text=f"claim {index}", source_urls=[]) for index in range(3)]
    verified = await Gate(fake).verify_claims(claims)

    assert [item.status for item in verified] == ["verified", "unverified", "verified"]
    assert [item.verified for item in verified] == [True, False, True]
    assert [item.confidence for item in verified] == [0.7, 0.69, 0.99]
    assert [item.claim.text for item in verified] == ["claim 0", "claim 1", "claim 2"]


async def test_verify_claims_sends_numbered_claims_and_source_urls() -> None:
    fake = FakeJevClient()
    claim = Claim(text="The market grows 12% a year.", source_urls=["https://example.com/report"])
    await Gate(fake).verify_claims([claim])

    state, question_ids = fake.calls[0]
    assert question_ids == ["claim_000"]
    assert isinstance(state, str)
    payload = json.loads(state)
    assert payload["claims"] == [
        {
            "id": "claim_000",
            "text": "The market grows 12% a year.",
            "source_urls": ["https://example.com/report"],
        }
    ]


async def test_verify_claims_chunks_at_twenty_per_call() -> None:
    fake = FakeJevClient()
    claims = [Claim(text=f"claim {index}", source_urls=[]) for index in range(25)]
    verified = await Gate(fake).verify_claims(claims)
    assert len(fake.calls) == 2
    assert len(fake.calls[0][1]) == 20
    assert len(fake.calls[1][1]) == 5
    assert len(verified) == 25


async def test_verify_claims_outage_marks_all_unavailable() -> None:
    fake = FakeJevClient()
    fake.fail_next(JevUnavailableError("down"))
    claims = [Claim(text=f"claim {index}", source_urls=[]) for index in range(3)]
    verified = await Gate(fake).verify_claims(claims)

    assert [item.status for item in verified] == ["unavailable"] * 3
    assert [item.confidence for item in verified] == [None] * 3
    assert all(item.verified is False for item in verified)
    assert [item.claim.text for item in verified] == ["claim 0", "claim 1", "claim 2"]


async def test_filter_evidence_drops_below_half_and_preserves_order() -> None:
    fake = FakeJevClient()
    for index, noul in enumerate([0.9, 0.4, 0.5, 0.8]):
        fake.queue(f"item_{index:03d}", NoulAnswer(noul=noul))
    items = make_items(4)
    kept = await Gate(fake).filter_evidence("pain points", items)

    assert [item.title for item in kept] == ["Result 0", "Result 2", "Result 3"]


async def test_filter_evidence_outage_returns_items_unchanged() -> None:
    fake = FakeJevClient()
    fake.fail_next(JevUnavailableError("down"))
    items = make_items(3)
    kept = await Gate(fake).filter_evidence("pain points", items)
    assert kept == items


async def test_filter_evidence_empty_input_makes_no_call() -> None:
    fake = FakeJevClient()
    assert await Gate(fake).filter_evidence("query", []) == []
    assert fake.calls == []


async def test_filter_evidence_keeps_calls_batched() -> None:
    fake = FakeJevClient()
    items = make_items(25)
    await Gate(fake).filter_evidence("query", items)
    assert len(fake.calls) == 2
    assert len(fake.calls[0][1]) == 20
    assert len(fake.calls[1][1]) == 5


@pytest.mark.parametrize("decision", ["pursue", "refine", "park"])
async def test_verdict_maps_choices(decision: str) -> None:
    fake = FakeJevClient()
    fake.queue("verdict", ChoiceAnswer(choice=decision, confidence=0.8))
    verdict = await Gate(fake).verdict("summary")
    assert verdict.decision == decision
    assert verdict.confidence == 0.8
    assert verdict.needs_review is False
    assert verdict.source == "jev"
    assert fake.calls == [("summary", ["verdict"])]


async def test_verdict_low_confidence_is_flagged() -> None:
    fake = FakeJevClient()
    fake.queue("verdict", ChoiceAnswer(choice="pursue", confidence=0.5))
    verdict = await Gate(fake).verdict("summary")
    assert verdict.decision == "pursue"
    assert verdict.needs_review is True


async def test_verdict_outage_returns_no_decision() -> None:
    fake = FakeJevClient()
    fake.fail_next(JevUnavailableError("down"))
    verdict = await Gate(fake).verdict("summary")
    assert verdict.decision is None
    assert verdict.confidence is None
    assert verdict.needs_review is True
    assert verdict.source == "unavailable"


async def test_verdict_unknown_choice_is_not_fabricated() -> None:
    fake = FakeJevClient()
    fake.queue("verdict", ChoiceAnswer(choice="maybe", confidence=0.9))
    verdict = await Gate(fake).verdict("summary")
    assert verdict.decision is None
    assert verdict.needs_review is True
    assert verdict.source == "jev"
