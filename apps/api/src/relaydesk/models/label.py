import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class LabelColor(enum.StrEnum):
    citron = "citron"
    slate = "slate"
    amber = "amber"
    rose = "rose"
    sky = "sky"


class Label(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "labels"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    color: Mapped[LabelColor] = mapped_column(
        Enum(LabelColor, native_enum=False, length=16),
        default=LabelColor.slate,
        nullable=False,
    )
