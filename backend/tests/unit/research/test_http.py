"""Unit tests for the resilient JSON fetcher."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.research.http import fetch_json

URL = "https://example.com/api"


class SleepRecorder:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


@respx.mock
async def test_returns_parsed_json(http_client: httpx.AsyncClient) -> None:
    respx.get(URL).mock(return_value=httpx.Response(200, json={"answer": 42}))
    result = await fetch_json(http_client, "GET", URL, timeout_seconds=1.0, retries=2)
    assert result == {"answer": 42}


@respx.mock
async def test_429_storm_is_bounded_and_returns_none(http_client: httpx.AsyncClient) -> None:
    sleeps = SleepRecorder()
    route = respx.get(URL).mock(return_value=httpx.Response(429))
    result = await fetch_json(http_client, "GET", URL, timeout_seconds=1.0, retries=2, sleep=sleeps)
    assert result is None
    assert route.call_count == 3
    assert len(sleeps.delays) == 2


@respx.mock
async def test_transient_5xx_then_success(http_client: httpx.AsyncClient) -> None:
    route = respx.get(URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"ok": True})]
    )
    result = await fetch_json(http_client, "GET", URL, timeout_seconds=1.0, retries=2)
    assert result == {"ok": True}
    assert route.call_count == 2


@respx.mock
async def test_client_error_is_not_retried(http_client: httpx.AsyncClient) -> None:
    sleeps = SleepRecorder()
    route = respx.get(URL).mock(return_value=httpx.Response(404))
    result = await fetch_json(http_client, "GET", URL, timeout_seconds=1.0, retries=2, sleep=sleeps)
    assert result is None
    assert route.call_count == 1
    assert sleeps.delays == []


@respx.mock
async def test_network_timeout_is_retried_then_returns_none(http_client: httpx.AsyncClient) -> None:
    sleeps = SleepRecorder()
    route = respx.get(URL).mock(side_effect=httpx.ConnectTimeout("boom"))
    result = await fetch_json(http_client, "GET", URL, timeout_seconds=1.0, retries=2, sleep=sleeps)
    assert result is None
    assert route.call_count == 3
    assert len(sleeps.delays) == 2


@respx.mock
async def test_invalid_json_returns_none_without_retry(http_client: httpx.AsyncClient) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(200, content=b"not json"))
    result = await fetch_json(http_client, "GET", URL, timeout_seconds=1.0, retries=2)
    assert result is None
    assert route.call_count == 1


class RecordingRng:
    def __init__(self) -> None:
        self.calls: list[tuple[float, float]] = []

    def uniform(self, lower: float, upper: float) -> float:
        self.calls.append((lower, upper))
        return lower


@respx.mock
async def test_backoff_ceilings_follow_exponential_schedule(
    http_client: httpx.AsyncClient,
) -> None:
    sleeps = SleepRecorder()
    rng = RecordingRng()
    respx.get(URL).mock(return_value=httpx.Response(500))
    result = await fetch_json(
        http_client,
        "GET",
        URL,
        timeout_seconds=1.0,
        retries=2,
        backoff_base_seconds=0.5,
        sleep=sleeps,
        rng=rng,  # type: ignore[arg-type]
    )
    assert result is None
    assert rng.calls == [(0.0, 0.5), (0.0, 1.0)]
    assert sleeps.delays == [0.0, 0.0]


@respx.mock
async def test_on_attempt_hook_runs_before_every_attempt(http_client: httpx.AsyncClient) -> None:
    attempts: list[int] = []

    async def on_attempt() -> None:
        attempts.append(len(attempts) + 1)

    respx.get(URL).mock(return_value=httpx.Response(503))
    result = await fetch_json(
        http_client,
        "GET",
        URL,
        timeout_seconds=1.0,
        retries=2,
        sleep=SleepRecorder(),
        on_attempt=on_attempt,
    )
    assert result is None
    assert attempts == [1, 2, 3]


@respx.mock
async def test_retries_zero_means_single_attempt(http_client: httpx.AsyncClient) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(500))
    result = await fetch_json(http_client, "GET", URL, timeout_seconds=1.0, retries=0)
    assert result is None
    assert route.call_count == 1


@pytest.mark.parametrize("status", [500, 502, 503, 504, 429])
@respx.mock
async def test_transient_statuses_are_retried(http_client: httpx.AsyncClient, status: int) -> None:
    sleeps = SleepRecorder()
    route = respx.get(URL).mock(return_value=httpx.Response(status))
    result = await fetch_json(http_client, "GET", URL, timeout_seconds=1.0, retries=1, sleep=sleeps)
    assert result is None
    assert route.call_count == 2
