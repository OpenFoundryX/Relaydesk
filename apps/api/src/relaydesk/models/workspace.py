from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class Workspace(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    monogram: Mapped[str] = mapped_column(String(4), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    conversation_seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Placeholder billing fields the console reads. Slice 7 replaces the source.
    plan: Mapped[str] = mapped_column(String(32), default="Starter", nullable=False)
    trial_days_left: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tickets_this_period: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    projected_tickets: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
