"""Application composition tests: routers, prefixes, and dependency wiring.

Runs the real ``create_app`` factory through ``TestClient`` with no database
connection: the lifespan only configures logging and disposes a never-connected
engine, so every request here is answered in-process without network access.

These tests catch wiring bugs (missing routers, wrong prefixes, lost dependency
overrides, CORS misconfiguration) that per-router integration tests cannot.
"""

from __future__ import annotations

from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.config import get_settings
from app.ideas.api import get_analysis_enqueuer
from app.main import create_app
from app.pipeline import SqlAnalysisEnqueuer

EXPECTED_PATHS = (
    "/ideas",
    "/ideas/{idea_id}",
    "/runs/{run_id}",
    "/runs/{run_id}/events",
    "/ideas/{idea_id}/report",
    "/ideas/{idea_id}/report.md",
    "/ideas/{idea_id}/report.pdf",
    "/compare",
    "/tags",
)


def test_health_endpoint_is_up() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_exposes_every_module_route() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    for path in EXPECTED_PATHS:
        assert path in paths, f"missing route {path}"


def test_analysis_enqueuer_override_resolves_to_sql_enqueuer() -> None:
    app = create_app()
    assert get_analysis_enqueuer in app.dependency_overrides
    resolved = app.dependency_overrides[get_analysis_enqueuer]()
    assert isinstance(resolved, SqlAnalysisEnqueuer)


def test_cors_middleware_is_configured_with_settings_origins() -> None:
    app = create_app()
    cors = [middleware for middleware in app.user_middleware if middleware.cls is CORSMiddleware]
    assert len(cors) == 1
    assert cors[0].kwargs["allow_origins"] == get_settings().api_cors_origins
    assert cors[0].kwargs["allow_credentials"] is True
