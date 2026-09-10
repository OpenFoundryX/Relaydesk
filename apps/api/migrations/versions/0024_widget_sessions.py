"""widget sessions

One row per panel open, carrying how far that visit got: searched, read an
article, submitted. This is the deflection baseline, and it is in the same
slice as the widget because deflection cannot be measured retroactively --
a workspace only has a before-and-after if the before was recorded.

Three booleans rather than an event stream, so a visitor who searches four
times is one row. No address, no email, no query text: the id is opaque and
attributable to nobody.

Revision ID: 0024
Revises: 0023
Create Date: 2026-09-10 13:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | Sequence[str] | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "widget_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("widget_key_id", sa.UUID(), nullable=False),
        sa.Column("searched", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "read_article", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("submitted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["widget_key_id"], ["widget_keys.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_widget_sessions_workspace_id",
        "widget_sessions",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_widget_sessions_workspace_id", table_name="widget_sessions")
    op.drop_table("widget_sessions")
