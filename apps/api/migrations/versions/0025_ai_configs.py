"""ai configs

How one workspace reaches a model, and what it will spend doing it.

``api_key`` is stored recoverable because the value must be replayed to the
provider on every call -- a digest cannot serve it. It is never returned by
any endpoint, which is the difference between this and ``webhooks.secret``:
a webhook signature needs the key at both ends, a model key needs only this
server. See the model docstring for what that costs.

Keyed on ``workspace_id`` rather than carrying its own id: a workspace has
one configuration or none, and spend is a property of the workspace, not of
an individual embed.

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-11 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | Sequence[str] | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_configs",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column(
            "provider", sa.String(length=32), nullable=False, server_default="anthropic"
        ),
        sa.Column(
            "model", sa.String(length=64), nullable=False, server_default="claude-opus-5"
        ),
        sa.Column("api_key", sa.Text(), nullable=True),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column(
            "daily_token_budget", sa.Integer(), nullable=False, server_default="200000"
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
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
        sa.PrimaryKeyConstraint("workspace_id"),
    )


def downgrade() -> None:
    op.drop_table("ai_configs")
