"""Token-bucket rate limiter shared by the research adapters."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable


async def _default_sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)


class TokenBucketRateLimiter:
    """Per-adapter token bucket with an initial burst up to the per-minute rate.

    The bucket starts full at ``rate_per_minute`` tokens and refills continuously
    at that rate. ``acquire`` consumes tokens when available and otherwise waits
    through the injected ``sleep``. Tests inject a clock and sleep so they never
    really sleep.
    """

    def __init__(
        self,
        rate_per_minute: float,
        *,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        if rate_per_minute <= 0:
            raise ValueError("rate_per_minute must be positive")
        self._rate_per_second = rate_per_minute / 60.0
        self._capacity = float(rate_per_minute)
        self._tokens = self._capacity
        self._clock: Callable[[], float] = clock if clock is not None else time.monotonic
        self._sleep: Callable[[float], Awaitable[None]] = (
            sleep if sleep is not None else _default_sleep
        )
        self._updated_at = self._clock()

    def _refill(self) -> None:
        now = self._clock()
        elapsed = max(0.0, now - self._updated_at)
        self._updated_at = now
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate_per_second)

    async def acquire(self, tokens: float = 1.0) -> None:
        """Wait until ``tokens`` are available, then consume them."""
        if tokens <= 0:
            raise ValueError("tokens must be positive")
        while True:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return
            missing = tokens - self._tokens
            await self._sleep(missing / self._rate_per_second)
