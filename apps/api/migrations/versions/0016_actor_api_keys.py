"""attribute activity and messages to an API key

``activity_events`` and ``messages`` each carry a nullable actor foreign key
beside a name snapshot, because inbound mail has always produced rows no
signed-in user caused. Slice 6 adds a second kind of principal, so each
table gains a second nullable key.

The name snapshot is enough to *display* history. The foreign key is what
answers "show me everything this key did", which is the question asked on
the day a key is suspected of having leaked -- and which cannot be
retrofitted onto rows written before the column existed. That is the whole
argument for paying for it now rather than when it is wanted.

``SET NULL`` rather than ``CASCADE``: revoking or deleting a key must never
erase the history of what it did.

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-08 09:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "activity_events", sa.Column("actor_api_key_id", sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        "fk_activity_events_actor_api_key_id",
        "activity_events",
        "api_keys",
        ["actor_api_key_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "messages", sa.Column("author_api_key_id", sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        "fk_messages_author_api_key_id",
        "messages",
        "api_keys",
        ["author_api_key_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_messages_author_api_key_id", "messages", type_="foreignkey"
    )
    op.drop_column("messages", "author_api_key_id")
    op.drop_constraint(
        "fk_activity_events_actor_api_key_id", "activity_events", type_="foreignkey"
    )
    op.drop_column("activity_events", "actor_api_key_id")
