"""Contract tests for the production ``OpenAIEmbedder`` (no network).

The real client is instantiated with an ``httpx.MockTransport`` so the tests can
assert the exact ``/embeddings`` request body and the response mapping, and that
every provider or transport failure surfaces as ``EmbeddingError``.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from openai import AsyncOpenAI

from app.ideas.embedder import EmbeddingError, OpenAIEmbedder

MODEL = "text-embedding-3-small"
DIMENSIONS = 4


def _embedding_response(vectors: list[list[float]]) -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {"object": "embedding", "index": index, "embedding": vector}
            for index, vector in enumerate(vectors)
        ],
        "model": MODEL,
        "usage": {"prompt_tokens": 2, "total_tokens": 2},
    }


def _install_mock_client(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
) -> None:
    """Replace ``AsyncOpenAI`` with a factory wired to the mock transport."""

    def factory(*args: Any, **kwargs: Any) -> AsyncOpenAI:
        kwargs["http_client"] = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        kwargs["max_retries"] = 0
        return AsyncOpenAI(*args, **kwargs)

    monkeypatch.setattr("app.ideas.embedder.AsyncOpenAI", factory)


async def test_embed_sends_model_dimensions_and_input_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=_embedding_response(
                [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8], [0.9, 1.0, 1.1, 1.2]]
            ),
        )

    _install_mock_client(monkeypatch, handler)
    embedder = OpenAIEmbedder(api_key="test-key", model=MODEL, dimensions=DIMENSIONS)

    vectors = await embedder.embed(["first text", "second text", "third text"])

    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.host == "api.openai.com"
    assert requests[0].url.path.endswith("/embeddings")
    assert requests[0].headers["authorization"] == "Bearer test-key"
    body = json.loads(requests[0].content)
    assert body["model"] == MODEL
    assert body["dimensions"] == DIMENSIONS
    assert body["input"] == ["first text", "second text", "third text"]
    assert vectors == [
        [0.1, 0.2, 0.3, 0.4],
        [0.5, 0.6, 0.7, 0.8],
        [0.9, 1.0, 1.1, 1.2],
    ]


async def test_single_text_still_sends_an_input_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_embedding_response([[1.0, 0.0, 0.0, 0.0]]))

    _install_mock_client(monkeypatch, handler)
    embedder = OpenAIEmbedder(api_key="test-key", model=MODEL, dimensions=DIMENSIONS)

    vectors = await embedder.embed(["only text"])

    assert json.loads(requests[0].content)["input"] == ["only text"]
    assert vectors == [[1.0, 0.0, 0.0, 0.0]]


async def test_api_error_is_wrapped_in_embedding_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            json={"error": {"message": "upstream exploded", "type": "server_error"}},
        )

    _install_mock_client(monkeypatch, handler)
    embedder = OpenAIEmbedder(api_key="test-key", model=MODEL, dimensions=DIMENSIONS)

    with pytest.raises(EmbeddingError, match="OpenAI embedding request failed"):
        await embedder.embed(["text"])


async def test_transport_error_is_wrapped_in_embedding_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    _install_mock_client(monkeypatch, handler)
    embedder = OpenAIEmbedder(api_key="test-key", model=MODEL, dimensions=DIMENSIONS)

    with pytest.raises(EmbeddingError, match="OpenAI embedding request failed"):
        await embedder.embed(["text"])
