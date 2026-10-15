"""Catalog shape, types, levels, and prompt snapshot tests."""

from __future__ import annotations

import json
from pathlib import Path

from app.jev import QUESTION_CATALOG, ChoiceQuestion, NoulQuestion, ScoreQuestion

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "jev"
SNAPSHOT = FIXTURES / "catalog_snapshot.json"

EXPECTED_KEYS = {
    "category",
    "business_type",
    "brief_is_specific",
    "problem_severity",
    "market_evidence",
    "competition_intensity",
    "customer_reachability",
    "feasibility",
    "monetization_clarity",
    "claim_supported",
    "is_relevant_evidence",
    "verdict",
}

SCORE_KEYS = {
    "problem_severity",
    "market_evidence",
    "competition_intensity",
    "customer_reachability",
    "feasibility",
    "monetization_clarity",
}

CHOICE_KEYS = {"category", "business_type", "verdict"}
NOUL_KEYS = {"brief_is_specific", "claim_supported", "is_relevant_evidence"}


def test_catalog_has_exactly_the_expected_keys() -> None:
    assert set(QUESTION_CATALOG) == EXPECTED_KEYS
    assert len(QUESTION_CATALOG) == 12


def test_entries_are_self_consistent_and_versioned() -> None:
    for key, entry in QUESTION_CATALOG.items():
        assert entry.key == key
        assert entry.version >= 1
        assert entry.description.strip()
        assert entry.question.instructions.strip()
        assert entry.question.type in {"choice", "score", "noul"}


def test_question_types_match_the_spec() -> None:
    for key in SCORE_KEYS:
        assert isinstance(QUESTION_CATALOG[key].question, ScoreQuestion)
    for key in CHOICE_KEYS:
        assert isinstance(QUESTION_CATALOG[key].question, ChoiceQuestion)
    for key in NOUL_KEYS:
        assert isinstance(QUESTION_CATALOG[key].question, NoulQuestion)


def test_score_questions_have_five_descriptive_levels() -> None:
    for key in SCORE_KEYS:
        question = QUESTION_CATALOG[key].question
        assert isinstance(question, ScoreQuestion)
        assert len(question.criteria) == 5
        assert all(isinstance(level, str) and level.strip() for level in question.criteria)


def test_category_and_verdict_criteria_match_the_spec() -> None:
    category = QUESTION_CATALOG["category"].question
    business_type = QUESTION_CATALOG["business_type"].question
    verdict = QUESTION_CATALOG["verdict"].question
    assert isinstance(category, ChoiceQuestion)
    assert isinstance(business_type, ChoiceQuestion)
    assert isinstance(verdict, ChoiceQuestion)
    assert set(category.criteria) == {
        "b2b_saas",
        "b2c_app",
        "marketplace",
        "hardware",
        "service",
        "content",
        "fintech",
        "health",
        "other",
    }
    assert set(business_type.criteria) == {"b2b", "b2c", "b2b2c", "b2g"}
    assert set(verdict.criteria) == {"pursue", "refine", "park"}


def test_catalog_snapshot_matches_so_prompt_changes_show_in_review() -> None:
    saved = json.loads(SNAPSHOT.read_text())
    current = {key: entry.model_dump(mode="json") for key, entry in QUESTION_CATALOG.items()}
    assert current == saved
