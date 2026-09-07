"""api keys

Adds ``api_keys``, the first non-human principal in the product. Every
credential before this one belonged to a person: a session belongs to a
user, an invite and a password reset are addressed to a mailbox. A key
belongs to the *workspace*, which is why ``created_by_user_id`` is nullable
and ``SET NULL`` -- an integration must not stop working, or keep working
under a departed employee's name, because of an HR action.

``token_hash`` is unique and is all that persists; the plaintext exists only
in the response that created the key. ``prefix`` is display-only. A revoked
key keeps its row (``revoked_at``) rather than being deleted, so the
attribution columns added in 0016 keep resolving to a name.

``scopes`` is a plain text array rather than an array of a database enum:
the ``native_enum=False`` CHECK-constraint pattern used by every scalar enum
column in this schema has no array form, so the closed set is enforced at
the application edge instead.

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-08 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "scopes",
            postgresql.ARRAY(sa.String(length=32)),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_api_keys_workspace_id", "api_keys", ["workspace_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_api_keys_workspace_id", table_name="api_keys")
    op.drop_table("api_keys")
