"""session workspace

Records the workspace a session was minted for, so it can be validated
against that workspace on every request instead of being re-derived from
the user's *current* memberships (see ``services.auth.active_membership``).
Without this, a session outlives the membership it was minted for, and a
user holding two active memberships makes the resolved workspace arbitrary.

A ``NOT NULL`` column cannot be added directly to a populated table and
there is no sensible default, so this adds it nullable, backfills from each
session's user's active membership, deletes sessions whose user has no
active membership (they could never authenticate through them anyway), and
only then tightens the column to ``NOT NULL``.

The backfill picks the same membership ``services.auth.default_membership``
would: if a session's user already holds two active memberships (invites
were 503'd in production, so this is a defensive guard rather than an
expected case), a plain ``UPDATE ... FROM`` with no ordering would let
Postgres pick one arbitrarily — reproducing, once, at migration time, the
exact ambiguity this task removes. The ``DISTINCT ON`` subquery orders by
``(created_at, id)`` to make that deterministic instead.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-04 17:37:36.846161
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # Backfill from each session user's active membership. DISTINCT ON
    # picks one membership per user deterministically (oldest first, same
    # ordering as services.auth.default_membership) instead of leaving
    # Postgres to pick arbitrarily among ties.
    op.execute(
        """
        UPDATE sessions SET workspace_id = m.workspace_id
        FROM (
            SELECT DISTINCT ON (user_id) user_id, workspace_id
            FROM memberships
            WHERE status = 'active'
            ORDER BY user_id, created_at, id
        ) m
        WHERE m.user_id = sessions.user_id
        """
    )
    # A session whose user has no active membership could never authenticate
    # anyway; deleting is correct and keeps the column NOT NULL.
    op.execute("DELETE FROM sessions WHERE workspace_id IS NULL")
    op.alter_column("sessions", "workspace_id", nullable=False)
    op.create_foreign_key(
        "fk_sessions_workspace_id",
        "sessions",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_sessions_workspace_id", "sessions", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_sessions_workspace_id", table_name="sessions")
    op.drop_constraint("fk_sessions_workspace_id", "sessions", type_="foreignkey")
    op.drop_column("sessions", "workspace_id")
