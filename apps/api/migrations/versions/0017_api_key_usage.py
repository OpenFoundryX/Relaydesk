"""api key usage windows

Adds ``api_key_usage``, the counter behind the per-key rate limit.

Deliberately not ``rate_limit_hits``. That table stores one row per call and
takes a ``pg_advisory_xact_lock`` per call, which is correct for five
anonymous portal submissions an hour and wrong for an authenticated API: at
a couple of requests a second every same-key caller would serialise behind
one lock, and a bulk import would write a row per request.

This is a fixed-window counter instead: the primary key is the
``(api_key_id, window_start)`` pair, which is what the upsert conflicts on,
so a call is one ``INSERT ... ON CONFLICT DO UPDATE ... RETURNING`` with no
lock and no extra row. The trade is the usual fixed-window one -- up to
twice the limit across a window boundary -- which is accepted because this
bound exists to stop a runaway integration, not to defeat an adversary.

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-08 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_key_usage",
        sa.Column("api_key_id", sa.UUID(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("api_key_id", "window_start"),
    )
    op.create_index(
        "ix_api_key_usage_window_start",
        "api_key_usage",
        ["window_start"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_api_key_usage_window_start", table_name="api_key_usage")
    op.drop_table("api_key_usage")
