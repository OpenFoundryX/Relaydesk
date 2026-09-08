"""webhooks

Adds ``webhooks``, the endpoints behind Settings -> Custom webhooks. A row is
an endpoint a workspace owns, described well enough for something inside
Relaydesk to decide to call it: a name, a description, a method, a URL, and
the parameters it accepts.

These are tools, not event subscriptions. Nothing in this table fires because
an inbox event happened; a caller chooses it and supplies arguments. Event
delivery, when it is built, needs its own table -- the two disagree about
whether repeating a call is safe, which is the only question that matters for
retries.

``name`` is unique per workspace because a tool is selected by name.
``params`` is JSONB: read and written as a unit, never queried across rows.
``secret`` is the HMAC key the receiver verifies with, and is therefore
stored in plaintext -- see the model docstring, which records what that costs.

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-09 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022"
down_revision: str | Sequence[str] | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "webhooks",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column(
            "method",
            sa.String(length=8),
            nullable=False,
        ),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("secret", sa.String(length=70), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "method IN ('GET', 'POST', 'PUT', 'PATCH', 'DELETE')",
            name="ck_webhooks_method",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        # SET NULL, not CASCADE: the webhook belongs to the workspace and
        # outlives whoever registered it.
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "name", name="uq_webhooks_workspace_name"),
    )
    op.create_index(
        "ix_webhooks_workspace_id", "webhooks", ["workspace_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_webhooks_workspace_id", table_name="webhooks")
    op.drop_table("webhooks")
