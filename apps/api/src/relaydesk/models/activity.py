import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class ActivityKind(enum.StrEnum):
    created = "created"
    status = "status"
    priority = "priority"
    assignee = "assignee"
    label = "label"
    reply = "reply"


class ActivityEvent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "activity_events"
    __table_args__ = (
        # Analytics: resolved counts, resolution times, and backlog replay.
        Index("ix_activity_events_workspace_kind_at", "workspace_id", "kind", "at"),
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
        index=True,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_api_key_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_name: Mapped[str] = mapped_column(String(160), nullable=False)
    kind: Mapped[ActivityKind] = mapped_column(
        Enum(
            ActivityKind,
            name="ck_activity_events_kind",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        nullable=False,
    )
    verb: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
