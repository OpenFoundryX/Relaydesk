from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class PollState(UUIDMixin, TimestampMixin, Base):
    """Where the poller got to. One row per mailbox.

    ``uidvalidity`` is stored beside ``last_uid`` because IMAP servers may
    renumber UIDs; when the server reports a different value, every stored UID
    is meaningless and the poller must re-sync from zero.
    """

    __tablename__ = "poll_state"

    mailbox: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    uidvalidity: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    last_uid: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
