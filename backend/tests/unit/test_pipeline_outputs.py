"""Unit tests for pipeline output schemas: validation, constraints, round-trip."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.jev import Claim, Scorecard, Verdict
from app.pipeline.outputs import (
    AnalysisResult,
    BusinessModelSection,
    ClaimRef,
    Competitor,
    CompetitorSection,
    CriticOutput,
    CustomerSection,
    FeasibilitySection,
    IdeaBrief,
    MarketSection,
)
from tests.fixtures.pipeline.fakes import (
    brief_args,
    business_args,
    competitors_args,
    critic_args,
    customers_args,
    feasibility_args,
    market_args,
)


def test_realistic_fixtures_validate() -> None:
    brief = IdeaBrief.model_validate(brief_args())
    assert brief.variants and len(brief.variants) <= 3
    assert brief.claims

    market = MarketSection.model_validate(market_args())
    assert market.tam.sources
    assert market.claims

    competitors = CompetitorSection.model_validate(competitors_args())
    assert competitors.competitors[0].url
    assert competitors.claims

    customers = CustomerSection.model_validate(customers_args())
    assert customers.pain_quotes
    assert customers.claims

    feasibility = FeasibilitySection.model_validate(feasibility_args())
    assert feasibility.risks[0].likelihood == 3

    business = BusinessModelSection.model_validate(business_args())
    assert business.unit_economics.assumptions

    critic = CriticOutput.model_validate(critic_args())
    assert 3 <= len(critic.next_steps) <= 5


def test_bad_urls_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Competitor(
            name="Bad",
            url="not-a-url",
            positioning="x",
            pricing="x",
            gap="x",
        )
    with pytest.raises(ValidationError):
        MarketSection.model_validate(
            market_args(tam={"value": "$1", "method": "guess", "sources": ["not-a-url"]})
        )
    with pytest.raises(ValidationError):
        CustomerSection.model_validate(
            customers_args(
                communities=[{"name": "c", "url": "nope", "why": "w"}],
            )
        )


def test_claim_and_item_constraints() -> None:
    with pytest.raises(ValidationError):
        IdeaBrief.model_validate(brief_args(variants=["a", "b", "c", "d"]))
    with pytest.raises(ValidationError):
        CriticOutput.model_validate(critic_args(next_steps=critic_args()["next_steps"][:2]))
    with pytest.raises(ValidationError):
        FeasibilitySection.model_validate(
            feasibility_args(
                risks=[
                    {
                        "description": "x",
                        "likelihood": 9,
                        "impact": 1,
                        "mitigation": "y",
                    }
                ]
            )
        )


def _scorecard() -> Scorecard:
    return Scorecard.model_validate(
        {
            "dimensions": [
                {"dimension": "problem_severity", "score": 3.0, "confidence": 0.9, "source": "jev"},
                {"dimension": "market_evidence", "score": 3.0, "confidence": 0.9, "source": "jev"},
                {
                    "dimension": "competition_intensity",
                    "score": 3.0,
                    "confidence": 0.9,
                    "source": "jev",
                },
                {
                    "dimension": "customer_reachability",
                    "score": 3.0,
                    "confidence": 0.9,
                    "source": "jev",
                },
                {"dimension": "feasibility", "score": 3.0, "confidence": 0.9, "source": "jev"},
                {
                    "dimension": "monetization_clarity",
                    "score": 3.0,
                    "confidence": 0.9,
                    "source": "jev",
                },
            ]
        }
    )


def test_analysis_result_json_round_trip() -> None:
    result = AnalysisResult(
        run_id=uuid.uuid4(),
        idea_id=uuid.uuid4(),
        version_id=uuid.uuid4(),
        brief=IdeaBrief.model_validate(brief_args()),
        market=MarketSection.model_validate(market_args()),
        competitors=CompetitorSection.model_validate(competitors_args()),
        customers=CustomerSection.model_validate(customers_args()),
        feasibility=FeasibilitySection.model_validate(feasibility_args()),
        business_model=BusinessModelSection.model_validate(business_args()),
        scorecard=_scorecard(),
        verdict=Verdict(decision="refine", confidence=0.8, source="jev"),
        claims=[
            ClaimRef(
                section="brief",
                claim=Claim(text="Fact", source_urls=["https://example.com/evidence"]),
                status="unverified",
                confidence=0.1,
            )
        ],
        next_steps=CriticOutput.model_validate(critic_args()).next_steps,
        cost_usd=0.123456,
        sections_status={"refine": "done", "market": "failed"},
        generated_at=datetime.now(UTC),
    )
    payload = result.model_dump(mode="json")
    assert json.loads(json.dumps(payload)) == payload
    restored = AnalysisResult.model_validate(payload)
    assert restored == result
    assert restored.model_dump(mode="json") == payload
    assert restored.market is not None
    assert str(restored.market.tam.sources[0]) == "https://example.com/evidence"


def test_claim_ref_defaults_to_unverified() -> None:
    ref = ClaimRef(section="market", claim=Claim(text="x"))
    assert ref.status == "unverified"
    assert ref.confidence is None


def test_optional_sections_can_be_none() -> None:
    result = AnalysisResult(
        run_id=uuid.uuid4(),
        idea_id=uuid.uuid4(),
        version_id=uuid.uuid4(),
        brief=IdeaBrief.model_validate(brief_args()),
        scorecard=_scorecard(),
        verdict=Verdict(decision=None, source="unavailable"),
        claims=[],
        next_steps=[],
        sections_status={"market": "failed"},
        generated_at=datetime.now(UTC),
    )
    assert result.market is None
    assert result.business_model is None
    assert result.scorecard.dimensions
