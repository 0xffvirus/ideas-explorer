"""Live eval: ~10 golden ideas through the real Jev client.

Not part of the default suite. Run manually, with real spend:

    RUN_EVALS=1 uv run pytest tests/eval -q -m eval
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from app.config import get_settings
from app.jev import QUESTION_CATALOG, ChoiceQuestion, Gate, JevClient

pytestmark = pytest.mark.eval

if os.environ.get("RUN_EVALS") != "1" or not get_settings().typesafe_api_key:
    pytest.skip(
        "live eval; set RUN_EVALS=1 and TYPESAFE_API_KEY to run",
        allow_module_level=True,
    )


GOLDEN_IDEAS: list[dict[str, Any]] = [
    {
        "id": "dental-scheduling",
        "text": (
            "A scheduling and reminder tool for independent dental clinics: it fills "
            "cancelled slots by texting the practice's waitlist and tracks no-shows."
        ),
        "sections": {
            "problem": (
                "Independent dental clinics lose 10-15% of revenue to no-shows and late "
                "cancellations. Reception staff call waitlisted patients manually, which "
                "they rarely have time to do."
            ),
            "market": (
                "There are roughly 180,000 dental practices in the US alone; practice "
                "management software spend is growing, and scheduling modules are sold "
                "as add-ons at $100-300 per location per month."
            ),
            "competitors": (
                "Dentrix and Eaglesoft dominate practice management but their patient "
                "communication is dated; newer tools like Weave and Solutionreach focus "
                "on messaging but treat waitlist filling as a side feature."
            ),
            "customers": (
                "Owner-dentists and office managers are reachable through dental "
                "association events, Facebook practice-owner groups, and dental supply "
                "reps. They buy tools that show immediate revenue recovery."
            ),
            "feasibility": (
                "SMS is commodity infrastructure; the hard part is integrating with "
                "practice management systems via their APIs or screen-level bridges. "
                "HIPAA compliance is required but well-understood."
            ),
            "business_model": (
                "Per-location SaaS at $149 per month with a one-time onboarding fee; "
                "clinics measure recovered revenue, so willingness to pay is high "
                "relative to the ROI."
            ),
        },
    },
    {
        "id": "used-sports-gear",
        "text": (
            "A marketplace where parents buy and sell outgrown kids' sports equipment "
            "by team and season, with local pickup."
        ),
        "sections": {
            "problem": (
                "Kids outgrow sports gear every season. Parents spend hundreds per year "
                "and resale is fragmented across generic marketplaces where sizing and "
                "sport-specific filtering are poor."
            ),
            "market": (
                "Youth sports is a $19B US market with 45M participants; secondhand "
                "sporting goods resale is estimated at several billion and growing as "
                "families trade down."
            ),
            "competitors": (
                "Facebook Marketplace and OfferUp dominate local resale but have weak "
                "sport and size filters; SidelineSwap targets hockey and lacrosse but "
                "not the parent-to-parent seasonal flow."
            ),
            "customers": (
                "Parents gather in team group chats, club Facebook groups, and at "
                "season-start swap events. Local pickup avoids shipping entirely."
            ),
            "feasibility": (
                "A two-sided marketplace MVP is a standard build; liquidity per city is "
                "the main risk, so starting team-by-team keeps density high."
            ),
            "business_model": (
                "Take rate of 10% on completed sales plus promoted listings; parents "
                "already pay full price for gear, so a cheaper used option sells itself."
            ),
        },
    },
    {
        "id": "freelancer-invoicing",
        "text": (
            "Invoicing and late-payment chasing for freelancers in emerging markets, "
            "with local payment rails and automatic reminders."
        ),
        "sections": {
            "problem": (
                "Freelancers in emerging markets wait 30-60 days to get paid and lack "
                "affordable tools that speak their payment methods; chasing clients is "
                "awkward and manual."
            ),
            "market": (
                "There are tens of millions of freelancers across LATAM, Africa, and "
                "Southeast Asia; global invoicing software is priced for Western "
                "markets in hard currency."
            ),
            "competitors": (
                "FreshBooks and Wave serve Western freelancers; local incumbents are "
                "mostly spreadsheet templates or bank apps with no reminder workflow."
            ),
            "customers": (
                "Freelancers cluster in online communities, coworking spaces, and "
                "creator networks; acquisition through payment providers and "
                "communities is cheap."
            ),
            "feasibility": (
                "Payments integration is the key dependency and varies by country; "
                "starting with one corridor keeps compliance and scope manageable."
            ),
            "business_model": (
                "Freemium with a small monthly fee in local currency and a payment "
                "processing margin; the product directly recovers late cash, so ROI is "
                "obvious."
            ),
        },
    },
    {
        "id": "municipal-permits",
        "text": (
            "Permit tracking and fee calculation software for small municipal "
            "governments, replacing paper workflows."
        ),
        "sections": {
            "problem": (
                "Small municipalities run permits on paper and spreadsheets; residents "
                "and contractors cannot see status, and clerks duplicate data entry."
            ),
            "market": (
                "About 19,000 US municipalities have populations under 25,000; most "
                "lack modern permitting software, and current vendors target larger "
                "cities."
            ),
            "competitors": (
                "Accela and Tyler Technologies serve large cities with multi-year "
                "contracts; small towns either use paper or general-purpose form tools."
            ),
            "customers": (
                "Town clerks and administrators are reachable through municipal "
                "associations and state procurement cooperatives, but sales cycles are "
                "slow and procurement rules apply."
            ),
            "feasibility": (
                "Technically straightforward; the challenges are procurement, data "
                "migration from paper, and accessibility/compliance requirements."
            ),
            "business_model": (
                "Annual subscription priced per capita plus implementation fees, sold "
                "via cooperatives; budgets are small but recurring."
            ),
        },
    },
    {
        "id": "rural-teletherapy",
        "text": (
            "A teletherapy platform connecting rural teenagers with licensed "
            "counselors through schools."
        ),
        "sections": {
            "problem": (
                "Rural teens face a severe shortage of mental health providers; school "
                "counselors are overloaded and waitlists run months."
            ),
            "market": (
                "Youth mental health spending is rising, with school districts "
                "allocating federal funds for telehealth; the rural provider gap is "
                "well documented."
            ),
            "competitors": (
                "Talkspace and BetterHelp serve consumers; school-focused players like "
                "Hazel Health concentrate on physical care in denser markets."
            ),
            "customers": (
                "School districts buy through administrators and health coordinators; "
                "engagement happens through state school board associations and "
                "Medicaid programs."
            ),
            "feasibility": (
                "Licensing across states, Medicaid billing, and minor consent rules "
                "make compliance heavy; the platform itself is a standard video stack."
            ),
            "business_model": (
                "District contracts billed per student per year or via Medicaid "
                "reimbursement; budgets are already earmarked."
            ),
        },
    },
    {
        "id": "soil-sensors",
        "text": (
            "Solar-powered soil moisture sensors sold to small farms with a simple "
            "irrigation SMS alert service."
        ),
        "sections": {
            "problem": (
                "Small farms over-water or under-water because monitoring equipment is "
                "expensive and requires connectivity that fields lack."
            ),
            "market": (
                "There are about 2 million small US farms; precision agriculture is "
                "growing, and low-cost sensors expand the addressable segment."
            ),
            "competitors": (
                "Teralytic and Sentek serve large operations at high price points; "
                "cheap hobby sensors exist but are unreliable and lack alerting."
            ),
            "customers": (
                "Farmers trust cooperative extension services and equipment dealers; "
                "word of mouth at farm shows matters more than digital channels."
            ),
            "feasibility": (
                "Hardware design, certification, weatherproofing, and field durability "
                "are non-trivial; unit economics depend on manufacturing scale."
            ),
            "business_model": (
                "Hardware at cost plus a $5 per acre annual monitoring subscription; "
                "water savings are measurable and often subsidized."
            ),
        },
    },
    {
        "id": "niche-newsletter",
        "text": (
            "A paid newsletter and community for independent pharmacy owners covering "
            "regulation, reimbursement, and operations."
        ),
        "sections": {
            "problem": (
                "Independent pharmacists drown in changing reimbursement rules and "
                "regulations with no single trusted, practical information source."
            ),
            "market": (
                "About 19,000 independent US pharmacies; professional information and "
                "continuing education spending per owner is meaningful and recurring."
            ),
            "competitors": (
                "Trade magazines and association newsletters exist but are ad-funded, "
                "shallow, and slow; no operator-focused paid community dominates."
            ),
            "customers": (
                "Owners gather in pharmacy owner groups on Facebook, state association "
                "meetings, and buying co-ops; a niche newsletter spreads fast in these "
                "tight networks."
            ),
            "feasibility": (
                "A newsletter and community are cheap and fast to launch; the risk is "
                "editorial consistency and access to expert sources."
            ),
            "business_model": (
                "Subscription at $30-50 per month per pharmacy plus sponsorships from "
                "vendors selling into pharmacies."
            ),
        },
    },
    {
        "id": "compliance-saas",
        "text": (
            "Automated evidence collection for SOC 2 compliance aimed at 20-100 person "
            "software companies."
        ),
        "sections": {
            "problem": (
                "Startups pursuing SOC 2 spend months screenshotting systems and "
                "answering auditor questions; engineers lose weeks per year."
            ),
            "market": (
                "Thousands of companies pursue SOC 2 annually as enterprise deals "
                "require it; compliance automation is a growing software category."
            ),
            "competitors": (
                "Vanta and Drata are well funded leaders; the space is crowded, and "
                "differentiation must come from a wedge such as audit partner network "
                "or price."
            ),
            "customers": (
                "CTOs and heads of engineering are reachable via startup communities, "
                "accelerators, and audit firms; buyers search actively when an "
                "enterprise deal is on the line."
            ),
            "feasibility": (
                "Read-only cloud integrations and policy templates are known patterns; "
                "maintaining integration coverage is ongoing work but feasible."
            ),
            "business_model": (
                "Annual SaaS from $7,000; buyers already pay similar amounts to the "
                "incumbent tools and auditors, so the willingness to pay is proven."
            ),
        },
    },
    {
        "id": "meal-planner",
        "text": (
            "A meal planning app that builds weekly menus around grocery store sales "
            "and each household's dietary needs."
        ),
        "sections": {
            "problem": (
                "Households waste food and overspend because planning meals around "
                "sales and preferences is tedious; generic recipe apps ignore budgets."
            ),
            "market": (
                "Grocery inflation is a top household concern; recipe and meal-planning "
                "apps have hundreds of millions of downloads with subscription "
                "monetization."
            ),
            "competitors": (
                "Mealime and Paprika are established; most apps lack store-specific "
                "sale integration, which is the differentiating hook."
            ),
            "customers": (
                "Budget-conscious parents are reachable on TikTok, Pinterest, and "
                "parenting communities; trial via a free weekly menu is a natural "
                "funnel."
            ),
            "feasibility": (
                "Grocery sale data depends on retailer APIs and scraping limitations; "
                "starting with user-submitted or receipt-parsed prices reduces the "
                "dependency."
            ),
            "business_model": (
                "Free tier plus $5 per month premium; grocery savings give a clear "
                "payback story for subscription conversion."
            ),
        },
    },
    {
        "id": "restaurant-bookkeeping",
        "text": (
            "A done-for-you bookkeeping and payroll service for independent "
            "restaurants, combining software with a dedicated bookkeeper."
        ),
        "sections": {
            "problem": (
                "Independent restaurants run on thin margins with messy daily sales, "
                "tips, and vendor invoices; most owners do books at midnight and miss "
                "tax deadlines."
            ),
            "market": (
                "There are over 700,000 US restaurants; bookkeeping and payroll "
                "services are a large recurring spend already handled by fragmented "
                "local accountants."
            ),
            "competitors": (
                "Bench and Bookkeeper360 serve general SMBs; local accountants lack "
                "restaurant specialization such as tip pooling and daily sales "
                "reconciliation."
            ),
            "customers": (
                "Owners are reachable through restaurant associations, supplier "
                "networks, and POS resellers; trust transfers through referrals within "
                "restaurant owner circles."
            ),
            "feasibility": (
                "A service business with software leverage; hiring and training "
                "bookkeepers is the operational constraint, and POS integrations "
                "reduce manual work."
            ),
            "business_model": (
                "Monthly retainer of $400-900 per location; the work replaces an "
                "existing accountant expense, so the value is easy to communicate."
            ),
        },
    },
]


def make_gate() -> tuple[Gate, JevClient]:
    settings = get_settings()
    client = JevClient(
        settings.typesafe_api_key,
        base_url=settings.jev_base_url,
        model=settings.jev_model,
        timeout_seconds=settings.jev_timeout_seconds,
        max_questions_per_call=settings.jev_max_questions_per_call,
    )
    gate = Gate(
        client,
        confidence_floor=settings.jev_confidence_floor,
        claim_threshold=settings.jev_claim_threshold,
    )
    return gate, client


async def test_golden_ideas_classify_and_score() -> None:
    gate, client = make_gate()
    try:
        categories: list[str] = []
        scores: list[float] = []
        scored_dimensions = 0
        total_dimensions = 0
        for idea in GOLDEN_IDEAS:
            classification = await gate.classify(idea["text"])
            assert classification.source == "jev", f"{idea['id']}: Jev unavailable"
            assert classification.category is not None
            assert classification.category_confidence is not None
            assert 0.0 <= classification.category_confidence <= 1.0
            category_question = QUESTION_CATALOG["category"].question
            assert isinstance(category_question, ChoiceQuestion)
            assert classification.category in category_question.criteria
            categories.append(classification.category)

            scorecard = await gate.scorecard(idea["sections"])
            assert [item.dimension for item in scorecard.dimensions] == [
                "problem_severity",
                "market_evidence",
                "competition_intensity",
                "customer_reachability",
                "feasibility",
                "monetization_clarity",
            ]
            for dimension in scorecard.dimensions:
                total_dimensions += 1
                if dimension.score is not None:
                    scored_dimensions += 1
                    assert 1.0 <= dimension.score <= 5.0
                    scores.append(dimension.score)
                if dimension.confidence is not None:
                    assert 0.0 <= dimension.confidence <= 1.0

        assert len(set(categories)) >= 3, f"categories collapsed: {categories}"
        assert scored_dimensions / total_dimensions >= 0.8
        assert max(scores) - min(scores) >= 0.5, f"score spread too narrow: {scores}"
    finally:
        await client.aclose()
