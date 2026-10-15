"""Deterministic offline embedder for tests and local development."""

from __future__ import annotations

import hashlib
import math
import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_FINGERPRINT_WEIGHT = 0.05


class FakeEmbedder:
    """Bag-of-words hashing embedder: shared tokens yield higher cosine similarity.

    Vectors are unit-norm and fully deterministic (``hashlib`` only, no network),
    so the same text always produces the same vector and different texts differ.
    A light plural normalization maps ``pets`` and ``pet`` to the same bucket.
    """

    def __init__(self, dimensions: int = 1536) -> None:
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        """Vector width this embedder produces."""
        return self._dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one deterministic unit vector per text."""
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        for token in _tokenize(text):
            index, sign = _bucket(token, self._dimensions)
            vector[index] += sign
        index, sign = _bucket(f"\x00{text}", self._dimensions)
        vector[index] += _FINGERPRINT_WEIGHT * sign
        norm = math.sqrt(sum(component * component for component in vector))
        if norm == 0.0:
            vector[0] = 1.0
            return vector
        return [component / norm for component in vector]


def _tokenize(text: str) -> list[str]:
    return [_singularize(token) for token in _TOKEN_RE.findall(text.lower())]


def _singularize(token: str) -> str:
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _bucket(value: str, dimensions: int) -> tuple[int, float]:
    digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest()
    raw = int.from_bytes(digest, "little")
    return raw % dimensions, 1.0 if (raw >> 63) & 1 == 0 else -1.0
