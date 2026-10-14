"""Cost accounting shared by research tools, Jev, and the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config import ModelPrice


class CostCapExceeded(RuntimeError):
    """Raised when a caller asks to charge past the configured cap."""


@dataclass
class CostMeter:
    """Tracks USD spend for one analysis run.

    ``cap_usd <= 0`` means "no cap" (used in tests and evals).
    """

    cap_usd: float = 0.0
    spent_usd: float = 0.0
    by_category: dict[str, float] = field(default_factory=dict[str, float])

    @property
    def remaining_usd(self) -> float:
        if self.cap_usd <= 0:
            return float("inf")
        return max(0.0, self.cap_usd - self.spent_usd)

    def would_exceed(self, estimate_usd: float) -> bool:
        if self.cap_usd <= 0:
            return False
        return self.spent_usd + estimate_usd > self.cap_usd

    def add(self, usd: float, *, category: str) -> None:
        if usd < 0:
            raise ValueError("cost must be non-negative")
        self.spent_usd += usd
        self.by_category[category] = self.by_category.get(category, 0.0) + usd

    def charge_tokens(
        self,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
        category: str,
        pricing: dict[str, ModelPrice],
        default: ModelPrice | None = None,
    ) -> float:
        """Charge token usage for ``model`` and return the USD amount."""
        price = pricing.get(model) or default or ModelPrice(input=0.0, output=0.0)
        usd = (input_tokens / 1_000_000) * price.input + (output_tokens / 1_000_000) * price.output
        self.add(usd, category=category)
        return usd
