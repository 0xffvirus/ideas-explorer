"""Unit tests for the token bucket, using an injected clock and sleep."""

from __future__ import annotations

import pytest

from app.research import TokenBucketRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_limiter(rate: float) -> tuple[TokenBucketRateLimiter, FakeClock, list[float]]:
    clock = FakeClock()
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.advance(seconds)

    limiter = TokenBucketRateLimiter(rate, clock=clock, sleep=fake_sleep)
    return limiter, clock, sleeps


async def test_initial_burst_up_to_capacity_is_free() -> None:
    limiter, _, sleeps = make_limiter(60)
    for _ in range(60):
        await limiter.acquire()
    assert sleeps == []


async def test_acquiring_past_the_burst_throttles_by_refill_rate() -> None:
    limiter, clock, sleeps = make_limiter(60)
    for _ in range(60):
        await limiter.acquire()
    await limiter.acquire()
    assert sleeps == [pytest.approx(1.0)]
    assert clock.now == pytest.approx(1.0)


async def test_tokens_refill_continuously_over_time() -> None:
    limiter, clock, sleeps = make_limiter(60)
    for _ in range(60):
        await limiter.acquire()
    clock.advance(10.0)
    for _ in range(10):
        await limiter.acquire()
    assert sleeps == []


async def test_partial_refill_waits_only_for_the_missing_tokens() -> None:
    limiter, clock, sleeps = make_limiter(30)
    for _ in range(30):
        await limiter.acquire()
    clock.advance(1.0)
    await limiter.acquire()
    assert sleeps == [pytest.approx(1.0)]
    assert clock.now == pytest.approx(2.0)


def test_invalid_rate_is_rejected() -> None:
    with pytest.raises(ValueError):
        TokenBucketRateLimiter(0)


async def test_non_positive_tokens_are_rejected() -> None:
    limiter, _, _ = make_limiter(60)
    with pytest.raises(ValueError):
        await limiter.acquire(0)
