"""Job worker entrypoint: ``uv run python -m app.worker``."""

from __future__ import annotations

import asyncio
import os
import socket
from collections.abc import Callable, Mapping
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import ModelPrice, Settings, get_settings
from app.cost import CostMeter
from app.db import Database
from app.ideas import OpenAIEmbedder
from app.jev import Gate, JevClient
from app.obs import configure_logging, get_logger
from app.pipeline.worker import run_forever
from app.research import ResearchTool, build_default_tools

logger = get_logger(__name__)


@dataclass
class WorkerClients:
    """Shared HTTP clients and the per-run factories that borrow them."""

    gate: Gate
    jev_client: JevClient
    tools_factory: Callable[[CostMeter], Mapping[str, ResearchTool]]
    gate_factory: Callable[[CostMeter], Gate]
    http_client: httpx.AsyncClient
    jev_http_client: httpx.AsyncClient

    async def aclose(self) -> None:
        """Close the two shared HTTP clients; per-run clients only borrow them."""
        await self.http_client.aclose()
        await self.jev_http_client.aclose()


def build_worker_clients(
    settings: Settings,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> WorkerClients:
    """Build one shared research client and one shared Jev client for the worker.

    Both per-run factories reuse those clients, so a run never constructs a
    connection pool of its own; each run still gets its own meter, and the
    per-run Jev client carries the configured ``JEV_*_USD_PER_MILLION`` prices
    so Jev spend lands inside the run's cost cap.
    """
    http_client = httpx.AsyncClient(timeout=settings.research_timeout_seconds)
    jev_http_client = httpx.AsyncClient(timeout=settings.jev_timeout_seconds)
    jev_pricing = {
        settings.jev_model: ModelPrice(
            input=settings.jev_input_usd_per_million,
            output=settings.jev_output_usd_per_million,
        )
    }

    def jev_client(*, meter: CostMeter | None) -> JevClient:
        return JevClient(
            api_key=settings.typesafe_api_key,
            base_url=settings.jev_base_url,
            model=settings.jev_model,
            timeout_seconds=settings.jev_timeout_seconds,
            max_questions_per_call=settings.jev_max_questions_per_call,
            http_client=jev_http_client,
            meter=meter,
            pricing=jev_pricing if meter is not None else None,
        )

    def gate_factory(meter: CostMeter) -> Gate:
        return Gate(
            jev_client(meter=meter),
            confidence_floor=settings.jev_confidence_floor,
            claim_threshold=settings.jev_claim_threshold,
        )

    def tools_factory(meter: CostMeter) -> Mapping[str, ResearchTool]:
        return build_default_tools(
            settings,
            session_factory=session_factory,
            meter=meter,
            http_client=http_client,
        )

    shared_jev = jev_client(meter=None)
    return WorkerClients(
        gate=Gate(
            shared_jev,
            confidence_floor=settings.jev_confidence_floor,
            claim_threshold=settings.jev_claim_threshold,
        ),
        jev_client=shared_jev,
        tools_factory=tools_factory,
        gate_factory=gate_factory,
        http_client=http_client,
        jev_http_client=jev_http_client,
    )


async def main() -> None:
    """Wire settings, clients, and the worker loop, then run until interrupted."""
    settings = get_settings()
    configure_logging(settings.log_level)
    database = Database(settings.database_url)
    embedder = OpenAIEmbedder(
        api_key=settings.openai_api_key,
        model=settings.openai_embedding_model,
        dimensions=settings.embedding_dimensions,
    )
    clients = build_worker_clients(settings, session_factory=database.session_factory)
    worker_id = f"{socket.gethostname()}-{os.getpid()}"
    try:
        await run_forever(
            worker_id,
            settings=settings,
            gate=clients.gate,
            tools=clients.tools_factory,
            gate_factory=clients.gate_factory,
            embedder=embedder,
            session_factory=database.session_factory,
            jev=clients.jev_client,
        )
    finally:
        await clients.aclose()
        await database.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("worker interrupted; shutting down")
