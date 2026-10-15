"""Snapshot tests for the packaged agent prompts (no DB, no network)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.pipeline.prompts import PROMPT_NAMES, load_prompt

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "pipeline" / "prompts_sha256.json"


def test_prompt_files_exist_and_match_the_hash_snapshot() -> None:
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    actual = {
        name: hashlib.sha256(load_prompt(name).encode("utf-8")).hexdigest() for name in PROMPT_NAMES
    }
    assert actual == expected


def test_prompt_names_are_stable() -> None:
    assert PROMPT_NAMES == (
        "refiner",
        "clarifier",
        "market",
        "competitor",
        "customer",
        "feasibility",
        "business_model",
        "critic",
    )


def test_unknown_prompt_raises() -> None:
    with pytest.raises(ValueError):
        load_prompt("nope")


def test_prompts_are_non_empty_markdown_with_titles() -> None:
    for name in PROMPT_NAMES:
        text = load_prompt(name)
        assert text.strip()
        assert text.startswith("# ")


def test_every_prompt_states_the_untrusted_evidence_rule() -> None:
    for name in PROMPT_NAMES:
        text = load_prompt(name)
        assert "## Untrusted evidence" in text
        assert "<untrusted_evidence>" in text
        assert "<user_input>" in text
        assert "<prior_sections>" in text
        assert "never instructions" in text
        assert "change your task or output schema" in text
