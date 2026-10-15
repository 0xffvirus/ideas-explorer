"""SQLAlchemy models for the agent-pipeline module.

Tables: ``analysis_runs``, ``run_steps``, ``run_events``, and ``jobs``. Only
``app.pipeline`` touches them (the orchestrator, the job queue, and the API).

Two additions beyond SPEC-agent-pipeline.md are documented here:

* ``analysis_runs.idea_id`` duplicates the idea of ``idea_version_id`` so runs
  can be listed per idea without joining ``idea_versions``.
* ``analysis_runs.questions`` and ``analysis_runs.answers`` persist the
  clarifier pause/resume cycle (questions asked, and the user's answers).
"""

from __future__ import annotations

import enum
import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RunStatus(enum.StrEnum):
    """Lifecycle of one analysis run."""

    pending = "pending"
    running = "running"
    awaiting_input = "awaiting_input"
    done = "done"
    failed = "failed"
    partial = "partial"


TERMINAL_RUN_STATUSES: tuple[RunStatus, ...] = (
    RunStatus.done,
    RunStatus.failed,
    RunStatus.partial,
)


class StepStatus(enum.StrEnum):
    """Lifecycle of one step inside a run."""

    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"
    skipped = "skipped"


class JobStatus(enum.StrEnum):
    """Lifecycle of one worker job."""

    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


def _values(enum_cls: type[enum.StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


class AnalysisRun(Base):
    """One analysis of one idea version, resumable from its last completed step."""

    __tablename__ = "analysis_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idea_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ideas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    idea_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("idea_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[RunStatus] = mapped_column(
        SAEnum(RunStatus, name="run_status", values_callable=_values),
        nullable=False,
        default=RunStatus.pending,
        server_default=RunStatus.pending.value,
    )
    step: Mapped[str] = mapped_column(Text, nullable=False, default="refine")
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    cost_cap_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    questions: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    answers: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RunStep(Base):
    """One step's durable state: its output is written before the next step starts."""

    __tablename__ = "run_steps"
    __table_args__ = (UniqueConstraint("run_id", "step", name="uq_run_steps_run_step"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[StepStatus] = mapped_column(
        SAEnum(StepStatus, name="step_status", values_callable=_values),
        nullable=False,
        default=StepStatus.pending,
        server_default=StepStatus.pending.value,
    )
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RunEvent(Base):
    """Append-only progress log; ``(run_id, seq)`` backs Last-Event-ID resumption."""

    __tablename__ = "run_events"
    __table_args__ = (UniqueConstraint("run_id", "seq", name="uq_run_events_run_seq"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event: Mapped[str] = mapped_column(Text, nullable=False)
    step: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Job(Base):
    """Postgres-backed work item claimed with ``FOR UPDATE SKIP LOCKED``."""

    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_status_run_after", "status", "run_after"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, name="job_status", values_callable=_values),
        nullable=False,
        default=JobStatus.queued,
        server_default=JobStatus.queued.value,
    )
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    locked_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


def next_event_seq(current_max: int | None) -> int:
    """Return the next gap-free event sequence number for a run."""
    return (current_max or 0) + 1


def run_event_to_sse(event: RunEvent) -> dict[str, str]:
    """Serialize one :class:`RunEvent` into the SSE fields EventSourceResponse expects."""
    return {
        "id": str(event.seq),
        "event": event.event,
        "data": json.dumps(event.data),
    }
