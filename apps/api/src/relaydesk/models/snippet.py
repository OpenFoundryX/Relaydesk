import uuid

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class Snippet(UUIDMixin, TimestampMixin, Base):
    """A canned reply an agent drops into a conversation.

    Workspace-wide rather than per-user: the point of a snippet is that
    everyone answers a recurring question the same way, so there is no
    owning agent and no sharing step.
    """

    __tablename__ = "snippets"
    __table_args__ = (UniqueConstraint("workspace_id", "title"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # CITEXT, like labels.name, because the title is what an agent types
    # after `/` in the composer. Two snippets whose titles differ only in
    # case are indistinguishable in that menu, so the collision is refused
    # by the database rather than left to the service to notice.
    title: Mapped[str] = mapped_column(CITEXT(), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
