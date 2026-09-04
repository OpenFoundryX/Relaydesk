"""invite single use

``accept_invite`` now deletes the invite row on success instead of setting
``accepted_at`` (single-use by deletion rather than by flag), and
``read_invite`` no longer checks that column. Without this migration, any
invite accepted *before* this deploy — its row still present, with
``accepted_at`` set — would pass the new code's checks unchanged: the row
exists, isn't expired, and nothing looks at ``accepted_at`` anymore. Its
token would become valid again, live and immediately usable, for as long as
it remained inside the original ``INVITE_TTL`` window.

So this deletes every already-accepted invite first — the same operation
``accept_invite`` itself now performs at acceptance time, just applied once
here for rows that predate the change — before dropping the column, which
would otherwise leave those rows silently unresolvable as "already used"
forever.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-05 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Re-arm nothing: a previously accepted invite's token must not become
    # valid again just because the column that used to reject it is gone.
    op.execute("DELETE FROM invites WHERE accepted_at IS NOT NULL")
    op.drop_column("invites", "accepted_at")


def downgrade() -> None:
    op.add_column(
        "invites",
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
