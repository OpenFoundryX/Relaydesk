"""drop placeholder billing columns

``plan``, ``trial_days_left``, ``tickets_this_period`` and
``projected_tickets`` were static columns invented to give the console
something to render before billing existed. Nothing wrote to them after
the seed, so every workspace showed the same fictional trial. Billing is
deferred rather than half-built, so the columns go with the UI that read
them; the subscription slice that eventually lands will model its own
state rather than inherit these.

``downgrade`` restores the columns with their old defaults, so the
pre-0013 code still runs against a downgraded database. The values it
restores are defaults, not the fictions that were there before -- there
is nothing to recover, because there was never any real data here.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-07 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("workspaces", "projected_tickets")
    op.drop_column("workspaces", "tickets_this_period")
    op.drop_column("workspaces", "trial_days_left")
    op.drop_column("workspaces", "plan")


def downgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column(
            "plan",
            sa.String(length=32),
            nullable=False,
            server_default="Starter",
        ),
    )
    for column in ("trial_days_left", "tickets_this_period", "projected_tickets"):
        op.add_column(
            "workspaces",
            sa.Column(column, sa.Integer(), nullable=False, server_default="0"),
        )
