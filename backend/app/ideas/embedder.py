"""Embedding port and the OpenAI adapter."""

from __future__ import annotations

from typing import Protocol

from openai import AsyncOpenAI


class EmbeddingError(RuntimeError):
    """Raised when an embedding provider fails."""


class Embedder(Protocol):
    """Turns text into vectors; implemented by OpenAI and by test fakes."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in order."""
        ...


class OpenAIEmbedder:
    """Async OpenAI embeddings client behind the :class:`Embedder` protocol.

    The client is created lazily so a missing API key never fails at import or
    construction time; the first ``embed`` call raises :class:`EmbeddingError`
    instead, which callers treat as "save without a vector" (retried by worker).
    """

    def __init__(self, api_key: str, model: str, dimensions: int) -> None:
        self._api_key = api_key
        self._client: AsyncOpenAI | None = None
        self._model = model
        self._dimensions = dimensions

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            if not self._api_key:
                raise EmbeddingError("OPENAI_API_KEY is not configured")
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed ``texts`` in a single request; raises :class:`EmbeddingError` on failure."""
        try:
            client = self._get_client()
            response = await client.embeddings.create(
                model=self._model,
                input=texts,
                dimensions=self._dimensions,
            )
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(f"OpenAI embedding request failed: {exc}") from exc
        return [list(item.embedding) for item in response.data]
