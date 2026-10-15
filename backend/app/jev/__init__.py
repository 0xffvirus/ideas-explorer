"""Jev gate: typed client, versioned question catalog, and decision helpers."""

from app.jev.catalog import QUESTION_CATALOG, CatalogEntry
from app.jev.claims import Claim, ClaimStatus, VerifiedClaim
from app.jev.client import JevClient
from app.jev.errors import JevProtocolError, JevUnavailableError
from app.jev.gate import (
    Classification,
    DimensionName,
    DimensionScore,
    Gate,
    Scorecard,
    Verdict,
)
from app.jev.testing import FakeJevClient
from app.jev.types import (
    Answer,
    AskResult,
    ChoiceAnswer,
    ChoiceQuestion,
    NoulAnswer,
    NoulQuestion,
    Question,
    ScoreAnswer,
    ScoreQuestion,
    Usage,
)

__all__ = [
    "QUESTION_CATALOG",
    "Answer",
    "AskResult",
    "CatalogEntry",
    "ChoiceAnswer",
    "ChoiceQuestion",
    "Claim",
    "ClaimStatus",
    "Classification",
    "DimensionName",
    "DimensionScore",
    "FakeJevClient",
    "Gate",
    "JevClient",
    "JevProtocolError",
    "JevUnavailableError",
    "NoulAnswer",
    "NoulQuestion",
    "Question",
    "ScoreAnswer",
    "ScoreQuestion",
    "Scorecard",
    "Usage",
    "Verdict",
    "VerifiedClaim",
]
