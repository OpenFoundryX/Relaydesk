"""widget keys

Adds ``widget_keys``, the credential behind the embeddable support widget.

``key`` is stored in plaintext, which no other credential in this schema
does. It is printed in the page source of every site that embeds the widget,
so it is not secret at any point in its life, and an admin must be able to
read it back to re-paste the snippet. See the model docstring, which records
what that costs and why a scope on ``api_keys`` was rejected instead.

``allowed_origins`` is JSONB holding exact origins; an empty list refuses
embedding rather than permitting it. ``settings`` is JSONB because none of it
is queried and all of it is presentational.

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-10 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: str | Sequence[str] | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "widget_keys",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column(
            "allowed_origins",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index(
        "ix_widget_keys_workspace_id", "widget_keys", ["workspace_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_widget_keys_workspace_id", table_name="widget_keys")
    op.drop_table("widget_keys")
