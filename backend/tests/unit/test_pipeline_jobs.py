"""Unit tests for job backoff math (no DB)."""

from __future__ import annotations

from app.pipeline.jobs import MAX_JOB_ATTEMPTS, backoff_seconds


def test_backoff_grows_exponentially_and_caps() -> None:
    assert backoff_seconds(0) == 2.0
    assert backoff_seconds(1) == 2.0
    assert backoff_seconds(2) == 4.0
    assert backoff_seconds(3) == 8.0
    assert backoff_seconds(5) == 32.0
    assert backoff_seconds(6) == 60.0
    assert backoff_seconds(50) == 60.0
    assert backoff_seconds(-3) == 2.0


def test_max_attempts_is_three() -> None:
    assert MAX_JOB_ATTEMPTS == 3
