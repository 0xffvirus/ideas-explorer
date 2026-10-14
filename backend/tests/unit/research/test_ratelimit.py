"""Unit tests for the token bucket."""

from __future__ import annotations

import pytest

from app.research.ratelimit import TokenBucket


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


async def test_burst_is_immediate_then_waits() -> None:
    clock = FakeClock()
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)
        clock.now += delay

    bucket = TokenBucket(60, burst=2, clock=clock, sleep=sleep)
    await bucket.acquire()
    await bucket.acquire()
    assert sleeps == []
    await bucket.acquire()
    assert sleeps == pytest.approx([1.0])


async def test_refill_over_time_replenishes() -> None:
    clock = FakeClock()
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)
        clock.now += delay

    bucket = TokenBucket(60, burst=2, clock=clock, sleep=sleep)
    await bucket.acquire()
    await bucket.acquire()
    clock.now += 5.0
    await bucket.acquire()
    await bucket.acquire()
    assert sleeps == []


@pytest.mark.parametrize("rate", [0, -5])
def test_invalid_rate_is_rejected(rate: int) -> None:
    with pytest.raises(ValueError):
        TokenBucket(rate)


@pytest.mark.parametrize("burst", [0, -1])
def test_invalid_burst_is_rejected(burst: int) -> None:
    with pytest.raises(ValueError):
        TokenBucket(60, burst=burst)


async def test_request_larger_than_capacity_is_rejected() -> None:
    async def sleep(_: float) -> None:
        return None

    bucket = TokenBucket(60, burst=2, clock=FakeClock(), sleep=sleep)
    with pytest.raises(ValueError):
        await bucket.acquire(5)


async def test_non_positive_tokens_are_rejected() -> None:
    async def sleep(_: float) -> None:
        return None

    bucket = TokenBucket(60, clock=FakeClock(), sleep=sleep)
    with pytest.raises(ValueError):
        await bucket.acquire(0)
