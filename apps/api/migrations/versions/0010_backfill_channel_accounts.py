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
    # Deliberately a no-op. This migration's upgrade cannot be told apart
    # from any channel_accounts row created afterward through the ordinary
    # product path (services.workspaces.create_workspace, or an admin
    # adding a second address) -- there is no marker column distinguishing
    # "backfilled by 0010" from "created since". A blanket DELETE here
    # (the original version of this downgrade) would destroy every
    # workspace's ingest token unconditionally, including ones minted long
    # after this deploy, which is irrecoverable: find_by_token then matches
    # nothing and every workspace's forwarded mail becomes `unrouted`.
    # Going 0010 -> 0009 leaves the backfilled rows in place; they are
    # harmless extra data under 0009's schema (which has no code path that
    # reads channel_accounts at all), and re-running 0010's upgrade after a
    # re-upgrade is already idempotent (it skips any workspace that already
    # has a row).
    pass
