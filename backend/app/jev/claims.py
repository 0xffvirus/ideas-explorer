"""Claims and their verification state."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

ClaimStatus = Literal["verified", "unverified", "unavailable"]


class Claim(BaseModel):
    """A factual statement plus the sources that are supposed to support it."""

    text: str
    source_urls: list[HttpUrl] = Field(default_factory=list[HttpUrl])


class VerifiedClaim(BaseModel):
    """A claim plus Jev's verdict on whether its sources support it."""

    claim: Claim
    status: ClaimStatus
    confidence: float | None = None

    @property
    def verified(self) -> bool:
        return self.status == "verified"
