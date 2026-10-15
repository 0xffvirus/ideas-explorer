"""Typed wire models for the Jev System One API.

The request carries one ``state`` and many named questions; each question is a
``choice`` (labels plus descriptions), a ``score`` (ordered criteria levels), or
a ``noul`` (a calibrated value between 0 and 1). See SPEC-jev-gate.md.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter

Criterion = str | dict[str, Any] | list[Any]


class ChoiceQuestion(BaseModel):
    """A question answered with one of several named options."""

    type: Literal["choice"] = "choice"
    instructions: str
    criteria: dict[str, Criterion | None]


class ScoreQuestion(BaseModel):
    """A question answered with a fractional position on an ordered scale."""

    type: Literal["score"] = "score"
    instructions: str
    criteria: list[Criterion]


class NoulQuestion(BaseModel):
    """A yes/no style question answered with a value between 0 and 1."""

    type: Literal["noul"] = "noul"
    instructions: str
    criteria: dict[str, Criterion] | None = None


Question = Annotated[ChoiceQuestion | ScoreQuestion | NoulQuestion, Field(discriminator="type")]


class ChoiceAnswer(BaseModel):
    """Jev's pick among the question's criteria, with calibrated confidence."""

    type: Literal["choice"] = "choice"
    choice: str
    confidence: float
    probabilities: dict[str, float] = Field(default_factory=dict)


class ScoreAnswer(BaseModel):
    """Jev's 0-based fractional position on the question's levels array."""

    type: Literal["score"] = "score"
    score: float
    confidence: float
    legend: dict[str, str] | None = None
    probabilities: dict[str, float] | None = None


class NoulAnswer(BaseModel):
    """Jev's probability that the answer is yes (docs call this ``noul``)."""

    type: Literal["noul"] = "noul"
    noul: float


Answer = Annotated[ChoiceAnswer | ScoreAnswer | NoulAnswer, Field(discriminator="type")]


class Usage(BaseModel):
    """Token usage reported by Jev for one HTTP call."""

    input_tokens: int = 0
    output_tokens: int = 0


class AskResult(BaseModel):
    """Merged result of one or more Jev calls: answers, usage, and raw model."""

    answers: dict[str, Answer]
    usage: Usage = Field(default_factory=Usage)
    raw_model: str | None = None


QUESTION_ADAPTER: TypeAdapter[Question] = TypeAdapter(Question)
ANSWER_ADAPTER: TypeAdapter[Answer] = TypeAdapter(Answer)
