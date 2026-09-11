import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from relaydesk.db.base import Base, TimestampMixin

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_DAILY_TOKEN_BUDGET = 200_000


class AiConfig(Base, TimestampMixin):
    """How one workspace reaches a model, and what it is willing to spend.

    ``workspace_id`` is the primary key: a workspace has one configuration
    or none. There is deliberately no per-embed override -- a workspace
    running two widgets gets the same answering behaviour on both, and
    spend is a property of the workspace rather than of a script tag.

    ``api_key`` is **write-only**. It is set through the console and never
    returned by any endpoint; the console shows a masked suffix so an admin
    can tell which key is installed without being handed it back. That
    departs from ``Webhook.secret``, which is stored in plaintext and *is*
    returned, and the reason is that a webhook signature needs the same key
    at both ends while a model key needs only this server. It cannot be a
    digest either -- the value has to be replayed to the provider -- so a
    database compromise discloses it, and that is the cost this design
    accepts rather than hides.

    ``enabled`` is separate from ``api_key`` being present so a workspace
    can switch the feature off without discarding what it configured.

    ``base_url`` set means the workspace is pointing at inference it hosts
    itself, which is what makes redaction skippable (spec D6): the text
    never leaves their deployment.
    """

    __tablename__ = "ai_configs"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    provider: Mapped[str] = mapped_column(
        String(32), nullable=False, default="anthropic", server_default="anthropic"
    )
    model: Mapped[str] = mapped_column(
        String(64), nullable=False, default=DEFAULT_MODEL, server_default=DEFAULT_MODEL
    )
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    daily_token_budget: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_DAILY_TOKEN_BUDGET,
        server_default=str(DEFAULT_DAILY_TOKEN_BUDGET),
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
