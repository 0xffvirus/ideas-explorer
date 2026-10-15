"""Versioned question catalog for the Jev gate.

Every prompt lives here, so prompt changes are visible in code review and are
tracked by each entry's ``version`` field. Score entries use five ordered
levels; :meth:`app.jev.gate.Gate.scorecard` maps the 0-based Jev answer
position onto a 1-5 score.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.jev.types import ChoiceQuestion, NoulQuestion, Question, ScoreQuestion


class CatalogEntry(BaseModel):
    """One versioned catalog question plus a short human description."""

    key: str
    version: int
    question: Question
    description: str


QUESTION_CATALOG: dict[str, CatalogEntry] = {
    "category": CatalogEntry(
        key="category",
        version=1,
        description="Primary category of the business idea.",
        question=ChoiceQuestion(
            instructions=(
                "Classify the business idea described in the state into exactly one "
                "category. Choose the option that best matches the primary product and "
                "how it makes money, not just the industry it touches."
            ),
            criteria={
                "b2b_saas": (
                    "Software sold on subscription to businesses: workflow, analytics, "
                    "HR, sales, or vertical SaaS tools."
                ),
                "b2c_app": (
                    "A consumer app or product used by individuals: productivity, "
                    "lifestyle, social, or utility apps."
                ),
                "marketplace": (
                    "A platform connecting two or more sides (buyers and sellers, hosts "
                    "and guests) where the platform takes a fee on transactions."
                ),
                "hardware": (
                    "A physical device or hardware product, including IoT, robotics, or "
                    "wearables, that ships to customers."
                ),
                "service": (
                    "A done-for-you service: consulting, agency work, managed operations, "
                    "or other professional services."
                ),
                "content": (
                    "A media, education, newsletter, or community product monetized "
                    "through subscriptions, ads, or sponsorships."
                ),
                "fintech": (
                    "A financial product or infrastructure play: payments, lending, "
                    "insurance, accounting, banking, or wealth."
                ),
                "health": (
                    "A health, wellness, or care product: clinical tools, telehealth, "
                    "diagnostics, or wellbeing."
                ),
                "other": "None of the above fit the idea's primary product and revenue model.",
            },
        ),
    ),
    "business_type": CatalogEntry(
        key="business_type",
        version=1,
        description="Primary buyer and go-to-market model.",
        question=ChoiceQuestion(
            instructions=(
                "Identify the primary buyer and go-to-market model for the idea in the "
                "state: who pays for the product and who uses it."
            ),
            criteria={
                "b2b": "Sold to organizations; the buyer is a business or institution.",
                "b2c": "Sold to individual consumers; the buyer is the end user.",
                "b2b2c": (
                    "Sold to businesses that use it to serve their own consumers, such "
                    "as white-label or embedded offerings."
                ),
                "b2g": (
                    "Sold to government or public-sector organizations, where public "
                    "procurement rules and budgets apply."
                ),
            },
        ),
    ),
    "brief_is_specific": CatalogEntry(
        key="brief_is_specific",
        version=1,
        description="Whether the raw idea text is concrete enough to analyze as-is.",
        question=NoulQuestion(
            instructions=(
                "Decide whether the raw idea text in the state is concrete enough to "
                "analyze without asking the user clarifying questions. It is specific "
                "when it names a problem, a target user, and a solution or approach. "
                "Answer 1 when the analysis can proceed; answer 0 when clarifying "
                "questions would materially change the result."
            ),
            criteria={
                "true": (
                    "The brief names a problem, a target user, and a solution or approach "
                    "clear enough to analyze."
                ),
                "false": (
                    "One or more of problem, target user, or solution is missing or too "
                    "vague; clarifying questions would materially improve the analysis."
                ),
            },
        ),
    ),
    "problem_severity": CatalogEntry(
        key="problem_severity",
        version=1,
        description="How acute and costly the problem is for the target users.",
        question=ScoreQuestion(
            instructions=(
                "Assess how acute the problem is for the target users described in the "
                "state: how often it occurs, what the status quo costs them, and how "
                "urgently they want a fix. Pick the level that best matches the evidence "
                "actually present in the state; do not infer beyond it."
            ),
            criteria=[
                (
                    "Mild inconvenience: rare, cheap to live with, and no user is "
                    "actively looking for a solution."
                ),
                (
                    "Noticeable friction: users hit it occasionally and work around it "
                    "manually, but the workaround is cheap and tolerated."
                ),
                (
                    "Real recurring pain: users spend meaningful time or money on "
                    "workarounds and mention the problem unprompted, though urgency is "
                    "moderate or mixed across segments."
                ),
                (
                    "Painful and frequent: real budget or loss is attached, and users "
                    "are actively searching for tools or services to solve it today."
                ),
                (
                    "Urgent and high-stakes: users are losing significant money, time, "
                    "or opportunity right now and would adopt any credible solution "
                    "immediately."
                ),
            ],
        ),
    ),
    "market_evidence": CatalogEntry(
        key="market_evidence",
        version=1,
        description="Strength of the evidence that a real, reachable market exists.",
        question=ScoreQuestion(
            instructions=(
                "Judge how strong the evidence in the market section of the state is "
                "that a real, reachable market exists for this idea: sizing method, "
                "sourced demand signals, growth, and timing. Base the level only on the "
                "evidence present in the state."
            ),
            criteria=[
                (
                    "No evidence: the section asserts a market exists with no numbers, "
                    "sources, or demand signals."
                ),
                (
                    "Weak: only generic or indirect signals such as a single unsourced "
                    "statistic or anecdote, with no method behind the estimates."
                ),
                (
                    "Moderate: credible but thin data, for example one or two sourced "
                    "figures or proxies, with visible gaps in sizing or growth."
                ),
                (
                    "Solid: multiple sourced and mutually consistent data points about "
                    "size, growth, and demand, with a stated method for the estimates."
                ),
                (
                    "Compelling: triangulated, well-sourced sizing from several methods "
                    "plus strong demand and timing signals, and the sources agree on the "
                    "trend."
                ),
            ],
        ),
    ),
    "competition_intensity": CatalogEntry(
        key="competition_intensity",
        version=1,
        description="How crowded and entrenched the competitive landscape is (higher is harder).",
        question=ScoreQuestion(
            instructions=(
                "Assess how crowded and entrenched the competitive landscape is in the "
                "state: number of direct competitors, their strength, substitutability, "
                "and barriers to entry. Higher levels mean more intense competition; the "
                "report inverts this dimension when aggregating."
            ),
            criteria=[
                (
                    "Wide open: no clear direct competitor, only distant or "
                    "non-overlapping substitutes."
                ),
                (
                    "Light: a few small or early players, none with a strong hold on the "
                    "target users."
                ),
                (
                    "Moderate: several established options with loyal users, but "
                    "meaningful gaps or underserved segments remain."
                ),
                (
                    "Crowded: many well-funded or well-known competitors, and "
                    "differentiation requires a sharp, defensible wedge."
                ),
                (
                    "Saturated: dominant incumbents with network effects, pricing power, "
                    "and switching costs that make displacement very hard."
                ),
            ],
        ),
    ),
    "customer_reachability": CatalogEntry(
        key="customer_reachability",
        version=1,
        description="How findable and reachable the target customers are.",
        question=ScoreQuestion(
            instructions=(
                "Assess how findable and reachable the target customers are based on "
                "the state: named communities and channels, buying triggers, and any "
                "evidence that the customers engage there."
            ),
            criteria=[
                (
                    "Unreachable: no identifiable segment, community, channel, or "
                    "trigger is described."
                ),
                (
                    "Hard to reach: the segment is defined only in the abstract; no "
                    "concrete community, channel, or list exists."
                ),
                (
                    "Reachable with effort: some plausible communities or channels "
                    "exist, but they are broad, gated, or of uncertain engagement."
                ),
                (
                    "Clearly reachable: specific communities, channels, or platforms "
                    "where the target users are active, with credible ways to engage "
                    "them."
                ),
                (
                    "Directly reachable: named communities and channels with evidence of "
                    "engagement, clear buying triggers, and a practical, low-cost path "
                    "to first customers."
                ),
            ],
        ),
    ),
    "feasibility": CatalogEntry(
        key="feasibility",
        version=1,
        description="How feasible building and launching this is for a small team.",
        question=ScoreQuestion(
            instructions=(
                "Assess how feasible it is for a small team to build and launch this "
                "idea based on the state: technical, operational, and legal/regulatory "
                "constraints, cost to MVP, and timeline. Higher levels mean easier to "
                "execute."
            ),
            criteria=[
                (
                    "Infeasible: needs capabilities, capital, licenses, or partnerships "
                    "far beyond a small team, or the timeline is unbounded."
                ),
                (
                    "Very hard: significant technical or regulatory hurdles and a "
                    "costly, slow path to a working MVP."
                ),
                (
                    "Challenging but plausible: a scoped MVP is reachable with effort; a "
                    "few hard problems (data, integrations, compliance) need resolving."
                ),
                (
                    "Feasible: a small team can build a credible MVP with known "
                    "technology in a reasonable time and budget."
                ),
                (
                    "Easily feasible: standard technology, few dependencies or "
                    "regulatory constraints, and an MVP achievable quickly and cheaply."
                ),
            ],
        ),
    ),
    "monetization_clarity": CatalogEntry(
        key="monetization_clarity",
        version=1,
        description="How clear and credible the path to revenue is.",
        question=ScoreQuestion(
            instructions=(
                "Assess how clear and credible the path to revenue is in the state: "
                "who pays, the pricing model, evidence of willingness to pay, and rough "
                "unit economics."
            ),
            criteria=[
                "No model: no payer, pricing, or revenue path is described.",
                (
                    "Vague: revenue is assumed, but the payer and pricing model are "
                    "undefined or unvalidated."
                ),
                (
                    "Plausible: a payer and a conventional pricing model are named, but "
                    "willingness to pay and unit economics are unproven."
                ),
                (
                    "Clear: a specific payer, a pricing approach, and early "
                    "willingness-to-pay evidence, with roughly credible unit economics."
                ),
                (
                    "Proven and scalable: demonstrated willingness to pay, pricing "
                    "grounded in real comparables or tests, and unit economics that "
                    "improve with scale."
                ),
            ],
        ),
    ),
    "claim_supported": CatalogEntry(
        key="claim_supported",
        version=1,
        description="Whether the given sources plausibly support a factual claim.",
        question=NoulQuestion(
            instructions=(
                "Decide whether the source material in the state plausibly supports the "
                "claim given in the instructions. Answer with the probability that the "
                "sources support the claim, from 0 (no support or contradicts) to 1 "
                "(clearly supported). Judge only what the sources say, not whether the "
                "claim is true in general."
            ),
            criteria={
                "true": "The sources directly and credibly support the claim.",
                "false": "The sources do not mention, do not support, or contradict the claim.",
            },
        ),
    ),
    "is_relevant_evidence": CatalogEntry(
        key="is_relevant_evidence",
        version=1,
        description="Whether a research result is relevant evidence for a query.",
        question=NoulQuestion(
            instructions=(
                "Decide whether the result in the state is relevant evidence for the "
                "research question in the instructions. Answer 1 when the result "
                "directly helps answer the question, 0 when it is off-topic, too "
                "generic, or about a different domain."
            ),
            criteria={
                "true": "The result directly addresses the research question.",
                "false": "The result is off-topic, too generic, or about a different domain.",
            },
        ),
    ),
    "verdict": CatalogEntry(
        key="verdict",
        version=1,
        description="Recommended next action given the full analysis summary.",
        question=ChoiceQuestion(
            instructions=(
                "Given the full analysis summary in the state, decide the recommended "
                "next action: pursue when the evidence supports committing resources "
                "now, refine when the idea has promise but needs a sharper or "
                "better-evidenced angle, and park when the evidence does not justify "
                "further investment now."
            ),
            criteria={
                "pursue": (
                    "Evidence is strong enough to justify committing resources and "
                    "moving to validation or build."
                ),
                "refine": (
                    "The idea has promise, but a key element (segment, wedge, evidence, "
                    "or business model) must be sharpened before committing."
                ),
                "park": (
                    "The evidence does not support the idea now; worth revisiting only "
                    "if underlying assumptions change."
                ),
            },
        ),
    ),
}
