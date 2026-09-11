"""ai calls

One row per inference attempt, whatever became of it -- answered, escalated,
refused, or degraded because one of spec D4's conditions applied.

This is the audit behind the deflection number. Slice 8 argued that such a
figure is only worth something if the workspace can check it; this table and
``widget_sessions`` are that check.

No message content is stored: not the question, not the answer, not the
articles retrieved. Shape and cost only.

``cost_micros`` is a BigInteger count of millionths, never a float, because
it will be summed across a billing period. ``widget_key_id`` is SET NULL so
that revoking an embed -- which is done by deleting it -- does not erase the
record of what it spent.

Revision ID: 0026
Revises: 0025
Create Date: 2026-09-11 10:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | Sequence[str] | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_calls",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("widget_key_id", sa.UUID(), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_micros", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "outcome",
            sa.String(length=16),
            sa.CheckConstraint(
                "outcome IN ('answered', 'escalated', 'refused', 'degraded')",
                name="ck_ai_calls_outcome",
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["widget_key_id"], ["widget_keys.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_calls_workspace_id", "ai_calls", ["workspace_id"])
    # The budget window (spec D5) counts today's tokens for one workspace.
    op.create_index(
        "ix_ai_calls_workspace_created", "ai_calls", ["workspace_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_ai_calls_workspace_created", table_name="ai_calls")
    op.drop_index("ix_ai_calls_workspace_id", table_name="ai_calls")
    op.drop_table("ai_calls")
