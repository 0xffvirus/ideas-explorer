"""Guardrails: outbound-network blocking, ask-first defaults, and eval gating."""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from app.config import settings_as_test_overrides

BACKEND_DIR = Path(__file__).resolve().parents[2]


def test_non_loopback_tcp_connect_is_blocked() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(RuntimeError, match="outbound network is blocked"):
            sock.connect(("93.184.216.34", 80))
    finally:
        sock.close()


def test_non_loopback_ipv6_connect_is_blocked() -> None:
    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    try:
        with pytest.raises(RuntimeError, match="outbound network is blocked"):
            sock.connect(("2001:db8::1", 443, 0, 0))
    finally:
        sock.close()


def test_loopback_and_unix_connects_are_allowed_through() -> None:
    loopback = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(ConnectionRefusedError):
            loopback.connect(("127.0.0.1", 1))
    finally:
        loopback.close()

    unix = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        with pytest.raises(FileNotFoundError):
            unix.connect("/tmp/idea-forge-tests-definitely-missing.sock")
    finally:
        unix.close()


def test_ask_first_defaults_are_unchanged() -> None:
    settings = settings_as_test_overrides()
    assert settings.run_cost_cap_usd == 0.75
    assert settings.jev_confidence_floor == 0.6
    assert settings.jev_claim_threshold == 0.7
    assert settings.step_timeout_seconds == 120.0
    assert settings.leads_enabled is False


def _run_pytest(
    *args: str,
    env_overrides: dict[str, str] | None = None,
    remove_env: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    for key in remove_env:
        env.pop(key, None)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_eval_module_skips_without_run_evals() -> None:
    result = _run_pytest(
        "tests/eval",
        "-m",
        "eval",
        remove_env=("RUN_EVALS", "TYPESAFE_API_KEY", "OPENAI_API_KEY", "TAVILY_API_KEY"),
    )
    assert "2 skipped" in result.stdout
    assert "failed" not in result.stdout.lower()
    assert "error" not in result.stdout.lower()


def test_eval_marker_collects_only_the_eval_modules() -> None:
    result = _run_pytest(
        "tests/eval",
        "-m",
        "eval",
        "--collect-only",
        env_overrides={
            "RUN_EVALS": "1",
            "TYPESAFE_API_KEY": "test-key",
            "OPENAI_API_KEY": "test-key",
            "TAVILY_API_KEY": "test-key",
        },
    )
    assert result.returncode == 0, result.stderr
    node_ids = [
        line for line in result.stdout.splitlines() if re.match(r"^tests/eval/[^:]+::\S+$", line)
    ]
    assert node_ids == [
        "tests/eval/test_jev_catalog_eval.py::test_golden_ideas_classify_and_score",
        "tests/eval/test_pipeline_live_eval.py::test_golden_ideas_through_the_live_pipeline",
    ]
