import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class RawMessageState(enum.StrEnum):
    fetched = "fetched"
    ingested = "ingested"
    unrouted = "unrouted"
    throttled = "throttled"
    failed = "failed"


class RawMessage(UUIDMixin, TimestampMixin, Base):
    """Immutable landing zone for one fetched message.

    Parsing happens in a separate task so a message we cannot parse fails
    alone rather than wedging the poll, and so the bytes survive for replay
    once the parser is fixed.
    """

    __tablename__ = "raw_messages"
    __table_args__ = (UniqueConstraint("mailbox", "uidvalidity", "uid"),)

    mailbox: Mapped[str] = mapped_column(String(255), nullable=False)
    uidvalidity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    raw: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    state: Mapped[RawMessageState] = mapped_column(
        Enum(
            RawMessageState,
            name="ck_raw_messages_state",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        default=RawMessageState.fetched,
        nullable=False,
        index=True,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # All three are unknown until routing succeeds.
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
    )
    channel_account_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("channel_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    external_id: Mapped[str | None] = mapped_column(String(998), nullable=True)
