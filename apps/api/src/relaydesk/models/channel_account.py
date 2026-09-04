import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class ChannelAccountKind(enum.StrEnum):
    email = "email"


class ChannelAccount(UUIDMixin, TimestampMixin, Base):
    """A workspace's ingest address.

    Holds no credentials by design: the deployment owns one mailbox,
    configured through the environment, and workspaces are distinguished by
    the address mail was forwarded to. A database compromise therefore grants
    no mailbox access.
    """

    __tablename__ = "channel_accounts"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[ChannelAccountKind] = mapped_column(
        Enum(
            ChannelAccountKind,
            name="ck_channel_accounts_kind",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        default=ChannelAccountKind.email,
        nullable=False,
    )
    ingest_token: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
