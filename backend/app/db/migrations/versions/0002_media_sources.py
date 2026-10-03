"""media sources: recording length and model usage for reading images

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-03 03:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("duration_seconds", sa.Float(), nullable=True))
    op.add_column(
        "sources", sa.Column("extraction_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("sources", "extraction_usage")
    op.drop_column("sources", "duration_seconds")
