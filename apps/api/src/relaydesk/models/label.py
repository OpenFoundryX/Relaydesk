import enum
import uuid

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import CITEXT
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
    # CITEXT, like contacts.email, so "Billing" and "billing" collide at the
    # database's unique constraint instead of relying on the service layer
    # to catch a case-insensitive duplicate before it's inserted.
    name: Mapped[str] = mapped_column(CITEXT(), nullable=False)
    color: Mapped[LabelColor] = mapped_column(
        Enum(
            LabelColor,
            name="ck_labels_color",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        default=LabelColor.slate,
        nullable=False,
    )
