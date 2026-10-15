"""Realistic, deterministic reports fixtures: an AnalysisResult and its Report.

No network and no database: every field is pinned so unit snapshots and
integration seeds share one source of truth.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from app.jev import (
    Claim,
    Classification,
    DimensionName,
    DimensionScore,
    Scorecard,
    Verdict,
)
from app.pipeline.outputs import (
    AnalysisResult,
    BusinessModelSection,
    ClaimRef,
    Community,
    Competitor,
    CompetitorSection,
    CustomerSection,
    FeasibilitySection,
    IdeaBrief,
    MarketSection,
    MarketSize,
    NextStep,
    PainQuote,
    Persona,
    PricingOption,
    Risk,
    UnitEconomics,
)

RUN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
IDEA_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
VERSION_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
GENERATED_AT = datetime(2026, 10, 12, 9, 30, tzinfo=UTC)

URL_MARKET = "https://example.com/pet-market"
URL_PRICING = "https://example.com/vettrack-pricing"
URL_COMMUNITY = "https://example.com/r-dogs-thread"


def make_brief() -> IdeaBrief:
    return IdeaBrief(
        title="PetPulse",
        one_liner="Early illness detection for senior dogs",
        problem="Owners miss early signs of illness in senior dogs until treatment is costly.",
        solution="A smart collar and app that track activity and vitals and alert owners early.",
        target_users="City owners of dogs aged eight and older.",
        value_prop="Peace of mind from earlier detection at a fraction of vet-bill cost.",
        key_assumptions=["Owners will pay monthly", "Sensors are accurate enough"],
        variants=["Vet partnership channel"],
        claims=[
            Claim(
                text="Senior dogs need frequent health monitoring.",
                source_urls=[URL_MARKET],
            )
        ],
    )


def make_market() -> MarketSection:
    return MarketSection(
        tam=MarketSize(
            value="$4.2B",
            method="Top-down from pet care spend",
            sources=[URL_MARKET],
        ),
        sam=MarketSize(
            value="$900M",
            method="Urban senior-dog owners",
            sources=[URL_MARKET],
        ),
        som=MarketSize(
            value="$20M",
            method="1 percent of SAM in year three",
            sources=[],
        ),
        trends=[
            Claim(text="Pet health spending is growing.", source_urls=[URL_MARKET]),
        ],
        timing_why_now=Claim(
            text="Cheap sensors make this possible now.",
            source_urls=[URL_MARKET],
        ),
        claims=[
            Claim(text="The pet health market is growing.", source_urls=[URL_MARKET]),
        ],
    )


def make_competitors() -> CompetitorSection:
    return CompetitorSection(
        competitors=[
            Competitor(
                name="VetTrack",
                url=URL_PRICING,
                positioning="Vet-first monitoring",
                pricing="$40/month",
                gap="No consumer self-serve track for early alerts",
            ),
            Competitor(
                name="PawSense",
                url="https://example.com/pawsense",
                positioning="Activity tracking only",
                pricing="$25/month",
                gap="No health signals beyond steps",
            ),
        ],
        differentiation=Claim(
            text="The consumer wedge is early alerts without a vet visit.",
            source_urls=[URL_PRICING],
        ),
        claims=[
            Claim(
                text="VetTrack charges 40 dollars per month.",
                source_urls=[URL_PRICING],
            )
        ],
    )


def make_customers() -> CustomerSection:
    return CustomerSection(
        personas=[
            Persona(
                name="Anxious owner",
                description="Urban professional with an aging dog.",
                pains=["Fear of missing symptoms", "Vet visits are expensive"],
                where_they_gather=["r/dogs", "breed Facebook groups"],
            )
        ],
        communities=[
            Community(
                name="r/dogs",
                url=URL_COMMUNITY,
                why="Active owner community with senior-dog threads",
            )
        ],
        pain_quotes=[
            PainQuote(
                quote="I wish I had caught it earlier.",
                url=URL_COMMUNITY,
                context="Senior dog health thread",
            )
        ],
        early_adopter_profile="Tech-savvy owners of dogs over eight who already track walks.",
        leads=None,
        claims=[
            Claim(
                text="Owners discuss missed symptoms online.",
                source_urls=[URL_COMMUNITY],
            )
        ],
    )


def make_feasibility() -> FeasibilitySection:
    return FeasibilitySection(
        technical="Sensor firmware plus a companion mobile app.",
        operational="Support, replacements, and firmware updates.",
        legal_regulatory="Consumer device and privacy rules apply.",
        mvp_cost_range="$40k-$70k",
        mvp_timeline="4-6 months",
        risks=[
            Risk(
                description="Sensor accuracy",
                likelihood=3,
                impact=4,
                mitigation="Bench test against veterinary data",
            ),
            Risk(
                description="Battery life",
                likelihood=2,
                impact=3,
                mitigation="Use low-power firmware profile",
            ),
        ],
        claims=[
            Claim(
                text="Consumer health devices need privacy review.",
                source_urls=[],
            )
        ],
    )


def make_business_model() -> BusinessModelSection:
    return BusinessModelSection(
        lean_canvas={
            "Problem": "Missed symptoms in senior dogs",
            "Solution": "Collar and app with early alerts",
            "Key metrics": "Retention and alert precision",
        },
        revenue_streams=["Hardware sale", "Monthly subscription"],
        pricing_options=[
            PricingOption(
                name="Plus",
                price_point="$19/month",
                notes="Matches comparable subscriptions",
            )
        ],
        unit_economics=UnitEconomics(
            cac_estimate="$45",
            ltv_estimate="$240",
            assumptions=["12 month retention"],
        ),
        go_to_market=["Vet partnerships", "Breeder referrals"],
        claims=[
            Claim(
                text="Comparable subscriptions cost about 20 dollars.",
                source_urls=[URL_PRICING],
            )
        ],
    )


def make_scorecard() -> Scorecard:
    def entry(
        dimension: DimensionName,
        score: float | None,
        confidence: float | None,
        *,
        source: Literal["jev", "unavailable"] = "jev",
        needs_review: bool = False,
    ) -> DimensionScore:
        return DimensionScore(
            dimension=dimension,
            score=score,
            confidence=confidence,
            needs_review=needs_review,
            source=source,
        )

    return Scorecard(
        dimensions=[
            entry("problem_severity", 4.0, 0.82),
            entry("market_evidence", 3.5, 0.75),
            entry("competition_intensity", 2.0, 0.55, needs_review=True),
            entry("customer_reachability", 4.5, 0.9),
            entry("feasibility", None, None, source="unavailable", needs_review=True),
            entry("monetization_clarity", 3.0, 0.65),
        ]
    )


def make_claim_refs() -> list[ClaimRef]:
    return [
        ClaimRef(
            section="market",
            claim=Claim(text="The pet health market is growing.", source_urls=[URL_MARKET]),
            status="verified",
            confidence=0.9,
        ),
        ClaimRef(
            section="brief",
            claim=Claim(
                text="Senior dogs need frequent health monitoring.",
                source_urls=[URL_MARKET],
            ),
            status="verified",
            confidence=0.91,
        ),
        ClaimRef(
            section="business_model",
            claim=Claim(
                text="Comparable subscriptions cost about 20 dollars.",
                source_urls=[URL_PRICING],
            ),
            status="verified",
            confidence=0.8,
        ),
        ClaimRef(
            section="competitors",
            claim=Claim(
                text="VetTrack charges 40 dollars per month.",
                source_urls=[URL_PRICING],
            ),
            status="unverified",
            confidence=0.4,
        ),
        ClaimRef(
            section="feasibility",
            claim=Claim(
                text="Consumer health devices need privacy review.",
                source_urls=[],
            ),
            status="unavailable",
            confidence=None,
        ),
        ClaimRef(
            section="customers",
            claim=Claim(
                text="Owners discuss missed symptoms online.",
                source_urls=[URL_COMMUNITY],
            ),
            status="unavailable",
            confidence=None,
        ),
    ]


def make_next_steps() -> list[NextStep]:
    return [
        NextStep(
            assumption="Owners pay monthly",
            test="Pre-sale page with a deposit button",
            cost_hint="$200",
        ),
        NextStep(
            assumption="Sensors detect issues early",
            test="Bench prototype against vet data",
            cost_hint="$2k",
        ),
        NextStep(
            assumption="Vets refer patients",
            test="Ten vet interviews",
            cost_hint="1 week",
        ),
    ]


def make_result(
    *,
    idea_id: uuid.UUID = IDEA_ID,
    version_id: uuid.UUID = VERSION_ID,
    run_id: uuid.UUID = RUN_ID,
    drop_sections: tuple[str, ...] = (),
) -> AnalysisResult:
    return AnalysisResult(
        run_id=run_id,
        idea_id=idea_id,
        version_id=version_id,
        brief=make_brief(),
        classification=Classification(
            category="hardware",
            category_confidence=0.88,
            business_type="b2c",
            business_type_confidence=0.9,
            needs_review=False,
            source="jev",
        ),
        market=None if "market" in drop_sections else make_market(),
        competitors=None if "competitors" in drop_sections else make_competitors(),
        customers=None if "customers" in drop_sections else make_customers(),
        feasibility=None if "feasibility" in drop_sections else make_feasibility(),
        business_model=(None if "business_model" in drop_sections else make_business_model()),
        scorecard=make_scorecard(),
        verdict=Verdict(
            decision="refine",
            confidence=0.58,
            needs_review=True,
            source="jev",
        ),
        claims=make_claim_refs(),
        next_steps=make_next_steps(),
        cost_usd=0.42,
        sections_status={
            "refine": "done",
            "clarify": "skipped",
            "market": "failed" if "market" in drop_sections else "done",
            "competitors": "done",
            "customers": "done",
            "feasibility": "done",
            "business_model": "done",
            "critic": "done",
        },
        generated_at=GENERATED_AT,
    )
