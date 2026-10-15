"""Scripted in-memory Jev client for unit and pipeline tests (no HTTP)."""

from __future__ import annotations

import json
from typing import Any

from app.jev.types import (
    Answer,
    AskResult,
    ChoiceAnswer,
    ChoiceQuestion,
    NoulAnswer,
    Question,
    ScoreAnswer,
    ScoreQuestion,
    Usage,
)


class FakeJevClient:
    """Deterministic stand-in for :class:`app.jev.client.JevClient`.

    Answers can be preloaded per question id, queued per call, or left to
    sensible per-type defaults: a choice picks the first criterion with
    confidence 0.9, a score returns 2.0 (the raw midpoint of a 0..4 level
    scale, which maps to 3.0 on the 1..5 scorecard scale) with confidence
    0.9, and a noul returns 0.9.
    """

    def __init__(self, answers: dict[str, Answer] | None = None) -> None:
        self.calls: list[tuple[str | dict[str, Any], list[str]]] = []
        self._static: dict[str, Answer] = dict(answers or {})
        self._queued: dict[str, list[Answer]] = {}
        self._failures: list[BaseException] = []
        self._default_choice: tuple[str, float] | None = None

    def queue(self, question_id: str, answer: Answer) -> None:
        """Queue one answer; queued answers are consumed before defaults."""
        self._queued.setdefault(question_id, []).append(answer)

    def default_choice(self, choice: str, *, confidence: float = 0.9) -> None:
        """Override the synthesized choice and confidence for choice questions."""
        self._default_choice = (choice, confidence)

    def fail_next(self, exc: BaseException) -> None:
        """Make the next ``ask`` raise ``exc`` (for example an outage)."""
        self._failures.append(exc)

    async def ask(self, state: str | dict[str, Any], questions: dict[str, Question]) -> AskResult:
        self.calls.append((state, list(questions)))
        if self._failures:
            raise self._failures.pop(0)
        answers = {
            question_id: self._resolve(question_id, question)
            for question_id, question in questions.items()
        }
        text = state if isinstance(state, str) else json.dumps(state, sort_keys=True)
        usage = Usage(input_tokens=len(text), output_tokens=len(questions))
        return AskResult(answers=answers, usage=usage, raw_model="fake-jev")

    def _resolve(self, question_id: str, question: Question) -> Answer:
        queued = self._queued.get(question_id)
        if queued:
            return queued.pop(0)
        if question_id in self._static:
            return self._static[question_id]
        return self._synthesize(question)

    def _synthesize(self, question: Question) -> Answer:
        if isinstance(question, ChoiceQuestion):
            confidence = self._default_choice[1] if self._default_choice else 0.9
            if self._default_choice is not None:
                choice = self._default_choice[0]
            else:
                choice = next(iter(question.criteria), "other")
            others = [key for key in question.criteria if key != choice]
            share = round((1.0 - confidence) / len(others), 6) if others else 0.0
            probabilities = {
                key: (confidence if key == choice else share) for key in question.criteria
            }
            return ChoiceAnswer(choice=choice, confidence=confidence, probabilities=probabilities)
        if isinstance(question, ScoreQuestion):
            return ScoreAnswer(score=2.0, confidence=0.9)
        return NoulAnswer(noul=0.9)
