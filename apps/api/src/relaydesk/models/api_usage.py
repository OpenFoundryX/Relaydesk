import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base


class ApiKeyUsage(Base):
    """One fixed window of one key's API calls.

    Deliberately *not* ``rate_limit_hits``. That table records one row per
    call and serialises same-key callers on a ``pg_advisory_xact_lock``,
    which is the right trade at five portal submissions an hour and the
    wrong one at a couple of requests a second: an import job would queue
    behind its own lock and write a row per call.

    This is a counter instead -- one row per key per minute, incremented in
    place. No lock, no serialisation between concurrent callers, and a row
    count bounded by (keys x minutes) rather than by traffic.

    No ``UUIDMixin``: the natural key *is* the pair, and it is what the
    upsert conflicts on.
    """

    __tablename__ = "api_key_usage"

    api_key_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        primary_key=True,
    )
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        # Declared here as well as in migration 0017, which creates
        # ``ix_api_key_usage_window_start`` -- the name SQLAlchemy's default
        # ``ix_<table>_<column>`` produces, so the two agree exactly. Without
        # it the next ``alembic revision --autogenerate`` would see an index
        # in the database that the metadata does not declare and propose
        # *dropping* it, taking ``sweep``'s range delete to a sequential scan.
        index=True,
    )
    count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
