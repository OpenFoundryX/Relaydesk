"""snippets

Adds ``snippets``, the canned replies behind Settings -> Templates. A row is
a title and a body; the body may contain ``{{customer.first_name}}``-style
placeholders, which are substituted in the console at the moment the agent
inserts one. Nothing here parses them -- an unrecognised placeholder is
stored and rendered verbatim, which is why no placeholder vocabulary is
pinned in the schema.

``title`` is CITEXT and unique per workspace: it is what an agent types
after ``/`` in the composer, so two titles differing only in case would be
indistinguishable at the point of use.

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-08 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "snippets",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("title", postgresql.CITEXT(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "title"),
    )
    op.create_index(
        "ix_snippets_workspace_id", "snippets", ["workspace_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_snippets_workspace_id", table_name="snippets")
    op.drop_table("snippets")
