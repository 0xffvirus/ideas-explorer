"""FastAPI application factory for Idea Forge."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import get_database
from app.ideas.api import get_analysis_enqueuer
from app.ideas.api import router as ideas_router
from app.obs import configure_logging
from app.pipeline import SqlAnalysisEnqueuer
from app.pipeline.api import router as pipeline_router
from app.reports import router as reports_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    configure_logging(get_settings().log_level)
    yield
    await get_database().dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Idea Forge",
        version="0.1.0",
        summary="Multi-agent business idea validation",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(ideas_router)
    app.include_router(pipeline_router)
    app.include_router(reports_router)

    database = get_database()
    enqueuer = SqlAnalysisEnqueuer(database.session_factory)
    app.dependency_overrides[get_analysis_enqueuer] = lambda: enqueuer

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
