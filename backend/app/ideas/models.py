"""SQLAlchemy models for the idea-core module.

Only ``app.ideas`` (service, API) touches these tables.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
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
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.db import Base


class IdeaStatus(enum.StrEnum):
    draft = "draft"
    queued = "queued"
    analyzing = "analyzing"
    done = "done"
    failed = "failed"


class IdeaVerdict(enum.StrEnum):
    pursue = "pursue"
    refine = "refine"
    park = "park"


def _values(enum_cls: type[enum.StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


class Idea(Base):
    __tablename__ = "ideas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[IdeaStatus] = mapped_column(
        SAEnum(IdeaStatus, name="idea_status", values_callable=_values),
        nullable=False,
        default=IdeaStatus.draft,
        server_default=IdeaStatus.draft.value,
    )
    verdict: Mapped[IdeaVerdict | None] = mapped_column(
        SAEnum(IdeaVerdict, name="idea_verdict", values_callable=_values),
        nullable=True,
    )
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    pinned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    versions: Mapped[list[IdeaVersion]] = relationship(
        back_populates="idea",
        cascade="all, delete-orphan",
        order_by="IdeaVersion.number",
        lazy="selectin",
    )
    tags: Mapped[list[Tag]] = relationship(
        secondary="idea_tags", back_populates="ideas", lazy="selectin"
    )


class IdeaVersion(Base):
    __tablename__ = "idea_versions"
    __table_args__ = (UniqueConstraint("idea_id", "number", name="uq_idea_versions_idea_number"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idea_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ideas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    brief: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    idea: Mapped[Idea] = relationship(back_populates="versions")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    ideas: Mapped[list[Idea]] = relationship(
        secondary="idea_tags", back_populates="tags", lazy="raise"
    )


class IdeaTag(Base):
    __tablename__ = "idea_tags"

    idea_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ideas.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )


class IdeaSearch(Base):
    """One row per idea: latest version text plus its embedding."""

    __tablename__ = "idea_search"
    __table_args__ = (
        Index("ix_idea_search_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_idea_search_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 64},
        ),
    )

    idea_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ideas.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tsv: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(get_settings().embedding_dimensions), nullable=True
    )
