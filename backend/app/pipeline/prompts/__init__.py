"""Versioned agent prompts, one Markdown file per agent.

Prompts are packaged data: they are loaded with ``importlib.resources`` and
snapshot-tested by hash so changes show up in review.
"""

from __future__ import annotations

from importlib.resources import files

PROMPT_NAMES = (
    "refiner",
    "clarifier",
    "market",
    "competitor",
    "customer",
    "feasibility",
    "business_model",
    "critic",
)


def load_prompt(name: str) -> str:
    """Return the text of ``prompts/<name>.md``."""
    if name not in PROMPT_NAMES:
        raise ValueError(f"unknown prompt {name!r}")
    return files(__package__).joinpath(f"{name}.md").read_text(encoding="utf-8")
