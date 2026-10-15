"""Unit tests for run-event sequencing and SSE serialization (no DB)."""

from __future__ import annotations

import json
import uuid

from app.pipeline.models import RunEvent, next_event_seq, run_event_to_sse


def test_next_event_seq_starts_at_one_and_is_gap_free() -> None:
    assert next_event_seq(None) == 1
    assert next_event_seq(0) == 1
    assert next_event_seq(1) == 2
    assert next_event_seq(41) == 42


def test_run_event_sse_serialization() -> None:
    event = RunEvent(
        run_id=uuid.uuid4(),
        seq=7,
        event="step_completed",
        step="market",
        data={"step": "market", "status": "done"},
    )
    payload = run_event_to_sse(event)
    assert payload["id"] == "7"
    assert payload["event"] == "step_completed"
    assert json.loads(payload["data"]) == {"step": "market", "status": "done"}
    assert set(payload) == {"id", "event", "data"}


def test_run_event_serialization_handles_empty_data() -> None:
    event = RunEvent(run_id=uuid.uuid4(), seq=1, event="run_done", step=None, data={})
    payload = run_event_to_sse(event)
    assert json.loads(payload["data"]) == {}
