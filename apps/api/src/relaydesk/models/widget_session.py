import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin


class WidgetSession(Base, TimestampMixin):
    """One panel open, and how far it got. The deflection baseline.

    Three booleans rather than an event stream: a visitor who searches four
    times is one row, the ratio is one query, and there is nothing to prune.

    The ratio this exists to answer is, of the sessions that tried to
    self-serve -- ``searched or read_article`` -- the share that did not go
    on to ``submitted``. Sessions that did neither are not deflection in
    either direction and belong in neither half of the fraction.

    ``ActivityEvent`` was the obvious home and cannot serve: its
    ``conversation_id`` is NOT NULL, and the sessions worth counting are
    exactly the ones that never produced a conversation.

    ``id`` is minted by the frame and is opaque. There is deliberately no
    address, no email, no query text and no article here -- three booleans
    and an id attributable to nobody. This table records the behaviour of
    other companies' customers, and that is the whole of what it may know.
    """

    __tablename__ = "widget_sessions"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    widget_key_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("widget_keys.id", ondelete="CASCADE"),
        nullable=False,
    )
    searched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_article: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    submitted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
