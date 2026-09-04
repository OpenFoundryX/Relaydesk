"""enum check constraints

``sa.Enum(..., native_enum=False)`` compiles to a plain VARCHAR: since
SQLAlchemy 1.4 ``create_constraint`` defaults to ``False``, so migrations
0001-0005 created the columns with no CHECK behind them and any string of
the right length was storable. The models now pass
``create_constraint=True``; this backfills the constraints on databases
already at 0005.

Each is named explicitly — and identically to what the model emits, so
autogenerate sees no drift — so a later slice that adds an enum value can
drop and recreate one by name.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-04 08:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (constraint name, table, column, allowed values)
CHECKS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("ck_memberships_role", "memberships", "role", ("admin", "agent")),
    ("ck_memberships_status", "memberships", "status", ("active", "invited")),
    ("ck_invites_role", "invites", "role", ("admin", "agent")),
    (
        "ck_conversations_channel",
        "conversations",
        "channel",
        ("email", "discord", "portal", "api"),
    ),
    (
        "ck_conversations_status",
        "conversations",
        "status",
        ("open", "pending", "resolved", "on_hold", "ignored", "trash"),
    ),
    (
        "ck_conversations_priority",
        "conversations",
        "priority",
        ("urgent", "high", "medium", "low"),
    ),
    (
        "ck_conversations_summary_state",
        "conversations",
        "summary_state",
        ("none", "ready", "failed"),
    ),
    ("ck_messages_role", "messages", "role", ("customer", "agent", "ai")),
    (
        "ck_labels_color",
        "labels",
        "color",
        ("citron", "slate", "amber", "rose", "sky"),
    ),
    (
        "ck_activity_events_kind",
        "activity_events",
        "kind",
        ("created", "status", "priority", "assignee", "label", "reply"),
    ),
)


def upgrade() -> None:
    # Raw DDL rather than op.create_check_constraint: the names below are
    # the final constraint names, and must not be run through a naming
    # convention that would prefix them a second time.
    for name, table, column, values in CHECKS:
        allowed = ", ".join(f"'{value}'" for value in values)
        op.execute(
            f'ALTER TABLE "{table}" ADD CONSTRAINT "{name}" '
            f'CHECK ("{column}" IN ({allowed}))'
        )


def downgrade() -> None:
    for name, table, _column, _values in reversed(CHECKS):
        op.execute(f'ALTER TABLE "{table}" DROP CONSTRAINT "{name}"')
