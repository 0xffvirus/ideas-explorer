"""Errors raised by the Jev gate."""

from __future__ import annotations


class JevProtocolError(Exception):
    """The Jev response did not match the documented wire format."""


class JevUnavailableError(Exception):
    """Jev was unreachable or kept failing with a retryable error."""
