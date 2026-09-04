"""backfill channel accounts

Every workspace now gets a default email ``ChannelAccount`` at creation
time (see ``services.workspaces.create_workspace``), but
workspaces created before this deploy have none. Without one, a workspace
has no ingest address at all, so this backfills a "Support" account with a
fresh random token for every workspace that is missing one.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-05 00:00:00.000000
"""

import secrets
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id FROM workspaces")).fetchall()
    for (workspace_id,) in rows:
        exists = connection.execute(
            sa.text("SELECT 1 FROM channel_accounts WHERE workspace_id = :id"),
            {"id": workspace_id},
        ).first()
        if exists:
            continue
        connection.execute(
            sa.text(
                "INSERT INTO channel_accounts "
                "(id, workspace_id, kind, ingest_token, display_name, active, "
                " created_at, updated_at) "
                "VALUES (:id, :ws, 'email', :token, 'Support', true, now(), now())"
            ),
            {
                "id": str(uuid.uuid4()),
                "ws": workspace_id,
                "token": secrets.token_hex(6),
            },
        )


def downgrade() -> None:
    # Nothing else creates channel_accounts rows before this migration, so a
    # plain delete is correct here.
    op.execute("DELETE FROM channel_accounts")
