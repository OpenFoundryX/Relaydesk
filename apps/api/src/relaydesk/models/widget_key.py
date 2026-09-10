import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin, UUIDMixin


class WidgetKey(UUIDMixin, TimestampMixin, Base):
    """A workspace's embed credential, published in other people's page source.

    ``key`` is stored verbatim, which departs from every bearer credential in
    this schema: ``ApiKey`` keeps only a SHA-256 digest and shows its secret
    exactly once. Neither is possible here. This value is printed in the HTML
    of every site that embeds the widget, so it is not secret at any point in
    its life, and an admin has to be able to read it back forever to re-paste
    the snippet. A digest cannot serve a credential that is public by
    construction. Spec D1 records why a ``public`` scope on ``ApiKey`` was
    rejected rather than this table added: a bearer token and an embed key
    sharing one table is how an ``rd_live_`` secret eventually ends up inside
    a ``<script>`` tag.

    Holding this key grants nothing anonymity did not already grant. Every
    endpoint it reaches is public: the knowledge base is a published help
    site and ticket submission is already an open endpoint. That is what
    makes ``allowed_origins`` -- enforced with ``frame-ancestors``, and so
    enforced by browsers and by nothing else -- an acceptable control. Spec
    D2 states the consequence: if a later slice gives the widget anything a
    stranger should not have, this model is wrong for it and needs verified
    identity, not more origins.

    ``allowed_origins`` holds exact origins, scheme and host and port, with
    no wildcards. An empty list refuses embedding rather than permitting it,
    so a key that has been created but not configured is inert.

    There is no ``revoked_at``. Unlike a bearer token a widget key carries no
    history worth auditing once it is gone; deleting the row is the
    revocation and the embed then fails closed.
    """

    __tablename__ = "widget_keys"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # Read and written as a unit, never queried across rows.
    allowed_origins: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    settings: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Written at most once a minute per key, so "is this still installed?"
    # can be answered without a write per page view.
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
