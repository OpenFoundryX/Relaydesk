import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class Contact(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("workspace_id", "email"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(CITEXT(), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    bounced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
