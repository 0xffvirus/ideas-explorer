"""Async token-bucket rate limiting, one bucket per adapter."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Protocol

Clock = Callable[[], float]
SleepFn = Callable[[float], Awaitable[None]]


class RateLimiter(Protocol):
    """What an adapter needs from a limiter; :class:`TokenBucket` implements it."""

    async def acquire(self, tokens: float = 1.0) -> None: ...


class TokenBucket:
    """Paces calls to ``rate_per_minute`` with a bounded burst.

    Time and sleeping are injectable so tests run without real delays.
    """

    def __init__(
        self,
        rate_per_minute: int,
        *,
        burst: int | None = None,
        clock: Clock = time.monotonic,
        sleep: SleepFn = asyncio.sleep,
    ) -> None:
        if rate_per_minute <= 0:
            raise ValueError("rate_per_minute must be positive")
        capacity = burst if burst is not None else max(1, rate_per_minute)
        if capacity <= 0:
            raise ValueError("burst must be positive")
        self._rate_per_second = rate_per_minute / 60.0
        self._capacity = float(capacity)
        self._tokens = float(capacity)
        self._updated_at = clock()
        self._clock = clock
        self._sleep = sleep
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> None:
        """Wait until ``tokens`` are available, then consume them."""
        if tokens <= 0:
            raise ValueError("tokens must be positive")
        if tokens > self._capacity:
            raise ValueError("tokens must not exceed the bucket capacity")
        while True:
            async with self._lock:
                now = self._clock()
                elapsed = max(0.0, now - self._updated_at)
                self._tokens = min(self._capacity, self._tokens + elapsed * self._rate_per_second)
                self._updated_at = now
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                wait_for = (tokens - self._tokens) / self._rate_per_second
            await self._sleep(wait_for)
