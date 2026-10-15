"""Lead-DB provider port for the disabled-by-default LeadFinder tool.

The concrete provider is TBD (see SPEC.md open questions: Apollo, Clearbit, or
another). Implementations must return company-level data only and must never
include individual names, emails, or phone numbers.
"""

from __future__ import annotations

from typing import Protocol

from app.research.evidence import CompanyLead


class LeadProvider(Protocol):
    """Port for a company-lead source; swapped in once a provider is approved."""

    name: str

    async def find(self, query: str, *, limit: int = 8) -> list[CompanyLead]:
        """Return up to ``limit`` company leads matching ``query``."""
        ...
