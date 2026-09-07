"""conversation external_id and metadata

The two fields the console's published code sample
(``apps/web/components/settings/code-sample.tsx``) promises on
``POST /v1/conversations``.

``external_id`` is the caller's own identifier, unique per workspace, and it
is what makes the create endpoint idempotent: a repeated POST returns the
conversation it already created instead of a duplicate. The index is
*partial* because Postgres treats NULLs as distinct -- a plain unique index
would permit unlimited duplicate ``(workspace_id, NULL)`` rows, which is
every conversation that did not arrive through the API, while appearing to
enforce the constraint. The same trap is documented on
``uq_messages_channel_external``.

``metadata`` is JSONB and unindexed: retrievable per conversation, not
queryable across them. Filtering on it would want a GIN index and a query
language, and that decision is deliberately not made here.

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-08 10:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations", sa.Column("external_id", sa.String(length=200), nullable=True)
    )
    op.add_column(
        "conversations",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )
    op.create_index(
        "uq_conversations_external_id",
        "conversations",
        ["workspace_id", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_conversations_external_id", table_name="conversations")
    op.drop_column("conversations", "metadata")
    op.drop_column("conversations", "external_id")
