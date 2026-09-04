"""email channel

Adds the tables and columns the email channel slice reads and writes: an
inbound-mail landing zone (``raw_messages``), workspace ingest addresses
(``channel_accounts``), message attachments, poller bookkeeping
(``poll_state``), and delivery/direction state on ``messages``.

Three things autogenerate does not produce, hand-written below:

- ``ck_messages_role`` is a named CHECK constraint from migration 0006.
  SQLAlchemy does not autogenerate CHECK-constraint changes, so widening
  ``MessageRole`` with ``system`` needs the constraint dropped and recreated
  explicitly.
- ``messages.direction`` is backfilled from ``role`` rather than defaulted,
  so existing seeded customer messages read as inbound instead of every row
  becoming outbound.
- ``uq_messages_channel_external`` is a partial unique index
  (``postgresql_where``): Postgres treats NULLs as distinct in a unique
  index, so without the predicate the index would silently permit unlimited
  duplicate ``(NULL, NULL)`` rows.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-04 12:00:40.643589
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "poll_state",
        sa.Column("mailbox", sa.String(length=255), nullable=False),
        sa.Column("uidvalidity", sa.BigInteger(), nullable=False),
        sa.Column("last_uid", sa.BigInteger(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mailbox"),
    )
    op.create_table(
        "channel_accounts",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "email",
                name="ck_channel_accounts_kind",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("ingest_token", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
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
        sa.UniqueConstraint("ingest_token"),
    )
    op.create_index(
        op.f("ix_channel_accounts_workspace_id"),
        "channel_accounts",
        ["workspace_id"],
        unique=False,
    )
    op.create_table(
        "raw_messages",
        sa.Column("mailbox", sa.String(length=255), nullable=False),
        sa.Column("uidvalidity", sa.BigInteger(), nullable=False),
        sa.Column("uid", sa.BigInteger(), nullable=False),
        sa.Column("raw", sa.LargeBinary(), nullable=False),
        sa.Column(
            "state",
            sa.Enum(
                "fetched",
                "ingested",
                "unrouted",
                "throttled",
                "failed",
                name="ck_raw_messages_state",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=True),
        sa.Column("channel_account_id", sa.UUID(), nullable=True),
        sa.Column("external_id", sa.String(length=998), nullable=True),
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
            ["channel_account_id"], ["channel_accounts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mailbox", "uidvalidity", "uid"),
    )
    op.create_index(
        op.f("ix_raw_messages_state"), "raw_messages", ["state"], unique=False
    )
    op.create_table(
        "attachments",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("inline", sa.Boolean(), nullable=False),
        sa.Column("content_id", sa.String(length=255), nullable=True),
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
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_attachments_message", "attachments", ["message_id"], unique=False
    )
    op.create_index(
        op.f("ix_attachments_workspace_id"),
        "attachments",
        ["workspace_id"],
        unique=False,
    )
    op.add_column(
        "contacts", sa.Column("bounced_at", sa.DateTime(timezone=True), nullable=True)
    )

    # (a) ck_messages_role is a named CHECK constraint (migration 0006) and is
    # not autogenerated. Widening MessageRole with `system` needs it dropped
    # and recreated, or the old constraint rejects every bounce notice.
    op.drop_constraint("ck_messages_role", "messages", type_="check")
    op.create_check_constraint(
        "ck_messages_role",
        "messages",
        sa.text("role IN ('customer', 'agent', 'ai', 'system')"),
    )

    # (b) direction is backfilled from role, not defaulted: a blanket default
    # would mark every existing seeded customer message as outbound.
    op.add_column("messages", sa.Column("direction", sa.String(16), nullable=True))
    op.execute(
        "UPDATE messages SET direction = "
        "CASE WHEN role = 'customer' THEN 'inbound' ELSE 'outbound' END"
    )
    op.alter_column("messages", "direction", nullable=False)
    op.create_check_constraint(
        "ck_messages_direction",
        "messages",
        sa.text("direction IN ('inbound', 'outbound')"),
    )

    op.add_column(
        "messages", sa.Column("external_id", sa.String(length=998), nullable=True)
    )
    op.add_column(
        "messages", sa.Column("in_reply_to", sa.String(length=998), nullable=True)
    )
    op.add_column("messages", sa.Column("body_html", sa.Text(), nullable=True))
    op.add_column("messages", sa.Column("raw_message_id", sa.UUID(), nullable=True))
    op.add_column("messages", sa.Column("channel_account_id", sa.UUID(), nullable=True))
    op.add_column(
        "messages",
        sa.Column(
            "delivery_state",
            sa.Enum(
                "none",
                "queued",
                "sent",
                "failed",
                name="ck_messages_delivery_state",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            server_default="none",
            nullable=False,
        ),
    )
    op.add_column("messages", sa.Column("delivery_error", sa.Text(), nullable=True))

    # (c) Partial on purpose: Postgres treats NULLs as distinct in a unique
    # index, so without postgresql_where this would silently permit
    # unlimited duplicate (NULL, NULL) rows.
    op.create_index(
        "uq_messages_channel_external",
        "messages",
        ["channel_account_id", "external_id"],
        unique=True,
        postgresql_where=sa.text(
            "channel_account_id IS NOT NULL AND external_id IS NOT NULL"
        ),
    )
    op.create_foreign_key(
        "fk_messages_channel_account_id_channel_accounts",
        "messages",
        "channel_accounts",
        ["channel_account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_messages_raw_message_id_raw_messages",
        "messages",
        "raw_messages",
        ["raw_message_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "users",
        sa.Column(
            "notify_on_assignment",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "notify_on_assignment")
    op.drop_constraint(
        "fk_messages_raw_message_id_raw_messages", "messages", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_messages_channel_account_id_channel_accounts",
        "messages",
        type_="foreignkey",
    )
    op.drop_index(
        "uq_messages_channel_external",
        table_name="messages",
        postgresql_where=sa.text(
            "channel_account_id IS NOT NULL AND external_id IS NOT NULL"
        ),
    )
    op.drop_column("messages", "delivery_error")
    op.drop_column("messages", "delivery_state")
    op.drop_column("messages", "channel_account_id")
    op.drop_column("messages", "raw_message_id")
    op.drop_column("messages", "body_html")
    op.drop_column("messages", "in_reply_to")
    op.drop_column("messages", "external_id")

    op.drop_constraint("ck_messages_direction", "messages", type_="check")
    op.drop_column("messages", "direction")

    op.drop_constraint("ck_messages_role", "messages", type_="check")
    op.create_check_constraint(
        "ck_messages_role",
        "messages",
        sa.text("role IN ('customer', 'agent', 'ai')"),
    )

    op.drop_column("contacts", "bounced_at")
    op.drop_index(op.f("ix_attachments_workspace_id"), table_name="attachments")
    op.drop_index("ix_attachments_message", table_name="attachments")
    op.drop_table("attachments")
    op.drop_index(op.f("ix_raw_messages_state"), table_name="raw_messages")
    op.drop_table("raw_messages")
    op.drop_index(
        op.f("ix_channel_accounts_workspace_id"), table_name="channel_accounts"
    )
    op.drop_table("channel_accounts")
    op.drop_table("poll_state")
