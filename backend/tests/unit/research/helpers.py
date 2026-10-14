"""Builders and fixture loaders for research adapter tests."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from app.cost import CostMeter
from app.research.adapters import AdapterDeps, HackerNewsSignals, RedditSignals, WebSearch
from app.research.cache import InMemoryCache
from app.research.contract import Cache
from app.research.ratelimit import TokenBucket

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "research"
FAST_RATE_PER_MINUTE = 10_000_000


def load_fixture(name: str) -> object:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


async def no_sleep(_: float) -> None:
    return None


def fast_deps(
    client: httpx.AsyncClient,
    *,
    cache: Cache | None = None,
    meter: CostMeter | None = None,
    ttl_seconds: int = 3600,
    retries: int = 2,
) -> AdapterDeps:
    return AdapterDeps(
        client=client,
        cache=cache if cache is not None else InMemoryCache(),
        rate_limiter=TokenBucket(FAST_RATE_PER_MINUTE),
        meter=meter,
        timeout_seconds=1.0,
        retries=retries,
        snippet_max_chars=1500,
        ttl_seconds=ttl_seconds,
        sleep=no_sleep,
    )


def make_web(
    client: httpx.AsyncClient,
    *,
    cache: Cache | None = None,
    meter: CostMeter | None = None,
    api_key: str = "test-key",
    retries: int = 2,
) -> WebSearch:
    return WebSearch(
        api_key=api_key,
        cost_per_search_usd=0.008,
        deps=fast_deps(client, cache=cache, meter=meter, retries=retries),
    )


def make_reddit(
    client: httpx.AsyncClient,
    *,
    cache: Cache | None = None,
    client_id: str = "client-id",
    client_secret: str = "client-secret",
    clock: Callable[[], float] = time.monotonic,
) -> RedditSignals:
    return RedditSignals(
        client_id=client_id,
        client_secret=client_secret,
        user_agent="idea-forge-test/0.1",
        deps=fast_deps(client, cache=cache),
        clock=clock,
    )


def make_hn(client: httpx.AsyncClient, *, cache: Cache | None = None) -> HackerNewsSignals:
    return HackerNewsSignals(deps=fast_deps(client, cache=cache))
