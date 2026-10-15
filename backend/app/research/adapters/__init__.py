"""HTTP providers behind the research tools.

Each provider implements one official API and maps its payload to evidence;
tools in :mod:`app.research.tools` add caching and the public surface. Shared
transport helpers live here: bounded retries on 429/5xx and transport errors,
and body decoding that never trusts the provider's shape. Only official APIs
are called; nothing here scrapes or bypasses rate limits.
"""

from __future__ import annotations

from typing import Any, cast

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.obs import get_logger

logger = get_logger(__name__)

RETRY_WAIT = wait_exponential_jitter(multiplier=0.2, max=2.0, jitter=0.2)


class RetryableStatusError(Exception):
    """Internal marker for a 429/5xx response worth retrying."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"retryable HTTP status {status_code}")
        self.status_code = status_code


def json_object(response: httpx.Response) -> dict[str, Any] | None:
    """Decode a JSON object body; ``None`` for anything else, never raising."""
    try:
        data = response.json()
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    return cast("dict[str, Any]", data)


def as_float(value: object) -> float | None:
    """Numeric value when ``value`` is a real number (bools excluded)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def as_str(value: object) -> str:
    """The string itself, or an empty string for ``None`` and non-strings."""
    return value if isinstance(value, str) else ""


async def request_with_retries(
    http: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_retries: int,
    request_timeout: float,
    headers: dict[str, str] | None = None,
    params: dict[str, str | int] | None = None,
    json: dict[str, object] | None = None,
    data: dict[str, str] | None = None,
    auth: tuple[str, str] | None = None,
) -> httpx.Response | None:
    """One HTTP request with bounded exponential-jitter retries.

    Retries cover 429, 5xx, and transport errors (network and timeouts). Returns
    the delivered response whatever its status, or ``None`` when every attempt
    failed; callers turn that into an empty result so one tool never fails a run.
    """
    retrying = AsyncRetrying(
        stop=stop_after_attempt(1 + max_retries),
        wait=RETRY_WAIT,
        retry=retry_if_exception_type((httpx.TransportError, RetryableStatusError)),
        reraise=True,
    )
    try:
        async for attempt in retrying:
            with attempt:
                response = await http.request(
                    method,
                    url,
                    timeout=request_timeout,
                    headers=headers,
                    params=params,
                    json=json,
                    data=data,
                    auth=auth,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    raise RetryableStatusError(response.status_code)
                return response
    except (httpx.TransportError, RetryableStatusError) as exc:
        logger.warning("request to %s failed after retries: %s", url, exc)
        return None
    return None
