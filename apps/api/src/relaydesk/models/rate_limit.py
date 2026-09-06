from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, UUIDMixin


class RateLimitHit(UUIDMixin, Base):
    """One recorded call against a rate-limited endpoint.

    Deliberately not workspace-scoped: the caller is anonymous and the whole
    point is to bound them before any workspace is trusted. Rows are counted
    inside a window and swept by age, never read individually -- the sweep
    is `relaydesk.services.ratelimit.sweep`, run on the beat schedule in
    `relaydesk.worker.app` by `relaydesk.worker.tasks.ratelimit`.
    """

    __tablename__ = "rate_limit_hits"
    __table_args__ = (
        sa.Index("ix_rate_limit_hits_lookup", "bucket", "key", "created_at"),
    )

    bucket: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    key: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
