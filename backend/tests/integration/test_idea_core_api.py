"""Integration tests for the idea-core FastAPI router (auto-skipped without Postgres)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.ideas.api import get_analysis_enqueuer, get_embedder, router
from app.ideas.testing import FakeEmbedder

pytestmark = pytest.mark.integration


@pytest.fixture
async def api_app(db_session: AsyncSession) -> AsyncIterator[FastAPI]:
    app = FastAPI()
    app.include_router(router)

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_embedder] = lambda: FakeEmbedder()
    app.dependency_overrides[get_analysis_enqueuer] = lambda: None
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def client(api_app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def test_create_get_patch_and_versions(client: AsyncClient) -> None:
    created = await client.post("/ideas", json={"raw_input": "A dog walking app for pet owners"})
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "queued"
    assert body["title"] == "A dog walking app for pet owners"
    assert body["latest_version"]["number"] == 1

    idea_id = body["id"]
    fetched = await client.get(f"/ideas/{idea_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == idea_id

    patched = await client.patch(f"/ideas/{idea_id}", json={"pinned": True, "tags": ["ai", "ml"]})
    assert patched.status_code == 200
    assert patched.json()["pinned"] is True
    assert patched.json()["tags"] == ["ai", "ml"]

    versioned = await client.post(
        f"/ideas/{idea_id}/versions", json={"raw_input": "second draft", "analyze": False}
    )
    assert versioned.status_code == 201
    assert [version["number"] for version in versioned.json()["versions"]] == [1, 2]

    similar = await client.get(f"/ideas/{idea_id}/similar")
    assert similar.status_code == 200
    assert similar.json() == []

    tags = await client.get("/tags")
    assert tags.status_code == 200
    assert tags.json() == [{"name": "ai", "count": 1}, {"name": "ml", "count": 1}]


async def test_validation_and_not_found(client: AsyncClient) -> None:
    assert (await client.post("/ideas", json={"raw_input": ""})).status_code == 422
    assert (await client.post("/ideas", json={"raw_input": "x" * 5001})).status_code == 422
    assert (await client.post("/ideas", json={})).status_code == 422
    assert (
        await client.post("/ideas", json={"raw_input": "x", "tags": ["t"] * 21})
    ).status_code == 422
    assert (
        await client.post("/ideas", json={"raw_input": "x", "tags": ["t" * 51]})
    ).status_code == 422
    assert (await client.post("/ideas", json={"raw_input": "x", "tags": ["  "]})).status_code == 422
    assert (
        await client.post("/ideas", json={"raw_input": "x", "context": {"blob": "y" * 10_001}})
    ).status_code == 422

    created = await client.post("/ideas", json={"raw_input": "versioned", "analyze": False})
    idea_id = created.json()["id"]
    assert (
        await client.post(
            f"/ideas/{idea_id}/versions",
            json={"raw_input": "x", "context": {"blob": "y" * 10_001}},
        )
    ).status_code == 422

    missing = uuid.uuid4()
    assert (await client.get(f"/ideas/{missing}")).status_code == 404
    assert (await client.patch(f"/ideas/{missing}", json={"pinned": True})).status_code == 404
    versions = await client.post(f"/ideas/{missing}/versions", json={"raw_input": "x"})
    assert versions.status_code == 404
    assert (await client.get(f"/ideas/{missing}/similar")).status_code == 404

    assert (await client.get("/ideas", params={"cursor": "not-a-real-cursor"})).status_code == 422
    assert (await client.get("/ideas", params={"limit": 0})).status_code == 422
    assert (await client.get("/ideas", params={"limit": 101})).status_code == 422
    assert (await client.get("/ideas", params={"mode": "bogus"})).status_code == 422
    assert (await client.get("/ideas", params={"sort": "bogus"})).status_code == 422
    assert (await client.get("/ideas", params={"sort": "title"})).status_code == 200


async def test_tags_are_trimmed_and_deduplicated_by_the_api(client: AsyncClient) -> None:
    created = await client.post(
        "/ideas",
        json={"raw_input": "a tagged idea", "tags": [" AI ", "ai", "ML"], "analyze": False},
    )
    assert created.status_code == 201
    assert created.json()["tags"] == ["AI", "ML"]

    idea_id = created.json()["id"]
    patched = await client.patch(f"/ideas/{idea_id}", json={"tags": ["ai", " AI ", "ml"]})
    assert patched.status_code == 200
    assert patched.json()["tags"] == ["ai", "ml"]


async def test_archived_visibility_via_api(client: AsyncClient) -> None:
    first = (await client.post("/ideas", json={"raw_input": "first", "analyze": False})).json()
    second = (await client.post("/ideas", json={"raw_input": "second", "analyze": False})).json()

    archived = await client.patch(f"/ideas/{second['id']}", json={"archived": True})
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None

    default = (await client.get("/ideas")).json()
    assert [item["id"] for item in default["items"]] == [first["id"]]
    only_archived = (await client.get("/ideas", params={"archived": "true"})).json()
    assert [item["id"] for item in only_archived["items"]] == [second["id"]]


async def test_search_modes_and_pagination_via_api(client: AsyncClient) -> None:
    await client.post(
        "/ideas", json={"raw_input": "Marketplace for vintage bicycles", "analyze": False}
    )
    await client.post("/ideas", json={"raw_input": "B2B payroll automation", "analyze": False})
    keyword = await client.get("/ideas", params={"q": "bicycles", "mode": "keyword"})
    assert keyword.status_code == 200
    assert [item["title"] for item in keyword.json()["items"]] == [
        "Marketplace for vintage bicycles"
    ]

    hybrid = await client.get("/ideas", params={"q": "bicycles", "mode": "hybrid"})
    assert hybrid.json()["items"][0]["title"] == "Marketplace for vintage bicycles"

    page = await client.get("/ideas", params={"limit": 1})
    assert page.status_code == 200
    body = page.json()
    assert len(body["items"]) == 1
    assert body["next_cursor"] is not None

    second_page = await client.get("/ideas", params={"limit": 1, "cursor": body["next_cursor"]})
    assert second_page.status_code == 200
    assert [item["id"] for item in second_page.json()["items"]] != [
        item["id"] for item in body["items"]
    ]
