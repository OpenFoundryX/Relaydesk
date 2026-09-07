import enum
import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class ApiKeyScope(enum.StrEnum):
    """What a key is allowed to do. A closed set; see spec D5.

    ``messages_write`` is deliberately not folded into
    ``conversations_write``: changing a status is internal bookkeeping,
    while sending a reply puts mail in a customer's inbox under the
    workspace's name. A triage integration should be able to hold the first
    without the second, and that is only expressible as a separate grant.
    """

    conversations_read = "conversations:read"
    conversations_write = "conversations:write"
    messages_write = "messages:write"
    contacts_read = "contacts:read"
    labels_read = "labels:read"
    labels_write = "labels:write"


class ApiKey(UUIDMixin, TimestampMixin, Base):
    """A machine principal belonging to a workspace, not to a user.

    Only ``token_hash`` persists; the plaintext exists once, in the response
    to the request that created it. ``prefix`` is display-only -- it is what
    the settings list shows so a human can tell two keys apart, and it is
    ``rd_`` plus the first four characters of the secret. Four characters of
    a 43-character token narrow nothing.

    ``created_by_user_id`` is ``SET NULL`` rather than ``CASCADE``: the key
    belongs to the workspace and must outlive the person who minted it (spec
    D1). Revocation sets ``revoked_at`` rather than deleting the row, so
    ``activity_events.actor_api_key_id`` keeps resolving to a name.
    """

    __tablename__ = "api_keys"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # A plain text array of ``ApiKeyScope`` values rather than an array of a
    # database enum. Every other enum column here is
    # ``Enum(..., native_enum=False, create_constraint=True)``, which is a
    # CHECK constraint over a scalar column and has no array equivalent that
    # Alembic autogenerates cleanly. Validation therefore lives at the
    # Pydantic edge and in ``services.api_keys.mint``, which is the only
    # writer.
    scopes: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, server_default="{}"
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
