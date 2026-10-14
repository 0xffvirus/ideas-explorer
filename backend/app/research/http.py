"""Resilient JSON fetching: timeout, bounded retries with jitter, never raises."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable, Mapping

import httpx

from app.obs import get_logger

logger = get_logger(__name__)

TRANSIENT_STATUS = frozenset({429, 500, 502, 503, 504})
SleepFn = Callable[[float], Awaitable[None]]
AttemptHook = Callable[[], Awaitable[None]]


async def fetch_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    timeout_seconds: float,
    retries: int,
    headers: Mapping[str, str] | None = None,
    params: Mapping[str, str] | None = None,
    data: Mapping[str, str] | None = None,
    json: object | None = None,
    auth: tuple[str, str] | None = None,
    backoff_base_seconds: float = 0.5,
    sleep: SleepFn = asyncio.sleep,
    rng: random.Random | None = None,
    on_attempt: AttemptHook | None = None,
) -> object | None:
    """Fetch and parse JSON, retrying transient failures with jitter.

    Returns ``None`` once the retry budget is exhausted, on non-transient
    client errors, or on an unparseable body. It never raises for a failed
    request so that one tool failure can never fail a run. ``on_attempt``
    runs before every request attempt, which lets callers rate-limit each
    retry rather than each logical fetch.
    """
    attempts = max(0, retries) + 1
    random_source = rng if rng is not None else random.Random()
    for attempt in range(attempts):
        last_attempt = attempt == attempts - 1
        if on_attempt is not None:
            await on_attempt()
        detail: str
        try:
            response = await client.request(
                method,
                url,
                timeout=timeout_seconds,
                headers=headers,
                params=params,
                data=data,
                json=json,
                auth=auth,
            )
        except httpx.HTTPError as exc:
            detail = f"{type(exc).__name__}: {exc}"
            if last_attempt:
                logger.warning("research fetch failed url=%r error=%r", url, detail)
                return None
            await _backoff(attempt, backoff_base_seconds, sleep=sleep, rng=random_source)
            continue
        if response.status_code in TRANSIENT_STATUS:
            if last_attempt:
                logger.warning("research fetch failed url=%r status=%d", url, response.status_code)
                return None
            await _backoff(attempt, backoff_base_seconds, sleep=sleep, rng=random_source)
            continue
        if response.status_code >= 400:
            logger.warning("research fetch rejected url=%r status=%d", url, response.status_code)
            return None
        try:
            return response.json()
        except ValueError:
            logger.warning("research fetch returned invalid JSON url=%r", url)
            return None
    return None


async def _backoff(
    attempt: int,
    base_seconds: float,
    *,
    sleep: SleepFn,
    rng: random.Random,
) -> None:
    ceiling = base_seconds * (2**attempt)
    await sleep(rng.uniform(0.0, ceiling))
