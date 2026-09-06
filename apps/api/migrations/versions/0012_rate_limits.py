"""rate limits

Adds ``rate_limit_hits``, the counter behind the Postgres-backed rate
limiter. Deliberately not workspace-scoped: the caller here is anonymous,
and the whole point of the table is to bound them before any workspace is
trusted. Rows are counted inside a window by ``(bucket, key, created_at)``
and never read individually, hence the composite index rather than a
unique constraint.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-06 14:25:38.790519
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_hits",
        sa.Column("bucket", sa.String(length=32), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rate_limit_hits_lookup",
        "rate_limit_hits",
        ["bucket", "key", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_rate_limit_hits_lookup", table_name="rate_limit_hits")
    op.drop_table("rate_limit_hits")
