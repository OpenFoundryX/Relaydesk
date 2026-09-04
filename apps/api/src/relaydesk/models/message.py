import enum
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class MessageRole(enum.StrEnum):
    customer = "customer"
    agent = "agent"
    ai = "ai"
    # Bounce notices and delivery failures belong to a thread but were
    # authored by neither a customer nor an agent.
    system = "system"


class MessageDirection(enum.StrEnum):
    inbound = "inbound"
    outbound = "outbound"


class DeliveryState(enum.StrEnum):
    none = "none"
    queued = "queued"
    sent = "sent"
    failed = "failed"


class Message(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_thread", "conversation_id", "sent_at"),
        # Partial on purpose. Postgres treats NULLs as distinct in a unique
        # index, so a plain index here would permit unlimited duplicate
        # (NULL, NULL) rows — which is every outbound and seeded message —
        # while appearing to enforce the constraint.
        Index(
            "uq_messages_channel_external",
            "channel_account_id",
            "external_id",
            unique=True,
            postgresql_where=sa.text(
                "channel_account_id IS NOT NULL AND external_id IS NOT NULL"
            ),
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(
            MessageRole,
            name="ck_messages_role",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        nullable=False,
    )
    author_name: Mapped[str] = mapped_column(String(160), nullable=False)
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    to_address: Mapped[str] = mapped_column(String(320), default="", nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    direction: Mapped[MessageDirection] = mapped_column(
        Enum(
            MessageDirection,
            name="ck_messages_direction",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        default=MessageDirection.outbound,
        nullable=False,
    )
    external_id: Mapped[str | None] = mapped_column(String(998), nullable=True)
    in_reply_to: Mapped[str | None] = mapped_column(String(998), nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_message_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("raw_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    channel_account_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("channel_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    delivery_state: Mapped[DeliveryState] = mapped_column(
        Enum(
            DeliveryState,
            name="ck_messages_delivery_state",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        default=DeliveryState.none,
        server_default="none",
        nullable=False,
    )
    delivery_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    attachments = relationship(
        "Attachment", lazy="selectin", cascade="all, delete-orphan"
    )
