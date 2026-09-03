import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class SavedView(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "saved_views"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
