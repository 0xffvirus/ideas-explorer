"""SQLAlchemy models for the research-tools module."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ResearchCache(Base):
    __tablename__ = "research_cache"
    __table_args__ = (Index("ix_research_cache_expires_at", "expires_at"),)

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    payload: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
