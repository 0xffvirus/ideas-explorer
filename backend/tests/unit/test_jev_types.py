"""Wire model validation: questions, answers, claims, and results."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.jev import (
    Answer,
    AskResult,
    ChoiceAnswer,
    Claim,
    NoulAnswer,
    ScoreAnswer,
    Usage,
    VerifiedClaim,
)
from app.jev.types import ANSWER_ADAPTER, QUESTION_ADAPTER


def test_question_adapter_parses_all_three_types() -> None:
    choice = QUESTION_ADAPTER.validate_python(
        {"type": "choice", "instructions": "i", "criteria": {"a": "A"}}
    )
    score = QUESTION_ADAPTER.validate_python(
        {"type": "score", "instructions": "i", "criteria": ["low", "high"]}
    )
    noul = QUESTION_ADAPTER.validate_python({"type": "noul", "instructions": "i"})
    assert choice.type == "choice"
    assert score.type == "score"
    assert noul.type == "noul"
    assert noul.criteria is None


def test_question_adapter_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        QUESTION_ADAPTER.validate_python({"type": "oracle", "instructions": "i"})


def test_answer_adapter_parses_all_three_types() -> None:
    assert isinstance(
        ANSWER_ADAPTER.validate_python({"type": "choice", "choice": "a", "confidence": 1.0}),
        ChoiceAnswer,
    )
    assert isinstance(
        ANSWER_ADAPTER.validate_python({"type": "score", "score": 1.5, "confidence": 0.5}),
        ScoreAnswer,
    )
    assert isinstance(ANSWER_ADAPTER.validate_python({"type": "noul", "noul": 0.7}), NoulAnswer)


def test_answer_adapter_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        ANSWER_ADAPTER.validate_python({"type": "oracle", "value": 1})


def test_claim_defaults_to_no_sources() -> None:
    claim = Claim(text="The market is growing.")
    assert claim.source_urls == []
    assert claim.model_dump(mode="json")["text"] == "The market is growing."


def test_claim_parses_urls() -> None:
    claim = Claim(text="sourced", source_urls=["https://example.com/a", "http://example.org/b"])
    assert [str(url) for url in claim.source_urls] == [
        "https://example.com/a",
        "http://example.org/b",
    ]


def test_claim_rejects_invalid_url() -> None:
    with pytest.raises(ValidationError):
        Claim(text="bad", source_urls=["not a url"])


def test_verified_claim_verified_property() -> None:
    claim = Claim(text="x", source_urls=[])
    verified = VerifiedClaim(claim=claim, status="verified", confidence=0.9)
    unverified = VerifiedClaim(claim=claim, status="unverified", confidence=0.3)
    unavailable = VerifiedClaim(claim=claim, status="unavailable")
    assert verified.verified is True
    assert unverified.verified is False
    assert unavailable.verified is False
    assert unavailable.confidence is None


def test_ask_result_defaults_usage() -> None:
    result = AskResult(answers={})
    assert result.usage == Usage()
    assert result.raw_model is None


def test_answer_union_is_importable_as_a_type_alias() -> None:
    assert Answer is not None
