"""analytics indexes

Two composite indexes covering the access pattern the analytics queries
introduce. Both lead with ``workspace_id`` because every one of those
queries is tenant-scoped before it is anything else, then narrow on the
discriminator the query already knows, then range-scan the time column.

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-08 15:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0020"
down_revision: str | Sequence[str] | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Resolved counts, resolution times and the whole backlog replay read
    # activity events this way and no other.
    op.create_index(
        "ix_activity_events_workspace_kind_at",
        "activity_events",
        ["workspace_id", "kind", "at"],
    )
    # First-reply lookups: outbound only, ordered by when it was sent.
    op.create_index(
        "ix_messages_workspace_direction_sent_at",
        "messages",
        ["workspace_id", "direction", "sent_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_messages_workspace_direction_sent_at", table_name="messages"
    )
    op.drop_index(
        "ix_activity_events_workspace_kind_at", table_name="activity_events"
    )
