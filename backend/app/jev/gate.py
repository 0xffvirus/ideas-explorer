"""Domain decisions on top of a Jev client.

Low confidence is data, not an error: every helper here returns a result with
``needs_review`` and ``source`` fields instead of raising on weak signals.
A Jev outage yields ``source="unavailable"`` results so the pipeline can
continue and the report can say "not scored" rather than fabricate a value.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal, Protocol

from pydantic import BaseModel

from app.jev.catalog import QUESTION_CATALOG
from app.jev.claims import Claim, ClaimStatus, VerifiedClaim
from app.jev.errors import JevProtocolError, JevUnavailableError
from app.jev.types import (
    AskResult,
    ChoiceAnswer,
    NoulAnswer,
    NoulQuestion,
    Question,
    ScoreAnswer,
    ScoreQuestion,
)


class EvidenceLike(Protocol):
    """Structural stand-in for ``app.research.Evidence`` (url, title, snippet).

    The research module owns the concrete model; the gate only needs these
    three attributes, so it stays decoupled from the research internals.
    """

    url: Any
    title: str
    snippet: str


class JevLike(Protocol):
    """Anything that can answer Jev questions, such as :class:`JevClient`."""

    async def ask(
        self, state: str | dict[str, Any], questions: dict[str, Question]
    ) -> AskResult: ...


DimensionName = Literal[
    "problem_severity",
    "market_evidence",
    "competition_intensity",
    "customer_reachability",
    "feasibility",
    "monetization_clarity",
]

SCORECARD_DIMENSIONS: tuple[DimensionName, ...] = (
    "problem_severity",
    "market_evidence",
    "competition_intensity",
    "customer_reachability",
    "feasibility",
    "monetization_clarity",
)

SECTION_ALIASES: dict[DimensionName, tuple[str, ...]] = {
    "problem_severity": ("problem", "problem_severity"),
    "market_evidence": ("market", "market_evidence"),
    "competition_intensity": ("competitors", "competition", "competition_intensity"),
    "customer_reachability": ("customers", "customer_reachability"),
    "feasibility": ("feasibility",),
    "monetization_clarity": ("business_model", "monetization_clarity"),
}

_CLAIMS_PER_CALL = 20
_EVIDENCE_PER_CALL = 20
_RELEVANCE_THRESHOLD = 0.5


class Classification(BaseModel):
    """Jev's category and business-type decision for a brief."""

    category: str | None = None
    category_confidence: float | None = None
    business_type: str | None = None
    business_type_confidence: float | None = None
    needs_review: bool = True
    source: Literal["jev", "unavailable"] = "unavailable"


class DimensionScore(BaseModel):
    """One scorecard dimension on the 1-5 scale, with Jev confidence."""

    dimension: DimensionName
    score: float | None = None
    confidence: float | None = None
    needs_review: bool = True
    source: Literal["jev", "unavailable"] = "unavailable"


class Scorecard(BaseModel):
    """The six idea dimensions, always in a fixed order."""

    dimensions: list[DimensionScore]


class Verdict(BaseModel):
    """Jev's recommended next action for an analyzed idea."""

    decision: Literal["pursue", "refine", "park"] | None = None
    confidence: float | None = None
    needs_review: bool = True
    source: Literal["jev", "unavailable"] = "unavailable"


def _map_jev_score(jev_score: float, levels: int) -> float:
    """Map a 0-based Jev position onto the 1-5 scale, clamped and rounded."""
    if levels <= 1:
        return 1.0
    normalized = jev_score / (levels - 1)
    normalized = min(max(normalized, 0.0), 1.0)
    return round(1.0 + normalized * 4.0, 2)


def _unavailable_dimension(dimension: DimensionName) -> DimensionScore:
    return DimensionScore(
        dimension=dimension,
        score=None,
        confidence=None,
        needs_review=True,
        source="unavailable",
    )


def _unavailable_claim(claim: Claim) -> VerifiedClaim:
    return VerifiedClaim(claim=claim, status="unavailable", confidence=None)


def _claim_id(index: int) -> str:
    return f"claim_{index:03d}"


def _item_id(index: int) -> str:
    return f"item_{index:03d}"


class Gate:
    """Decision helpers built on any object implementing :class:`JevLike`."""

    def __init__(
        self,
        client: JevLike,
        *,
        confidence_floor: float = 0.6,
        claim_threshold: float = 0.7,
    ) -> None:
        self._client = client
        self._confidence_floor = confidence_floor
        self._claim_threshold = claim_threshold

    async def classify(self, state: str) -> Classification:
        """Classify a brief; never raises on a Jev outage."""
        questions: dict[str, Question] = {
            "category": QUESTION_CATALOG["category"].question,
            "business_type": QUESTION_CATALOG["business_type"].question,
        }
        try:
            result = await self._client.ask(state, questions)
        except JevUnavailableError:
            return Classification(needs_review=True, source="unavailable")
        category = result.answers["category"]
        business_type = result.answers["business_type"]
        if not isinstance(category, ChoiceAnswer) or not isinstance(business_type, ChoiceAnswer):
            raise JevProtocolError("expected choice answers for category and business_type")
        needs_review = (
            category.confidence < self._confidence_floor
            or business_type.confidence < self._confidence_floor
        )
        return Classification(
            category=category.choice,
            category_confidence=category.confidence,
            business_type=business_type.choice,
            business_type_confidence=business_type.confidence,
            needs_review=needs_review,
            source="jev",
        )

    async def scorecard(self, sections: Mapping[str, str]) -> Scorecard:
        """Score all six dimensions, grouped by the report section each uses.

        Grouping: ``problem_severity`` is judged against ``problem``,
        ``market_evidence`` against ``market``, ``competition_intensity``
        against ``competitors`` (or ``competition``), ``customer_reachability``
        against ``customers``, ``feasibility`` against ``feasibility``, and
        ``monetization_clarity`` against ``business_model``. A dimension's own
        name is accepted as a section key too. Each distinct section text is
        one ``ask()`` call, so the same text is never sent twice. Dimensions
        whose section is absent are returned as unavailable rather than scored
        from unrelated text.
        """
        groups: dict[str, list[DimensionName]] = {}
        for dimension in SCORECARD_DIMENSIONS:
            for section_key in SECTION_ALIASES[dimension]:
                if section_key in sections:
                    groups.setdefault(section_key, []).append(dimension)
                    break
        scores: dict[DimensionName, DimensionScore] = {}
        if groups:
            outcomes = await asyncio.gather(
                *(
                    self._score_group_safe(sections[key], dimensions)
                    for key, dimensions in groups.items()
                )
            )
            if any(outcome is None for outcome in outcomes):
                return Scorecard(
                    dimensions=[_unavailable_dimension(d) for d in SCORECARD_DIMENSIONS]
                )
            for outcome in outcomes:
                if outcome is not None:
                    scores.update(outcome)
        for dimension in SCORECARD_DIMENSIONS:
            scores.setdefault(dimension, _unavailable_dimension(dimension))
        return Scorecard(dimensions=[scores[dimension] for dimension in SCORECARD_DIMENSIONS])

    async def verify_claims(self, claims: list[Claim]) -> list[VerifiedClaim]:
        """Check that sources support each claim; batches are one call each."""
        if not claims:
            return []
        batches = [
            claims[index : index + _CLAIMS_PER_CALL]
            for index in range(0, len(claims), _CLAIMS_PER_CALL)
        ]
        outcomes = await asyncio.gather(
            *(
                self._verify_batch_safe(batch, start)
                for start, batch in (
                    (index * _CLAIMS_PER_CALL, batch) for index, batch in enumerate(batches)
                )
            )
        )
        if any(outcome is None for outcome in outcomes):
            return [_unavailable_claim(claim) for claim in claims]
        verified: list[VerifiedClaim] = []
        for outcome in outcomes:
            if outcome is not None:
                verified.extend(outcome)
        return verified

    async def filter_evidence(
        self, query: str, items: Sequence[EvidenceLike]
    ) -> list[EvidenceLike]:
        """Drop results Jev judges irrelevant; preserve input order."""
        if not items:
            return []
        ordered = list(items)
        batches = [
            ordered[index : index + _EVIDENCE_PER_CALL]
            for index in range(0, len(ordered), _EVIDENCE_PER_CALL)
        ]
        outcomes = await asyncio.gather(
            *(
                self._filter_batch_safe(query, batch, start)
                for start, batch in (
                    (index * _EVIDENCE_PER_CALL, batch) for index, batch in enumerate(batches)
                )
            )
        )
        if any(outcome is None for outcome in outcomes):
            return ordered
        keep: list[bool] = []
        for outcome in outcomes:
            if outcome is not None:
                keep.extend(outcome)
        return [item for item, kept in zip(ordered, keep, strict=True) if kept]

    async def verdict(self, summary: str) -> Verdict:
        """Pick pursue/refine/park; never fabricates a decision on outage."""
        question = QUESTION_CATALOG["verdict"].question
        try:
            result = await self._client.ask(summary, {"verdict": question})
        except JevUnavailableError:
            return Verdict(decision=None, confidence=None, needs_review=True, source="unavailable")
        answer = result.answers["verdict"]
        if not isinstance(answer, ChoiceAnswer):
            raise JevProtocolError("expected a choice answer for the verdict")
        decision: Literal["pursue", "refine", "park"] | None = None
        if answer.choice in ("pursue", "refine", "park"):
            decision = answer.choice
        return Verdict(
            decision=decision,
            confidence=answer.confidence,
            needs_review=decision is None or answer.confidence < self._confidence_floor,
            source="jev",
        )

    async def _score_group(
        self, state: str, dimensions: Sequence[DimensionName]
    ) -> dict[DimensionName, DimensionScore]:
        questions: dict[str, Question] = {}
        levels: dict[DimensionName, int] = {}
        for dimension in dimensions:
            question = QUESTION_CATALOG[dimension].question
            if not isinstance(question, ScoreQuestion):
                raise JevProtocolError(f"catalog entry {dimension!r} is not a score question")
            questions[dimension] = question
            levels[dimension] = len(question.criteria)
        result = await self._client.ask(state, questions)
        scores: dict[DimensionName, DimensionScore] = {}
        for dimension in dimensions:
            answer = result.answers[dimension]
            if not isinstance(answer, ScoreAnswer):
                raise JevProtocolError(f"expected a score answer for {dimension!r}")
            scores[dimension] = DimensionScore(
                dimension=dimension,
                score=_map_jev_score(answer.score, levels[dimension]),
                confidence=answer.confidence,
                needs_review=answer.confidence < self._confidence_floor,
                source="jev",
            )
        return scores

    async def _score_group_safe(
        self, state: str, dimensions: Sequence[DimensionName]
    ) -> dict[DimensionName, DimensionScore] | None:
        try:
            return await self._score_group(state, dimensions)
        except JevUnavailableError:
            return None

    async def _verify_batch(self, claims: list[Claim], start: int) -> list[VerifiedClaim]:
        state_items = [
            {
                "id": _claim_id(start + index),
                "text": claim.text,
                "source_urls": [str(url) for url in claim.source_urls],
            }
            for index, claim in enumerate(claims)
        ]
        state = json.dumps({"claims": state_items})
        base = QUESTION_CATALOG["claim_supported"].question
        if not isinstance(base, NoulQuestion):
            raise JevProtocolError("catalog entry 'claim_supported' is not a noul question")
        questions: dict[str, Question] = {}
        for index, claim in enumerate(claims):
            questions[_claim_id(start + index)] = base.model_copy(
                update={
                    "instructions": (
                        "The source URLs and snippets in the state support this claim: "
                        f"{claim.text}"
                    )
                }
            )
        result = await self._client.ask(state, questions)
        verified: list[VerifiedClaim] = []
        for index, claim in enumerate(claims):
            answer = result.answers[_claim_id(start + index)]
            if not isinstance(answer, NoulAnswer):
                raise JevProtocolError(f"expected a noul answer for claim {start + index}")
            status: ClaimStatus = (
                "verified" if answer.noul >= self._claim_threshold else "unverified"
            )
            verified.append(VerifiedClaim(claim=claim, status=status, confidence=answer.noul))
        return verified

    async def _verify_batch_safe(
        self, claims: list[Claim], start: int
    ) -> list[VerifiedClaim] | None:
        try:
            return await self._verify_batch(claims, start)
        except JevUnavailableError:
            return None

    async def _filter_batch(
        self, query: str, items: Sequence[EvidenceLike], start: int
    ) -> list[bool]:
        state_items = [
            {
                "id": _item_id(start + index),
                "url": str(item.url),
                "title": item.title,
                "snippet": item.snippet,
            }
            for index, item in enumerate(items)
        ]
        state = json.dumps({"query": query, "results": state_items})
        base = QUESTION_CATALOG["is_relevant_evidence"].question
        if not isinstance(base, NoulQuestion):
            raise JevProtocolError("catalog entry 'is_relevant_evidence' is not a noul question")
        questions: dict[str, Question] = {}
        for index in range(len(items)):
            item_id = _item_id(start + index)
            questions[item_id] = base.model_copy(
                update={
                    "instructions": (
                        f"Is this result relevant evidence for: {query}? "
                        f"The result is {item_id} in the state."
                    )
                }
            )
        result = await self._client.ask(state, questions)
        flags: list[bool] = []
        for index in range(len(items)):
            answer = result.answers[_item_id(start + index)]
            if not isinstance(answer, NoulAnswer):
                raise JevProtocolError(f"expected a noul answer for evidence item {start + index}")
            flags.append(answer.noul >= _RELEVANCE_THRESHOLD)
        return flags

    async def _filter_batch_safe(
        self, query: str, items: Sequence[EvidenceLike], start: int
    ) -> list[bool] | None:
        try:
            return await self._filter_batch(query, items, start)
        except JevUnavailableError:
            return None
