import enum
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class Channel(enum.StrEnum):
    email = "email"
    discord = "discord"
    portal = "portal"
    api = "api"


class ConversationStatus(enum.StrEnum):
    open = "open"
    pending = "pending"
    resolved = "resolved"
    on_hold = "on_hold"
    ignored = "ignored"
    trash = "trash"


class Priority(enum.StrEnum):
    urgent = "urgent"
    high = "high"
    medium = "medium"
    low = "low"


class SummaryState(enum.StrEnum):
    none = "none"
    ready = "ready"
    failed = "failed"


class ConversationLabel(Base):
    __tablename__ = "conversation_labels"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    label_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("labels.id", ondelete="CASCADE"),
        primary_key=True,
    )


class Conversation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "number"),
        Index("ix_conversations_inbox", "workspace_id", "status", "last_message_at"),
        # Partial, for the same reason as ``uq_messages_channel_external``:
        # Postgres treats NULLs as distinct, so a plain unique index would
        # permit unlimited duplicate (workspace_id, NULL) rows -- which is
        # every conversation that did not arrive through the API -- while
        # appearing to enforce the constraint.
        Index(
            "uq_conversations_external_id",
            "workspace_id",
            "external_id",
            unique=True,
            postgresql_where=sa.text("external_id IS NOT NULL"),
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[str] = mapped_column(String(400), nullable=False)
    contact_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    channel: Mapped[Channel] = mapped_column(
        Enum(
            Channel,
            name="ck_conversations_channel",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        nullable=False,
    )
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(
            ConversationStatus,
            name="ck_conversations_status",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        default=ConversationStatus.open,
        nullable=False,
    )
    priority: Mapped[Priority] = mapped_column(
        Enum(
            Priority,
            name="ck_conversations_priority",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        default=Priority.medium,
        nullable=False,
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    preview: Mapped[str] = mapped_column(Text, default="", nullable=False)
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    unread: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_state: Mapped[SummaryState] = mapped_column(
        Enum(
            SummaryState,
            name="ck_conversations_summary_state",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        default=SummaryState.none,
        nullable=False,
    )
    # The caller's own identifier for this ticket. Unique per workspace, so
    # a repeated POST returns the conversation it already created rather
    # than a duplicate -- which is what makes an interrupted import safe to
    # re-run.
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # The column is ``metadata``; the attribute cannot be, because
    # Declarative owns that name on every model. Capped at the schema edge
    # (8 KB, 50 keys) so it stays a place for an order id and does not
    # become a blob store inside the hottest table in the product.
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}", default=dict
    )

    contact = relationship("Contact", lazy="selectin")
    assignee = relationship("User", lazy="selectin")
    labels = relationship("Label", secondary="conversation_labels", lazy="selectin")
    draft = relationship(
        "Draft", uselist=False, lazy="selectin", cascade="all, delete-orphan"
    )
