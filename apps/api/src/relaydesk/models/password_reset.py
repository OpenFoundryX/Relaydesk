import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class PasswordReset(UUIDMixin, TimestampMixin, Base):
    """A single-use capability to set one user's password.

    Shaped like ``invites`` because it is the same kind of object: a
    short-lived secret that is mailed, hashed at rest, and consumed once.

    No ``email`` column. The row points at a user and the address is read
    from that user when the mail is composed; storing a second copy would
    let the two disagree after an address change.

    ``ON DELETE CASCADE`` so deleting a user cannot leave a live capability
    pointing at an account that no longer exists.
    """

    __tablename__ = "password_resets"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
