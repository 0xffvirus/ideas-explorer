"""Async HTTP client for the Jev System One API.

Wire contract (docs.typesafe.ai): ``POST {base_url}/systemone`` with a Bearer
token and ``{"state", "model", "questions"}``; the response carries
``{"model", "answers", "usage"}``. Questions beyond ``max_questions_per_call``
are chunked and the chunks are run concurrently.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

import httpx
from pydantic import ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import ModelPrice, get_settings
from app.cost import CostMeter
from app.jev.errors import JevProtocolError, JevUnavailableError
from app.jev.types import (
    ANSWER_ADAPTER,
    Answer,
    AskResult,
    NoulQuestion,
    Question,
    Usage,
)

_RETRY_ATTEMPTS = 3
_RETRY_WAIT = wait_exponential_jitter(multiplier=0.2, max=2.0, jitter=0.2)


class _RetryableStatusError(Exception):
    """Internal marker for a 429 or 5xx response worth retrying."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"retryable Jev HTTP status {status_code}")
        self.status_code = status_code


def _question_payload(question: Question) -> dict[str, Any]:
    payload = question.model_dump()
    if isinstance(question, NoulQuestion) and question.criteria is None:
        payload.pop("criteria", None)
    return payload


class JevClient:
    """Thin typed wrapper around the Jev System One endpoint."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
        max_questions_per_call: int = 20,
        http_client: httpx.AsyncClient | None = None,
        meter: CostMeter | None = None,
        pricing: dict[str, ModelPrice] | None = None,
    ) -> None:
        if max_questions_per_call < 1:
            raise ValueError("max_questions_per_call must be at least 1")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._max_questions_per_call = max_questions_per_call
        self._meter = meter
        self._pricing = pricing
        self._http = (
            http_client if http_client is not None else httpx.AsyncClient(timeout=timeout_seconds)
        )
        self._owns_http = http_client is None

    @property
    def endpoint(self) -> str:
        return f"{self._base_url}/systemone"

    async def aclose(self) -> None:
        """Close the underlying HTTP client when this instance owns it."""
        if self._owns_http:
            await self._http.aclose()

    async def ask(self, state: str | dict[str, Any], questions: dict[str, Question]) -> AskResult:
        """Ask Jev every question against ``state`` and merge the chunked results."""
        if not questions:
            return AskResult(answers={}, usage=Usage(), raw_model=None)
        items = list(questions.items())
        chunks = [
            dict(items[index : index + self._max_questions_per_call])
            for index in range(0, len(items), self._max_questions_per_call)
        ]
        results = await asyncio.gather(*(self._ask_chunk(state, chunk) for chunk in chunks))
        answers: dict[str, Answer] = {}
        input_tokens = 0
        output_tokens = 0
        raw_model: str | None = None
        for result in results:
            answers.update(result.answers)
            input_tokens += result.usage.input_tokens
            output_tokens += result.usage.output_tokens
            if raw_model is None:
                raw_model = result.raw_model
        return AskResult(
            answers=answers,
            usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
            raw_model=raw_model,
        )

    async def _ask_chunk(
        self, state: str | dict[str, Any], chunk: dict[str, Question]
    ) -> AskResult:
        payload: dict[str, Any] = {
            "state": state,
            "model": self._model,
            "questions": {
                question_id: _question_payload(question) for question_id, question in chunk.items()
            },
        }
        response = await self._post(payload)
        data = self._decode(response)
        answers = self._parse_answers(data, chunk)
        usage = self._parse_usage(data)
        self._charge(usage)
        model = data.get("model")
        return AskResult(
            answers=answers,
            usage=usage,
            raw_model=model if isinstance(model, str) else None,
        )

    async def _post(self, payload: dict[str, Any]) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        retrying = AsyncRetrying(
            stop=stop_after_attempt(_RETRY_ATTEMPTS),
            wait=_RETRY_WAIT,
            retry=retry_if_exception_type((httpx.TransportError, _RetryableStatusError)),
            reraise=True,
        )
        try:
            async for attempt in retrying:
                with attempt:
                    response = await self._http.post(self.endpoint, json=payload, headers=headers)
                    if response.status_code == 429 or response.status_code >= 500:
                        raise _RetryableStatusError(response.status_code)
                    return response
        except (httpx.TransportError, _RetryableStatusError) as exc:
            raise JevUnavailableError(f"Jev request to {self.endpoint} failed: {exc}") from exc
        raise JevUnavailableError(f"Jev request to {self.endpoint} failed after retries")

    def _decode(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code != 200:
            body = response.text[:300]
            raise JevProtocolError(f"Jev returned HTTP {response.status_code}: {body}")
        try:
            data = response.json()
        except ValueError as exc:
            raise JevProtocolError("Jev returned a non-JSON body") from exc
        if not isinstance(data, dict):
            raise JevProtocolError("Jev returned a non-object body")
        return cast("dict[str, Any]", data)

    def _parse_answers(self, data: dict[str, Any], chunk: dict[str, Question]) -> dict[str, Answer]:
        raw = data.get("answers")
        if not isinstance(raw, dict):
            raise JevProtocolError("Jev response is missing the 'answers' object")
        answers: dict[str, Answer] = {}
        for question_id in chunk:
            if question_id not in raw:
                raise JevProtocolError(f"Jev returned no answer for question {question_id!r}")
            try:
                answers[question_id] = ANSWER_ADAPTER.validate_python(raw[question_id])
            except ValidationError as exc:
                raise JevProtocolError(
                    f"Jev returned an invalid answer for question {question_id!r}: {exc}"
                ) from exc
        return answers

    def _parse_usage(self, data: dict[str, Any]) -> Usage:
        raw = data.get("usage")
        if raw is None:
            return Usage()
        try:
            return Usage.model_validate(raw)
        except ValidationError as exc:
            raise JevProtocolError("Jev returned an invalid 'usage' object") from exc

    def _charge(self, usage: Usage) -> None:
        if self._meter is None or self._pricing is None:
            return
        settings = get_settings()
        default = ModelPrice(
            input=settings.jev_input_usd_per_million,
            output=settings.jev_output_usd_per_million,
        )
        self._meter.charge_tokens(
            model=self._model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            category="jev",
            pricing=self._pricing,
            default=default,
        )
