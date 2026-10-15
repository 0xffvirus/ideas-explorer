"""Unit tests for the worker process wiring: one shared HTTP client per provider."""

from __future__ import annotations

from typing import Any, ClassVar

import pytest

from app import worker as worker_module
from app.config import ModelPrice, settings_as_test_overrides
from app.cost import CostMeter
from app.jev import Gate


class _RecordingJevClient:
    """Stand-in for ``JevClient`` that records its constructor arguments."""

    created: ClassVar[list[_RecordingJevClient]] = []

    def __init__(self, api_key: str, **kwargs: Any) -> None:
        self.api_key = api_key
        self.meter = kwargs.get("meter")
        self.pricing = kwargs.get("pricing")
        self.http_client = kwargs.get("http_client")
        _RecordingJevClient.created.append(self)


async def test_build_worker_clients_reuses_shared_http_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = settings_as_test_overrides(
        jev_input_usd_per_million=3.0,
        jev_output_usd_per_million=9.0,
    )
    _RecordingJevClient.created = []
    tools_calls: list[dict[str, Any]] = []

    def recording_build_default_tools(_settings: Any, **kwargs: Any) -> dict[str, Any]:
        tools_calls.append(kwargs)
        return {}

    monkeypatch.setattr(worker_module, "JevClient", _RecordingJevClient)
    monkeypatch.setattr(worker_module, "build_default_tools", recording_build_default_tools)

    clients = worker_module.build_worker_clients(settings, session_factory=None)
    try:
        meter_one = CostMeter()
        meter_two = CostMeter()
        assert clients.tools_factory(meter_one) == {}
        assert clients.tools_factory(meter_two) == {}
        assert [call["http_client"] for call in tools_calls] == [
            clients.http_client,
            clients.http_client,
        ]
        assert [call["meter"] for call in tools_calls] == [meter_one, meter_two]

        assert isinstance(clients.gate_factory(meter_one), Gate)
        assert isinstance(clients.gate_factory(meter_two), Gate)

        per_run = [client for client in _RecordingJevClient.created if client.meter is not None]
        assert [client.meter for client in per_run] == [meter_one, meter_two]
        assert all(client.http_client is clients.jev_http_client for client in per_run)
        assert per_run[0].pricing == {"jev-latest": ModelPrice(input=3.0, output=9.0)}
        assert clients.jev_client.http_client is clients.jev_http_client
        assert clients.jev_client.meter is None
    finally:
        await clients.aclose()

    assert clients.http_client.is_closed
    assert clients.jev_http_client.is_closed
