"""research cache

Revision ID: 4e8a1c7d92b3
Revises:
Create Date: 2026-10-14

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "4e8a1c7d92b3"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_cache",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_research_cache_expires_at", "research_cache", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_research_cache_expires_at", table_name="research_cache")
    op.drop_table("research_cache")
